"""
ai/AGENT.md graph table, search_hotels:
  spots centroid -> SerpApi Google Hotels near centroid -> distance to
  each spot -> score.
  Fallback: n/a (no LLM).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TypedDict

import httpx
from langgraph.graph import END, StateGraph

from app.config import get_settings
from app.kg import ingest as kg_ingest
from app.rules.hotel_scoring import HotelCandidate, score_hotels
from app.schemas.common import GeoPoint, Money, ProviderRef
from app.schemas.hotels import HotelOption, HotelSearchRequest, HotelSearchResponse, SpotDistance
from app.tools.geo import Point, centroid, haversine_km
from app.tools.serpapi import FixtureNotFound, NormalizedHotel, SerpApiClient

logger = logging.getLogger("services.ai.graphs.search_hotels")


@dataclass
class HotelDeps:
    serpapi: SerpApiClient


def default_deps() -> HotelDeps:
    return HotelDeps(serpapi=SerpApiClient())


class HotelState(TypedDict, total=False):
    request: HotelSearchRequest
    deps: HotelDeps
    centroid_point: Point
    raw: list[NormalizedHotel]
    options: list[HotelOption]


async def node_centroid(state: HotelState) -> dict:
    req = state["request"]
    points = [Point(lat=s.location.lat, lng=s.location.lng) for s in req.selected_spots]
    return {"centroid_point": centroid(points)}


async def node_fetch_hotels(state: HotelState) -> dict:
    req = state["request"]
    deps = state["deps"]
    c = state["centroid_point"]
    # check-in/check-out aren't on the request today (apps/api passes
    # nights + stay budget); derive a nominal window length equal to
    # `nights` starting "today" purely for the SerpApi query shape — the
    # actual dates live on the Trip row in Postgres, which this service
    # never reads (root AGENTS.md §4.4). apps/api should pass real dates
    # here if/when the hotel search needs to reflect the trip's actual
    # calendar; tracked as a follow-up, not guessed at silently.
    from datetime import date, timedelta

    today = date.today()
    try:
        hotels = await deps.serpapi.search_hotels(
            city=req.city, lat=c.lat, lng=c.lng, check_in=today, check_out=today + timedelta(days=req.nights)
        )
    except (FixtureNotFound, httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning("search_hotels: SerpApi call failed (%s), returning empty results", type(exc).__name__)
        hotels = []
    return {"raw": hotels}


async def node_score(state: HotelState) -> dict:
    req = state["request"]
    hotels = state["raw"]
    spot_points = [Point(lat=s.location.lat, lng=s.location.lng) for s in req.selected_spots]

    distances_per_hotel: list[list[float]] = []
    for hotel in hotels:
        hp = Point(lat=hotel.lat, lng=hotel.lng)
        distances_per_hotel.append([haversine_km(hp, sp) for sp in spot_points])

    candidates = [
        HotelCandidate(
            price_per_night_minor=hotel.price_per_night_amount_minor,
            avg_distance_km=(sum(d) / len(d)) if d else 0.0,
            rating=hotel.rating,
        )
        for hotel, d in zip(hotels, distances_per_hotel, strict=True)
    ]
    scores = score_hotels(candidates)

    settings = get_settings()
    options: list[HotelOption] = []
    for hotel, dists, score in zip(hotels, distances_per_hotel, scores, strict=True):
        options.append(
            HotelOption(
                provider_ref=ProviderRef(id=hotel.provider_ref.id, deep_link=hotel.provider_ref.deep_link),
                name=hotel.name,
                location=GeoPoint(lat=hotel.lat, lng=hotel.lng),
                price_per_night=Money(
                    amount_minor=hotel.price_per_night_amount_minor, currency=hotel.currency
                ),
                rating=hotel.rating,
                review_snippet=hotel.review_snippet,
                distances=[
                    SpotDistance(spot_id=spot.id, spot_name=spot.name, distance_km=round(dist, 2))
                    for spot, dist in zip(req.selected_spots, dists, strict=True)
                ],
                score=score,
            )
        )
    options.sort(key=lambda o: o.score, reverse=True)
    options = options[: settings.cap_hotels]

    async def _bg_ingest() -> None:
        try:
            for hotel in hotels:
                await kg_ingest.ingest_hotel(hotel, city=req.city, country="")
            for hotel, dists in zip(hotels, distances_per_hotel, strict=True):
                for spot, dist in zip(req.selected_spots, dists, strict=True):
                    await kg_ingest.ingest_hotel_near_place(hotel.provider_ref.id, spot.id, round(dist, 2))
        except Exception:  # noqa: BLE001
            pass

    import asyncio
    asyncio.create_task(_bg_ingest())

    return {"options": options}


def build_graph():
    graph = StateGraph(HotelState)
    graph.add_node("centroid", node_centroid)
    graph.add_node("fetch_hotels", node_fetch_hotels)
    graph.add_node("score", node_score)
    graph.set_entry_point("centroid")
    graph.add_edge("centroid", "fetch_hotels")
    graph.add_edge("fetch_hotels", "score")
    graph.add_edge("score", END)
    return graph.compile()


_compiled = None


async def run(request: HotelSearchRequest, deps: HotelDeps | None = None) -> HotelSearchResponse:
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    result = await _compiled.ainvoke({"request": request, "deps": deps or default_deps()})
    return HotelSearchResponse(trip_id=request.trip_id, options=result["options"], fallback_used=False)
