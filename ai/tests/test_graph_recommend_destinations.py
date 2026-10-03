import json
from datetime import date
from unittest.mock import AsyncMock

import httpx
import pytest

from app.graphs.recommend_destinations import RecommendDeps, run
from app.llm.provider import LLMProvider, ProviderUnavailable
from app.schemas.common import Money
from app.schemas.destinations import DestinationRecommendRequest
from app.tools.serpapi import SerpApiClient
from tests.conftest import FakeLLMBackend


def _request() -> DestinationRecommendRequest:
    return DestinationRecommendRequest(
        trip_id="trip-1",
        source="JFK",
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 17),
        travelers=2,
        budget_total=Money(amount_minor=200000, currency="USD"),
        vibes=["food", "culture_heritage"],
    )


async def _kg_candidates_enough(vibes, limit):
    # Enough candidates that the cold-start path never triggers.
    return [
        {"city": "Paris", "country": "France", "vibeScore": 0.9},
        {"city": "Rome", "country": "Italy", "vibeScore": 0.85},
        {"city": "Kyoto", "country": "Japan", "vibeScore": 0.8},
        {"city": "Lyon", "country": "France", "vibeScore": 0.75},
        {"city": "Osaka", "country": "Japan", "vibeScore": 0.7},
    ][:limit]


async def _kg_candidates_cold_start(vibes, limit):
    return [{"city": "Paris", "country": "France", "vibeScore": 0.9}]


@pytest.mark.asyncio
async def test_happy_path_llm_ranks_top_5():
    llm_response = json.dumps(
        {
            "options": [
                {
                    "city": "Paris",
                    "country": "France",
                    "estimatedFlightPrice": {"amountMinor": 61200, "currency": "USD"},
                    "vibeMatchScore": 0.9,
                    "reason": "Great food and heritage match.",
                    "source": "llm",
                }
            ]
        }
    )
    deps = RecommendDeps(
        kg_candidates=_kg_candidates_enough,
        serpapi=SerpApiClient(),  # fixtures-backed, no live network
        llm=LLMProvider(backends=[FakeLLMBackend("gemini", response_json=llm_response)]),
    )
    response = await run(_request(), deps=deps)
    assert response.fallback_used is False
    assert len(response.options) == 1
    assert response.options[0].city == "Paris"
    assert response.options[0].source == "llm"


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_vibe_score_ranking():
    deps = RecommendDeps(
        kg_candidates=_kg_candidates_enough,
        serpapi=SerpApiClient(),
        llm=LLMProvider(backends=[FakeLLMBackend("gemini", raise_exc=ProviderUnavailable("no key"))]),
    )
    response = await run(_request(), deps=deps)
    assert response.fallback_used is True
    assert len(response.options) == 5
    assert response.options[0].city == "Paris"  # highest vibeScore (0.9) sorts first
    assert response.options[0].source == "knowledge_graph"
    assert "vibe" in response.options[0].reason.lower() or "budget" in response.options[0].reason.lower()


@pytest.mark.asyncio
async def test_cold_start_falls_back_to_seed_pool_when_kg_and_llm_both_unavailable():
    deps = RecommendDeps(
        kg_candidates=_kg_candidates_cold_start,
        serpapi=SerpApiClient(),
        llm=LLMProvider(backends=[FakeLLMBackend("gemini", raise_exc=ProviderUnavailable("no key"))]),
    )
    response = await run(_request(), deps=deps)
    # Should still produce options even though both KG and LLM failed to
    # give a full candidate set — the seed pool fills the gap.
    assert len(response.options) >= 1
    assert response.fallback_used is True


@pytest.mark.asyncio
async def test_live_serpapi_error_during_price_check_does_not_crash_the_request():
    # Regression test for a real production bug: a live SerpApi call that
    # returns a 4xx (e.g. a bad query param for a seed-pool candidate like
    # a city name where an IATA code was expected) used to propagate all
    # the way up and 500 the whole recommendation instead of falling back
    # to the budget-derived estimate price for that one candidate.
    serpapi = SerpApiClient()
    bad_response = httpx.Response(
        400, request=httpx.Request("GET", "https://serpapi.com/search")
    )
    serpapi.search_flights = AsyncMock(
        side_effect=httpx.HTTPStatusError("bad request", request=bad_response.request, response=bad_response)
    )

    deps = RecommendDeps(
        kg_candidates=_kg_candidates_enough,
        serpapi=serpapi,
        llm=LLMProvider(backends=[FakeLLMBackend("gemini", raise_exc=ProviderUnavailable("no key"))]),
    )

    response = await run(_request(), deps=deps)

    assert len(response.options) == 5
    # every candidate should have fallen back to the budget-derived estimate
    assert all(o.estimated_flight_price.amount_minor > 0 for o in response.options)
