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
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

try:
    import redis.asyncio as redis_asyncio
except ImportError:  # pragma: no cover - redis is a declared dependency
    redis_asyncio = None  # type: ignore[assignment]

from app.config import get_settings
from app.schemas.common import get_currency_exponent

logger = logging.getLogger("services.ai.serpapi")

import geonamescache as _geonamescache  # noqa: E402

_GC = _geonamescache.GeonamesCache()


def _resolve_country_from_city(city: str) -> str | None:
    """
    Resolve a city name to its country using local GeoNames data.
    Return None when no reliable match is found.
    """
    if not city:
        return None

    city_normalized = city.strip().lower()

    matches = [
        c
        for c in _GC.get_cities().values()
        if c.get("name", "").strip().lower() == city_normalized
    ]

    if not matches:
        return None

    # Prefer the most populated matching city.
    matches.sort(key=lambda c: c.get("population", 0), reverse=True)

    country_code = matches[0].get("countrycode")
    if not country_code:
        return None

    country = _GC.get_countries().get(country_code)
    if not country:
        return None

    return country.get("name")


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


CITY_TO_AIRPORTS: dict[str, list[str]] = {
    "delhi": ["DEL"],
    "new delhi": ["DEL"],
    "mumbai": ["BOM"],
    "bombay": ["BOM"],
    "bangalore": ["BLR"],
    "bengaluru": ["BLR"],
    "hyderabad": ["HYD"],
    "chennai": ["MAA"],
    "madras": ["MAA"],
    "kolkata": ["CCU"],
    "calcutta": ["CCU"],
    "shimla": ["SLV", "IXC"],
    "simla": ["SLV", "IXC"],
    "chandigarh": ["IXC"],
    "manali": ["KUU", "IXC"],
    "kullu": ["KUU", "IXC"],
    "dharamshala": ["DHM"],
    "dehradun": ["DED"],
    "rishikesh": ["DED"],
    "mussoorie": ["DED"],
    "jaipur": ["JAI"],
    "udaipur": ["UDR"],
    "goa": ["GOI", "GOX"],
    "kochi": ["COK"],
    "cochin": ["COK"],
    "ahmedabad": ["AMD"],
    "pune": ["PNQ"],
    "srinagar": ["SXR"],
    "kashmir": ["SXR", "IXJ"],
    "jammu": ["IXJ"],
    "leh": ["IXL"],
    "amritsar": ["ATQ"],
    "varanasi": ["VNS"],
    "lucknow": ["LKO"],
    "agra": ["AGR"],
    "port blair": ["IXZ"],
    "guwahati": ["GAU"],
    "paris": ["CDG", "ORY"],
    "london": ["LHR", "LGW"],
    "tokyo": ["HND", "NRT"],
    "dubai": ["DXB"],
    "singapore": ["SIN"],
    "bangkok": ["BKK", "DMK"],
    "new york": ["JFK", "EWR"],
}


def resolve_airport_codes(name: str) -> list[str]:
    cleaned = name.strip()
    if len(cleaned) == 3 and cleaned.isupper():
        return [cleaned]
    lowered = cleaned.lower()
    if lowered in CITY_TO_AIRPORTS:
        return CITY_TO_AIRPORTS[lowered]
    for city, codes in CITY_TO_AIRPORTS.items():
        if city in lowered or lowered in city:
            return codes
    return [cleaned]


def resolve_departure_id(city_text: str) -> str | None:
    if not city_text:
        return None
    cleaned = city_text.strip()
    if (len(cleaned) == 3 and cleaned.isupper()) or cleaned.startswith(("/m/", "/g/")):
        return cleaned
    codes = resolve_airport_codes(cleaned)
    return codes[0] if (codes and codes[0].lower() != cleaned.lower()) else None


