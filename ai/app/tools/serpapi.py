"""
ai/AGENT.md "SerpApi": the ONLY SerpApi client in the service.
  - handles Redis caching (TTLs in root AGENTS.md §7)
  - fixtures when USE_LIVE_APIS is false (root AGENTS.md §7)
  - hard result caps (root AGENTS.md §7)
  - normalizes every response into our models immediately; raw SerpApi
    JSON never leaves this module
  - keeps provider deep links so the frontend can link out (we don't book)

Nothing outside app/tools/serpapi.py should import httpx/SerpApi types or
see a raw SerpApi JSON blob.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx

try:
    import redis.asyncio as redis_asyncio
except ImportError:  # pragma: no cover - redis is a declared dependency
    redis_asyncio = None  # type: ignore[assignment]

from app.config import get_settings

logger = logging.getLogger("services.ai.serpapi")

SERPAPI_BASE_URL = "https://serpapi.com/search"

Engine = str  # "google_flights" | "google_hotels" | "google_maps" | "google_maps_reviews" | "google_events"


# ---------------------------------------------------------------------------
# Normalized shapes. Graphs/nodes only ever see these, never raw SerpApi JSON.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedProviderRef:
    id: str
    deep_link: str | None = None


@dataclass(frozen=True)
class NormalizedFlightLeg:
    airline: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departs_at: datetime
    arrives_at: datetime


@dataclass(frozen=True)
class NormalizedFlight:
    provider_ref: NormalizedProviderRef
    outbound: list[NormalizedFlightLeg]
    inbound: list[NormalizedFlightLeg]
    price_amount_minor: int
    currency: str
    stops: int
    total_duration_minutes: int


@dataclass(frozen=True)
class NormalizedHotel:
    provider_ref: NormalizedProviderRef
    name: str
    lat: float
    lng: float
    price_per_night_amount_minor: int
    currency: str
    rating: float | None
    review_snippet: str | None


@dataclass(frozen=True)
class NormalizedPlace:
    provider_ref: NormalizedProviderRef
    name: str
    lat: float
    lng: float
    rating: float | None
    types: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NormalizedEvent:
    name: str
    date: date | None
    venue: str | None
    lat: float | None = None
    lng: float | None = None


# ---------------------------------------------------------------------------
# Cache key + fixture resolution
# ---------------------------------------------------------------------------


def _cache_key(engine: Engine, params: dict[str, Any]) -> str:
    normalized = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return f"serpapi:{engine}:{digest}"


def _fixture_slug(params: dict[str, Any]) -> str:
    normalized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


class FixtureNotFound(RuntimeError):
    pass


def _load_fixture(fixtures_dir: Path, engine: Engine, params: dict[str, Any]) -> dict[str, Any]:
    """
    Look for a query-specific fixture first (as written by
    scripts/record_fixture.py), then fall back to a generic
    `<engine>_sample.json` so the MVP demo works without recording a
    fixture for every single query shape.
    """
    specific = fixtures_dir / f"{engine}__{_fixture_slug(params)}.json"
    if specific.exists():
        with open(specific, encoding="utf-8") as f:
            return json.load(f)

    generic = fixtures_dir / f"{engine}_sample.json"
    if generic.exists():
        with open(generic, encoding="utf-8") as f:
            return json.load(f)

    raise FixtureNotFound(
        f"No fixture for engine={engine!r} params={params!r}. "
        f"Run scripts/record_fixture.py or add {generic.name}."
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class SerpApiClient:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis: Any | None = None

    async def _get_redis(self) -> Any | None:
        if redis_asyncio is None:
            return None
        if self._redis is None:
            try:
                self._redis = redis_asyncio.from_url(self._settings.redis_url)
            except Exception:  # pragma: no cover - defensive
                logger.warning("serpapi: could not init redis client", exc_info=True)
                return None
        return self._redis

    async def _cached_fetch(
        self, engine: Engine, params: dict[str, Any], ttl_seconds: int
    ) -> dict[str, Any]:
        key = _cache_key(engine, params)
        r = await self._get_redis()
        if r is not None:
            try:
                cached = await r.get(key)
                if cached:
                    return json.loads(cached)
            except Exception:  # pragma: no cover - cache is best-effort
                logger.warning("serpapi: redis get failed, continuing without cache", exc_info=True)

        raw = await self._fetch_raw(engine, params)

        if r is not None:
            try:
                await r.set(key, json.dumps(raw, default=str), ex=ttl_seconds)
            except Exception:  # pragma: no cover
                logger.warning("serpapi: redis set failed", exc_info=True)

        return raw

    async def _fetch_raw(self, engine: Engine, params: dict[str, Any]) -> dict[str, Any]:
        if not self._settings.use_live_apis:
            return _load_fixture(self._settings.fixtures_dir, engine, params)

        query = {**params, "engine": engine, "api_key": self._settings.serpapi_key}
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(SERPAPI_BASE_URL, params=query)
            resp.raise_for_status()
            return resp.json()

    # -- public, per-engine methods -----------------------------------

    async def search_flights(
        self, *, source: str, destination: str, start_date: date, end_date: date, cap: int | None = None
    ) -> list[NormalizedFlight]:
        params = {
            "departure_id": source,
            "arrival_id": destination,
            "outbound_date": start_date.isoformat(),
            "return_date": end_date.isoformat(),
        }
        raw = await self._cached_fetch("google_flights", params, self._settings.ttl_flights)
        flights = _normalize_flights(raw)
        cap = cap or self._settings.cap_flights
        return flights[:cap]

    async def search_hotels(
        self, *, city: str, lat: float, lng: float, check_in: date, check_out: date, cap: int | None = None
    ) -> list[NormalizedHotel]:
        params = {
            "q": f"hotels in {city}",
            "lat": round(lat, 3),
            "lng": round(lng, 3),
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
        }
        raw = await self._cached_fetch("google_hotels", params, self._settings.ttl_hotels)
        hotels = _normalize_hotels(raw)
        cap = cap or self._settings.cap_hotels
        return hotels[:cap]

    async def search_places(self, *, city: str, query: str, cap: int | None = None) -> list[NormalizedPlace]:
        params = {"q": f"{query} in {city}"}
        raw = await self._cached_fetch("google_maps", params, self._settings.ttl_places)
        places = _normalize_places(raw)
        cap = cap or self._settings.cap_spots
        return places[:cap]

    async def search_events(
        self, *, city: str, start_date: date, end_date: date, cap: int | None = None
    ) -> list[NormalizedEvent]:
        params = {"q": f"events in {city}", "start": start_date.isoformat(), "end": end_date.isoformat()}
        raw = await self._cached_fetch("google_events", params, self._settings.ttl_places)
        events = _normalize_events(raw)
        cap = cap or self._settings.cap_spots
        return events[:cap]


# ---------------------------------------------------------------------------
# Per-engine normalizers. Defensive against missing fields — fixtures and
# live payloads are both "whatever SerpApi felt like returning that day".
# ---------------------------------------------------------------------------


def _normalize_flights(raw: dict[str, Any]) -> list[NormalizedFlight]:
    out: list[NormalizedFlight] = []
    for group_key in ("best_flights", "other_flights"):
        for item in raw.get(group_key, []):
            flights_legs = item.get("flights", [])
            if not flights_legs:
                continue
            legs = [
                NormalizedFlightLeg(
                    airline=leg.get("airline", "Unknown"),
                    flight_number=leg.get("flight_number", ""),
                    departure_airport=leg.get("departure_airport", {}).get("id", ""),
                    arrival_airport=leg.get("arrival_airport", {}).get("id", ""),
                    departs_at=_parse_dt(leg.get("departure_airport", {}).get("time")),
                    arrives_at=_parse_dt(leg.get("arrival_airport", {}).get("time")),
                )
                for leg in flights_legs
            ]
            out.append(
                NormalizedFlight(
                    provider_ref=NormalizedProviderRef(
                        id=item.get("departure_token")
                        or item.get("booking_token")
                        or legs[0].flight_number,
                        deep_link=item.get("booking_link")
                        or raw.get("search_metadata", {}).get("google_flights_url"),
                    ),
                    outbound=legs,
                    inbound=[],
                    price_amount_minor=int(round(float(item.get("price", 0)) * 100)),
                    currency=raw.get("search_parameters", {}).get("currency", "USD"),
                    stops=max(0, len(legs) - 1),
                    total_duration_minutes=int(item.get("total_duration", 0)),
                )
            )
    out.sort(key=lambda f: f.price_amount_minor)
    return out


def _normalize_hotels(raw: dict[str, Any]) -> list[NormalizedHotel]:
    out: list[NormalizedHotel] = []
    for item in raw.get("properties", []):
        coords = item.get("gps_coordinates", {})
        if "latitude" not in coords or "longitude" not in coords:
            continue
        rate = item.get("rate_per_night", {})
        out.append(
            NormalizedHotel(
                provider_ref=NormalizedProviderRef(
                    id=item.get("property_token", item.get("name", "")),
                    deep_link=item.get("link"),
                ),
                name=item.get("name", "Unknown hotel"),
                lat=float(coords["latitude"]),
                lng=float(coords["longitude"]),
                price_per_night_amount_minor=int(round(float(rate.get("extracted_lowest", 0)) * 100)),
                currency=rate.get("currency", "USD"),
                rating=item.get("overall_rating"),
                review_snippet=_first_review_snippet(item),
            )
        )
    return out


def _first_review_snippet(item: dict[str, Any]) -> str | None:
    reviews = item.get("reviews_breakdown") or item.get("reviews")
    if isinstance(reviews, list) and reviews:
        first = reviews[0]
        if isinstance(first, dict):
            return first.get("snippet") or first.get("description")
    return None


def _normalize_places(raw: dict[str, Any]) -> list[NormalizedPlace]:
    out: list[NormalizedPlace] = []
    for item in raw.get("local_results", raw.get("place_results", [])) or []:
        coords = item.get("gps_coordinates", {})
        if "latitude" not in coords or "longitude" not in coords:
            continue
        out.append(
            NormalizedPlace(
                provider_ref=NormalizedProviderRef(
                    id=item.get("place_id", item.get("data_id", item.get("title", ""))),
                    deep_link=item.get("link"),
                ),
                name=item.get("title", "Unknown place"),
                lat=float(coords["latitude"]),
                lng=float(coords["longitude"]),
                rating=item.get("rating"),
                types=item.get("type", []) if isinstance(item.get("type"), list) else [],
            )
        )
    return out


def _normalize_events(raw: dict[str, Any]) -> list[NormalizedEvent]:
    out: list[NormalizedEvent] = []
    for item in raw.get("events_results", []) or []:
        when = item.get("date", {})
        venue = item.get("venue", {})
        out.append(
            NormalizedEvent(
                name=item.get("title", "Unknown event"),
                date=_parse_date(when.get("start_date")),
                venue=venue.get("name"),
            )
        )
    return out


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime(1970, 1, 1)
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime(1970, 1, 1)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%b %d", "%Y-%m-%d", "%b %d, %Y"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.date()
        except ValueError:
            continue
    return None
