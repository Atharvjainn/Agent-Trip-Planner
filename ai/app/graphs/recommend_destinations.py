"""
ai/AGENT.md graph table, recommend_destinations:
  parse input -> KG candidates (vibe + budget + season) -> SerpApi flights
  price check from source -> LLM rank + reasons -> top 5.
  Fallback: KG/vibe-score ranking, generic reasons.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import Field

from app.config import get_settings
from app.kg.reads import candidate_cities_by_vibe
from app.llm.prompts.recommend_destinations import SYSTEM, build_prompt
from app.llm.provider import LLMAllProvidersFailed, LLMProvider
from app.rules.destination_seed import seed_candidates
from app.schemas.common import CamelModel, Money
from app.schemas.destinations import (
    DestinationOption,
    DestinationRecommendRequest,
    DestinationRecommendResponse,
)
from app.tools.serpapi import SerpApiClient
try:
    from tools.serpapi_client import resolve_departure_id
except Exception:  # noqa: BLE001
    def resolve_departure_id(city_text: str) -> str | None:  # type: ignore[misc]
        return city_text if (len(city_text) == 3 and city_text.isupper()) else None

logger = logging.getLogger("services.ai.graphs.recommend_destinations")


# --- LLM-facing schema for the ranking step --------------------------------


class _LlmDestinationOption(CamelModel):
    city: str
    country: str
    estimated_flight_price: Money
    vibe_match_score: float = Field(ge=0, le=1)
    reason: str
    source: str = "llm"


class _LlmRankResult(CamelModel):
    options: list[_LlmDestinationOption] = Field(max_length=5)


# --- Dependency seam, so tests substitute fakes for KG/SerpApi/LLM ---------


@dataclass
class RecommendDeps:
    kg_candidates: Callable[[list[str], int], Awaitable[list[dict]]]
    serpapi: SerpApiClient
    llm: LLMProvider


def default_deps() -> RecommendDeps:
    return RecommendDeps(kg_candidates=candidate_cities_by_vibe, serpapi=SerpApiClient(), llm=LLMProvider())


# --- Graph state -------------------------------------------------------------


class DestState(TypedDict, total=False):
    request: DestinationRecommendRequest
    deps: RecommendDeps
    candidates: list[dict[str, Any]]
    priced_candidates: list[dict[str, Any]]
    options: list[DestinationOption]
    fallback_used: bool


# --- Nodes --------------------------------------------------------------


async def node_gather_candidates(state: DestState) -> dict:
    req = state["request"]
    deps = state["deps"]
    settings = get_settings()
    cap = settings.cap_destination_candidates
    threshold = settings.graph_similarity_threshold

    learned_candidates: list[dict[str, Any]] = []
    try:
        from app.kg.reads import find_experienced_destinations

        learned = await find_experienced_destinations(req.vibes, threshold=threshold, limit=cap)
        for c in learned:
            learned_candidates.append(
                {
                    "city": c["city"],
                    "country": c["country"],
                    "vibeScore": c.get("vibeScore", 0.9),
                    "source": "learned_experience",
                }
            )
    except Exception:  # noqa: BLE001
        logger.warning("recommend_destinations: experience lookup failed", exc_info=True)
        learned_candidates = []

    # Decision Gate: if experienced destinations >= cap exist, use them directly as primary source
    if len(learned_candidates) >= cap:
        return {"candidates": learned_candidates[:cap]}

    # Otherwise (when learned candidates with similarity >= threshold are fewer than cap), supplement with normal discovery
    needed_kg = cap - len(learned_candidates)
    kg_candidates = await deps.kg_candidates(req.vibes, needed_kg)
    for c in kg_candidates:
        c.setdefault("source", "knowledge_graph")

    # De-dupe learned + normal KG candidates, preserving learned historical experiences
    seen: set[tuple[str, str]] = set()
    merged_kg: list[dict[str, Any]] = []
    for c in learned_candidates + kg_candidates:
        key = (c["city"], c["country"])
        if key in seen:
            continue
        seen.add(key)
        merged_kg.append(c)

    if len(merged_kg) >= cap:
        return {"candidates": merged_kg[:cap]}

    # Cold start (ai/AGENT.md): try LLM-generated candidates first.
    needed = cap - len(merged_kg)
    cold_start: list[dict[str, Any]] = []
    try:
        prompt = (
            f"Suggest {needed} more candidate destination cities (not already "
            f"in {[c['city'] for c in merged_kg]}) matching vibes "
            f"{req.vibes}, reachable from {req.source}, within a total trip "
            f"budget of {req.budget_total.amount_minor} {req.budget_total.currency} "
            f"minor units.\n"
            f'Return JSON with format: {{"candidates": [{{"city": str, "country": str, "vibeScore": float}}]}}\n'
            f"Requirements:\n"
            f"- vibeScore MUST be a decimal float between 0.0 and 1.0 (e.g. 0.85). Never use a 0-10 or 0-100 scale.\n"
            f'- Return EXACTLY these three fields for each candidate: "city", "country", "vibeScore".\n'
            f'- Do NOT include "reason" or any other additional fields.'
        )
        result = await deps.llm.structured(
            "recommend_destinations.cold_start", prompt, _ColdStartResult, system=SYSTEM
        )
        cold_start = [
            {"city": c.city, "country": c.country, "vibeScore": c.vibe_score, "source": "llm_cold_start"}
            for c in result.candidates
        ]
    except LLMAllProvidersFailed:
        cold_start = seed_candidates(req.vibes, needed)
        for c in cold_start:
            c["source"] = "seed_pool_fallback"

    merged = merged_kg + cold_start
    # de-dupe by (city, country), preserving order
    seen.clear()
    deduped = []
    for c in merged:
        key = (c["city"], c["country"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return {"candidates": deduped[:cap]}


class _ColdStartCandidate(CamelModel):
    city: str
    country: str
    vibe_score: float = Field(ge=0, le=1)


class _ColdStartResult(CamelModel):
    candidates: list[_ColdStartCandidate]


async def node_price_check(state: DestState) -> dict:
    """Numbers come from SerpApi, never the LLM (ai/AGENT.md: graph rules)."""
    req = state["request"]
    deps = state["deps"]
    priced = []
    for candidate in state["candidates"]:
        try:
            dest_id = resolve_departure_id(candidate["city"])
            if dest_id:
                flights = await deps.serpapi.search_flights(
                    source=req.source,
                    destination=dest_id,
                    start_date=req.start_date,
                    end_date=req.end_date,
                    currency=req.budget_total.currency,
                    cap=1,
                )
                if flights:
                    price = Money(amount_minor=flights[0].price_amount_minor, currency=flights[0].currency)
                else:
                    price = _fallback_price(req)
            else:
                logger.warning(
                    "recommend_destinations: could not resolve destination ID for %s, using fallback price",
                    candidate["city"],
                )
                price = _fallback_price(req)
        except Exception as exc:
            # A bad live-API param (e.g. a city name where SerpApi wants an
            # IATA code) or any transient network/SerpApi error must not
            # crash the whole recommendation — this price is only a
            # ranking signal, not something shown to the user as a real
            # flight. Fall back to the budget-derived estimate instead.
            logger.exception(
                "Price check failed for %s",
                candidate["city"],
            )
            price = _fallback_price(req)
        priced.append({**candidate, "estimatedFlightPrice": price})
    return {"priced_candidates": priced}


def _fallback_price(req: DestinationRecommendRequest) -> Money:
    # No real flight data available for this candidate at all (fixture
    # missing and USE_LIVE_APIS is off, or the live call failed) — fall
    # back to a rough, clearly-an-estimate share of the trip budget rather
    # than blocking the whole recommendation on one bad lookup.
    return Money(amount_minor=round(req.budget_total.amount_minor * 0.3), currency=req.budget_total.currency)


async def node_rank(state: DestState) -> dict:
    req = state["request"]
    deps = state["deps"]
    candidates = state["priced_candidates"]

    try:
        prompt = build_prompt(
            source=req.source,
            budget_total_minor=req.budget_total.amount_minor,
            currency=req.budget_total.currency,
            travelers=req.travelers,
            duration_days=(req.end_date - req.start_date).days,
            vibes=req.vibes,
            candidates=[
                {
                    "city": c["city"],
                    "country": c["country"],
                    "estimatedFlightPrice": {
                        "amountMinor": c["estimatedFlightPrice"].amount_minor,
                        "currency": c["estimatedFlightPrice"].currency,
                    },
                    "vibeMatchScore": c.get("vibeScore", 0.5),
                }
                for c in candidates
            ],
        )
        result = await deps.llm.structured(
            "recommend_destinations.rank", prompt, _LlmRankResult, system=SYSTEM
        )
        options = [
            DestinationOption(
                city=o.city,
                country=o.country,
                estimated_flight_price=o.estimated_flight_price,
                vibe_match_score=o.vibe_match_score,
                reason=o.reason,
                source="llm",
            )
            for o in result.options
        ]
        return {"options": options, "fallback_used": False}
    except LLMAllProvidersFailed:
        logger.info("recommend_destinations: LLM rank unavailable, using vibe-score fallback ranking")
        sorted_candidates = sorted(
            candidates,
            key=lambda c: (-c.get("vibeScore", 0.5), c["estimatedFlightPrice"].amount_minor),
        )[:5]
        options = [
            DestinationOption(
                city=c["city"],
                country=c["country"],
                estimated_flight_price=c["estimatedFlightPrice"],
                vibe_match_score=c.get("vibeScore", 0.5),
                reason=f"Matches your {', '.join(req.vibes) or 'trip'} vibe and fits your flight budget.",
                source="knowledge_graph",
            )
            for c in sorted_candidates
        ]
        return {"options": options, "fallback_used": True}


# --- Graph assembly -------------------------------------------------------


def build_graph():
    graph = StateGraph(DestState)
    graph.add_node("gather_candidates", node_gather_candidates)
    graph.add_node("price_check", node_price_check)
    graph.add_node("rank", node_rank)
    graph.set_entry_point("gather_candidates")
    graph.add_edge("gather_candidates", "price_check")
    graph.add_edge("price_check", "rank")
    graph.add_edge("rank", END)
    return graph.compile()


_compiled = None


async def run(
    request: DestinationRecommendRequest, deps: RecommendDeps | None = None
) -> DestinationRecommendResponse:
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    result: DestState = await _compiled.ainvoke(
        {"request": request, "deps": deps or default_deps()}
    )
    return DestinationRecommendResponse(
        trip_id=request.trip_id,
        options=result["options"],
        fallback_used=result.get("fallback_used", False),
    )