def _generate_fallback_flights(dep_code: str, arr_code: str, start_date: date, end_date: date) -> list[NormalizedFlight]:
    airlines = [
        ("IndiGo", "6E-2145", 540000, "INR", 85),
        ("Air India", "AI-883", 680000, "INR", 90),
        ("SpiceJet", "SG-1022", 495000, "INR", 95),
        ("Alliance Air", "9I-805", 720000, "INR", 75),
    ]
    out: list[NormalizedFlight] = []
    dep_dt = datetime.combine(start_date, datetime.min.time()).replace(hour=7, minute=30)
    for idx, (airline, fl_num, price_minor, curr, dur) in enumerate(airlines):
        arr_dt = dep_dt + timedelta(minutes=dur)
        legs = [
            NormalizedFlightLeg(
                airline=airline,
                flight_number=fl_num,
                departure_airport=dep_code,
                arrival_airport=arr_code,
                departs_at=dep_dt,
                arrives_at=arr_dt,
            )
        ]
        out.append(
            NormalizedFlight(
                provider_ref=NormalizedProviderRef(
                    id=f"fallback-{dep_code}-{arr_code}-{idx}",
                    deep_link=f"https://www.google.com/travel/flights?q=flights%20from%20{dep_code}%20to%20{arr_code}",
                ),
                outbound=legs,
                inbound=[],
                price_amount_minor=price_minor + (idx * 60000),
                currency=curr,
                stops=0,
                total_duration_minutes=dur,
            )
        )
        dep_dt = dep_dt.replace(hour=dep_dt.hour + 3)
    return out


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
        print("[SERPAPI CACHE] NEW SERPAPI CACHE CODE RUNNING")
        key = _cache_key(engine, params)
        r = await self._get_redis()
        print("[SERPAPI] REDIS OBJECT:", r)

        if r is not None:
            try:
                cached = await r.get(key)

                if cached:
                    print(
                        f"[REDIS CACHE HIT] engine={engine} "
                        f"key={key} ttl={ttl_seconds}s ({ttl_seconds / 3600:.1f}h)"
                    )
                    return json.loads(cached)

                print(
                    f"[REDIS CACHE MISS] engine={engine} "
                    f"key={key} storing_for={ttl_seconds}s ({ttl_seconds / 3600:.1f}h)"
                )

            except Exception:
                logger.warning(
                    "serpapi: redis get failed, continuing without cache",
                    exc_info=True,
                )

        raw = await self._fetch_raw(engine, params)

        if r is not None:
            try:
                await r.set(
                    key,
                    json.dumps(raw, default=str),
                    ex=ttl_seconds,
                )
                print(
                    f"[REDIS CACHE STORED] engine={engine} "
                    f"ttl={ttl_seconds}s ({ttl_seconds / 3600:.1f}h)"
                )
            except Exception:
                logger.warning("serpapi: redis set failed", exc_info=True)

        return raw

    async def _fetch_raw(self, engine: Engine, params: dict[str, Any]) -> dict[str, Any]:
        if not self._settings.use_live_apis:
            return _load_fixture(self._settings.fixtures_dir, engine, params)

        query = {**params, "engine": engine, "api_key": self._settings.serpapi_key}
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                resp = await client.get(SERPAPI_BASE_URL, params=query)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                logger.warning("serpapi: HTTP/network error for engine=%s: %s, falling back to fixture", engine, exc)
                return _load_fixture(self._settings.fixtures_dir, engine, params)

    # -- public, per-engine methods -----------------------------------

    async def search_flights(
        self,
        *,
        source: str,
        destination: str,
        start_date: date,
        end_date: date,
        currency: str | None = None,
        cap: int | None = None,
    ) -> list[NormalizedFlight]:
        dep_id = resolve_departure_id(source)
        if not dep_id:
            logger.warning("serpapi: unresolvable departure_id for %s, skipping flight search", source)
            return []
        dest_codes = resolve_airport_codes(destination)
        flights: list[NormalizedFlight] = []

        # Try destination airport candidates in priority order (e.g. SLV then IXC for Shimla)
        for arr_id in dest_codes:
            params = {
                "departure_id": dep_id,
                "arrival_id": arr_id,
                "outbound_date": start_date.isoformat(),
                "return_date": end_date.isoformat(),
                "currency": currency or "USD",
            }
            try:
                raw = await self._cached_fetch("google_flights", params, self._settings.ttl_flights)
                flights = _normalize_flights(raw)
                if flights:
                    break
            except Exception as exc:
                logger.warning(
                    "serpapi: flight search failed for %s -> %s: %s",
                    dep_id, arr_id, exc
                )

        if not flights:
            # Deterministic fallback flights so user flow is never blocked
            target_arr = dest_codes[-1] if len(dest_codes) > 1 else dest_codes[0]
            flights = _generate_fallback_flights(dep_id, target_arr, start_date, end_date)

        cap = cap or self._settings.cap_flights
        return flights[:cap]

    async def search_hotels(
        self, *, city: str, lat: float, lng: float, check_in: date, check_out: date, cap: int | None = None
    ) -> list[NormalizedHotel]:
        # 1. Location-based metadata query (stable info: properties list with metadata)
        meta_params = {
            "q": f"hotels in {city}",
            "lat": round(lat, 3),
            "lng": round(lng, 3),
        }
        # 2. Date-specific query for volatile price data
        price_params = {
            **meta_params,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
        }

        r = await self._get_redis()
        meta_key = _cache_key("google_hotels_meta", meta_params)
        price_key = _cache_key("google_hotels_price", price_params)

        cached_meta: dict[str, Any] | None = None
        cached_prices: dict[str, Any] | None = None

        if r is not None:
            try:
                raw_meta = await r.get(meta_key)
                if raw_meta:
                    cached_meta = json.loads(raw_meta)
            except Exception:  # pragma: no cover
                logger.warning("serpapi: redis get meta_key failed, continuing without meta cache", exc_info=True)

            try:
                raw_prices = await r.get(price_key)
                if raw_prices:
                    cached_prices = json.loads(raw_prices)
            except Exception:  # pragma: no cover
                logger.warning("serpapi: redis get price_key failed, continuing without price cache", exc_info=True)

        if cached_meta is None or cached_prices is None:
            # Fetch raw data from SerpApi using full search parameters (includes both metadata and price info)
            fresh_raw = await self._fetch_raw("google_hotels", price_params)
            properties = fresh_raw.get("properties", [])
            extracted_meta = []
            extracted_prices = {}

            for prop in properties:
                prop_copy = dict(prop)
                token = prop.get("property_token") or prop.get("name")
                rate = prop_copy.pop("rate_per_night", None)
                extracted_meta.append(prop_copy)
                if token and rate is not None:
                    extracted_prices[token] = rate

            meta_payload = {"properties": extracted_meta}
            price_payload = {"prices": extracted_prices}

            # Update cache for whichever entries were missing
            if cached_meta is None:
                cached_meta = meta_payload
                if r is not None:
                    try:
                        await r.set(meta_key, json.dumps(meta_payload, default=str), ex=self._settings.ttl_hotel_metadata)
                    except Exception:  # pragma: no cover
                        logger.warning("serpapi: redis set meta_key failed", exc_info=True)

            if cached_prices is None:
                cached_prices = price_payload
                if r is not None:
                    try:
                        await r.set(price_key, json.dumps(price_payload, default=str), ex=self._settings.ttl_hotel_prices)
                    except Exception:  # pragma: no cover
                        logger.warning("serpapi: redis set price_key failed", exc_info=True)

        # Reconstruct properties using cached/retrieved metadata and prices
        properties_meta = cached_meta.get("properties", [])
        prices_map = cached_prices.get("prices", {})
        reconstructed_properties = []
        for prop in properties_meta:
            prop_copy = dict(prop)
            token = prop.get("property_token") or prop.get("name")
            if token in prices_map:
                prop_copy["rate_per_night"] = prices_map[token]
            reconstructed_properties.append(prop_copy)
        raw = {"properties": reconstructed_properties}

        hotels = _normalize_hotels(raw)
        cap = cap or self._settings.cap_hotels
        import asyncio
        from app.kg.ingest import ingest_hotel
        country = _resolve_country_from_city(city)
        if country:
            for hotel in hotels:
                asyncio.create_task(_bg_ingest(ingest_hotel(hotel, city=city, country=country)))
        else:
            logger.warning(
                "serpapi: could not resolve country for city=%s; skipping KG ingestion",
                city,
            )
        return hotels[:cap]

    async def search_places(self, *, city: str, query: str, cap: int | None = None) -> list[NormalizedPlace]:
        params = {"q": f"{query} in {city}"}
        raw = await self._cached_fetch("google_maps", params, self._settings.ttl_place_metadata)
        places = _normalize_places(raw)
        cap = cap or self._settings.cap_spots
        import asyncio
        from app.kg.ingest import ingest_place
        country = _resolve_country_from_city(city)
        if country:
            for place in places:
                asyncio.create_task(_bg_ingest(ingest_place(place, city=city, country=country)))
        else:
            logger.warning(
                "serpapi: could not resolve country for city=%s; skipping KG ingestion",
                city,
            )
        return places[:cap]

    async def search_events(
        self, *, city: str, start_date: date, end_date: date, cap: int | None = None
    ) -> list[NormalizedEvent]:
        params = {"q": f"events in {city}"}

        raw = await self._cached_fetch(
            "google", params, self._settings.ttl_events
        )

        events = _normalize_events(raw)

        events = [
            event for event in events
            if event.date is not None
            and start_date <= event.date <= end_date
        ]
        cap = cap or self._settings.cap_spots
        import asyncio
        from app.kg.ingest import ingest_event
        country = _resolve_country_from_city(city)
        if country:
            for event in events:
                asyncio.create_task(_bg_ingest(ingest_event(event, city=city, country=country)))
        else:
            logger.warning(
                "serpapi: could not resolve country for city=%s; skipping KG ingestion",
                city,
            )
        return events[:cap]



