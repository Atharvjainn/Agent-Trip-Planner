"""
ai/AGENT.md graph table, search_flights:
  SerpApi Google Flights -> normalize -> sort by price within flights budget.
  Fallback: n/a (no LLM).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TypedDict

import httpx
from langgraph.graph import END, StateGraph

from app.config import get_settings
from app.schemas.common import Money, ProviderRef
from app.schemas.flights import FlightLeg, FlightOption, FlightSearchRequest, FlightSearchResponse
from app.tools.serpapi import FixtureNotFound, NormalizedFlight, SerpApiClient

logger = logging.getLogger("services.ai.graphs.search_flights")


@dataclass
class FlightDeps:
    serpapi: SerpApiClient


def default_deps() -> FlightDeps:
    return FlightDeps(serpapi=SerpApiClient())


class FlightState(TypedDict, total=False):
    request: FlightSearchRequest
    deps: FlightDeps
    raw: list[NormalizedFlight]
    options: list[FlightOption]


async def node_fetch(state: FlightState) -> dict:
    req = state["request"]
    deps = state["deps"]
    try:
        flights = await deps.serpapi.search_flights(
            source=req.source, destination=req.destination, start_date=req.start_date, end_date=req.end_date
        )
    except (FixtureNotFound, httpx.HTTPStatusError, httpx.RequestError) as exc:
        # No LLM fallback exists for this job (ai/AGENT.md: "n/a (no
        # LLM)"), so the fallback here is simply an empty result set —
        # apps/web's documented "empty state" for this screen is exactly
        # for this case, rather than a 500.
        logger.warning(
            "search_flights: SerpApi call failed (%s), returning empty results", type(exc).__name__
        )
        flights = []
    return {"raw": flights}


async def node_filter_and_sort(state: FlightState) -> dict:
    req = state["request"]
    settings = get_settings()
    budget_minor = req.flights_budget.amount_minor

    # Within-budget options first (still price-sorted), then the cheapest
    # over-budget options after — so the page always has something to
    # show even if nothing fits, per apps/web's "empty state" requirement.
    within_budget = [f for f in state["raw"] if f.price_amount_minor <= budget_minor]
    over_budget = [f for f in state["raw"] if f.price_amount_minor > budget_minor]
    ordered = within_budget + over_budget

    options = [
        FlightOption(
            provider_ref=ProviderRef(id=f.provider_ref.id, deep_link=f.provider_ref.deep_link),
            outbound=[
                FlightLeg(
                    airline=leg.airline,
                    flight_number=leg.flight_number,
                    departure_airport=leg.departure_airport,
                    arrival_airport=leg.arrival_airport,
                    departs_at=leg.departs_at,
                    arrives_at=leg.arrives_at,
                )
                for leg in f.outbound
            ],
            inbound=[
                FlightLeg(
                    airline=leg.airline,
                    flight_number=leg.flight_number,
                    departure_airport=leg.departure_airport,
                    arrival_airport=leg.arrival_airport,
                    departs_at=leg.departs_at,
                    arrives_at=leg.arrives_at,
                )
                for leg in f.inbound
            ],
            price=Money(amount_minor=f.price_amount_minor, currency=f.currency),
            stops=f.stops,
            total_duration_minutes=f.total_duration_minutes,
        )
        for f in ordered[: settings.cap_flights]
    ]
    return {"options": options}


def build_graph():
    graph = StateGraph(FlightState)
    graph.add_node("fetch", node_fetch)
    graph.add_node("filter_and_sort", node_filter_and_sort)
    graph.set_entry_point("fetch")
    graph.add_edge("fetch", "filter_and_sort")
    graph.add_edge("filter_and_sort", END)
    return graph.compile()


_compiled = None


async def run(request: FlightSearchRequest, deps: FlightDeps | None = None) -> FlightSearchResponse:
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    result = await _compiled.ainvoke({"request": request, "deps": deps or default_deps()})
    return FlightSearchResponse(trip_id=request.trip_id, options=result["options"], fallback_used=False)
