"""
ai/AGENT.md: "Ingest after each SerpApi fetch, in the background.
Ingestion failures are logged, never fail the request." and "No user
names, emails, or free text in Neo4j."

Every function here takes already-normalized data (from tools/serpapi.py
or tools/geo.py) and never a raw SerpApi payload or anything containing a
user's name/email. `trip_id` passed in must already be the anonymized ID
apps/api uses for KG linkage, never the user's account ID.
"""
from __future__ import annotations

import logging

from app.kg import queries
from app.kg.driver import run_write
from app.tools.serpapi import NormalizedEvent, NormalizedHotel, NormalizedPlace

logger = logging.getLogger("services.ai.kg.ingest")


async def _safe_write(query: str, params: dict, *, what: str) -> None:
    try:
        await run_write(query, params)
    except Exception:  # noqa: BLE001 - ingestion must never fail the request
        logger.warning("kg_ingest_failed", extra={"what": what}, exc_info=True)


async def ingest_place(place: Any, *, city: str, country: str) -> None:
    lat = getattr(place, "lat", None) or (place.location.lat if hasattr(place, "location") else None)
    lng = getattr(place, "lng", None) or (place.location.lng if hasattr(place, "location") else None)
    await _safe_write(queries.MERGE_CITY, {"name": city, "country": country}, what="city")
    await _safe_write(
        queries.MERGE_PLACE,
        {
            "provider_id": place.provider_ref.id,
            "name": place.name,
            "lat": lat,
            "lng": lng,
            "rating": place.rating,
            "city": city,
            "country": country,
        },
        what="place",
    )


async def ingest_place_vibe_scores(provider_id: str, vibe_scores: list[tuple[str, float]]) -> None:
    for vibe, score in vibe_scores:
        await _safe_write(
            queries.MERGE_PLACE_VIBE,
            {"provider_id": provider_id, "vibe": vibe, "score": score},
            what="place_vibe",
        )


async def ingest_hotel(hotel: Any, *, city: str, country: str) -> None:
    lat = getattr(hotel, "lat", None) or (hotel.location.lat if hasattr(hotel, "location") else None)
    lng = getattr(hotel, "lng", None) or (hotel.location.lng if hasattr(hotel, "location") else None)
    await _safe_write(queries.MERGE_CITY, {"name": city, "country": country}, what="city")
    await _safe_write(
        queries.MERGE_HOTEL,
        {
            "provider_id": hotel.provider_ref.id,
            "name": hotel.name,
            "lat": lat,
            "lng": lng,
            "rating": hotel.rating,
            "city": city,
            "country": country,
        },
        what="hotel",
    )


async def ingest_hotel_near_place(hotel_provider_id: str, place_provider_id: str, km: float) -> None:
    await _safe_write(
        queries.MERGE_HOTEL_NEAR_PLACE,
        {"hotel_provider_id": hotel_provider_id, "place_provider_id": place_provider_id, "km": km},
        what="hotel_near_place",
    )


async def ingest_event(event: NormalizedEvent, *, city: str, country: str) -> None:
    if event.date is None:
        return  # KG model keys Event on (name, date); skip undated events
    await _safe_write(queries.MERGE_CITY, {"name": city, "country": country}, what="city")
    await _safe_write(
        queries.MERGE_EVENT,
        {
            "name": event.name,
            "date": event.date.isoformat(),
            "venue": event.venue,
            "city": city,
            "country": country,
        },
        what="event",
    )


async def ingest_trip_context(
    trip_id: str, *, city: str, country: str, wanted_vibes: list[str]
) -> None:
    """trip_id must be the anonymized ID — see module docstring."""
    await _safe_write(queries.MERGE_CITY, {"name": city, "country": country}, what="city")
    await _safe_write(
        queries.MERGE_TRIP, {"trip_id": trip_id, "city": city, "country": country}, what="trip"
    )
    for vibe in wanted_vibes:
        await _safe_write(
            queries.MERGE_TRIP_WANTED_VIBE, {"trip_id": trip_id, "vibe": vibe}, what="trip_wanted_vibe"
        )


async def ingest_trip_selected_place(trip_id: str, provider_id: str) -> None:
    await _safe_write(
        queries.MERGE_TRIP_SELECTED_PLACE,
        {"trip_id": trip_id, "provider_id": provider_id},
        what="trip_selected_place",
    )


async def ingest_trip_selected_hotel(trip_id: str, provider_id: str) -> None:
    await _safe_write(
        queries.MERGE_TRIP_SELECTED_HOTEL,
        {"trip_id": trip_id, "provider_id": provider_id},
        what="trip_selected_hotel",
    )
