import json
from datetime import date

import pytest

from app.graphs.discover_spots import SpotDeps, run
from app.llm.provider import LLMProvider, ProviderUnavailable
from app.schemas.spots import SpotDiscoverRequest
from app.tools.serpapi import SerpApiClient
from tests.conftest import FakeLLMBackend


def _request() -> SpotDiscoverRequest:
    return SpotDiscoverRequest(
        trip_id="trip-1",
        city="Paris",
        country="France",
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 17),
        vibes=["nightlife", "culture_heritage", "food"],
    )


@pytest.mark.asyncio
async def test_happy_path_llm_tags_the_unconfident_place():
    # google_maps_sample.json has one place ("Zephyrion Pavilion") with no
    # keyword-matchable type, so it should be sent to the LLM for tagging.
    llm_response = json.dumps(
        {"tags": [{"placeId": "place-mystery-5", "vibeScores": [{"vibe": "culture_heritage", "score": 0.7}]}]}
    )
    deps = SpotDeps(
        serpapi=SerpApiClient(),
        llm=LLMProvider(backends=[FakeLLMBackend("gemini", response_json=llm_response)]),
    )
    response = await run(_request(), deps=deps)

    assert response.fallback_used is False
    mystery = next(s for s in response.spots if s.name == "Zephyrion Pavilion")
    assert mystery.tag_source == "llm"
    assert any(vs.vibe == "culture_heritage" for vs in mystery.vibe_scores)

    bar = next(s for s in response.spots if "Sunset" in s.name)
    assert bar.tag_source == "keyword_match"
    assert any(vs.vibe == "nightlife" for vs in bar.vibe_scores)


@pytest.mark.asyncio
async def test_llm_unavailable_keeps_keyword_tags_for_everyone():
    deps = SpotDeps(
        serpapi=SerpApiClient(),
        llm=LLMProvider(backends=[FakeLLMBackend("gemini", raise_exc=ProviderUnavailable("no key"))]),
    )
    response = await run(_request(), deps=deps)

    assert response.fallback_used is True
    assert all(s.tag_source == "keyword_match" for s in response.spots)
    assert len(response.spots) == 5


@pytest.mark.asyncio
async def test_matching_event_is_attached_when_venue_matches_a_spot():
    deps = SpotDeps(
        serpapi=SerpApiClient(),
        llm=LLMProvider(backends=[FakeLLMBackend("gemini", raise_exc=ProviderUnavailable("no key"))]),
    )
    response = await run(_request(), deps=deps)
    market = next(s for s in response.spots if s.name == "Riverside Market")
    assert market.matching_event is not None
    assert market.matching_event.name == "Riverside Market Night Market"