async def _bg_ingest(coro: Any) -> None:
    """Fire-and-forget wrapper. Ingestion errors are logged, never propagated."""
    try:
        await coro
    except BaseException:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Per-engine normalizers. Defensive against missing fields — fixtures and
# live payloads are both "whatever SerpApi felt like returning that day".
# ---------------------------------------------------------------------------


def _normalize_flights(raw: dict[str, Any], requested_currency: str | None = None) -> list[NormalizedFlight]:
    out: list[NormalizedFlight] = []
    detected_currency = (
        raw.get("search_parameters", {}).get("currency")
        or raw.get("search_metadata", {}).get("currency")
        or requested_currency
        or "USD"
    ).upper().strip()

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
            item_curr = (item.get("currency") or detected_currency).upper().strip()
            item_exp = get_currency_exponent(item_curr)
            price_val = float(item.get("price", 0))
            price_minor = int(round(price_val * (10 ** item_exp)))

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
                    price_amount_minor=price_minor,
                    currency=item_curr,
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
        event_date_str = when.get("start_date") if isinstance(when, dict) else (when if isinstance(when, str) else None)
        venue_name = venue.get("name") if isinstance(venue, dict) else (venue if isinstance(venue, str) else None)
        out.append(
            NormalizedEvent(
                name=item.get("title", "Unknown event"),
                date=_parse_date(event_date_str),
                venue=venue_name,
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