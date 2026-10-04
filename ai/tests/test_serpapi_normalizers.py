import json
from pathlib import Path

import pytest

from app.tools.serpapi import (
    _normalize_events,
    _normalize_flights,
    _normalize_hotels,
    _normalize_places,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "serpapi"


def _load(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def test_normalize_flights_sorts_by_price_and_keeps_deep_links():
    raw = _load("google_flights_sample.json")
    flights = _normalize_flights(raw)
    assert len(flights) == 3
    prices = [f.price_amount_minor for f in flights]
    assert prices == sorted(prices)
    assert flights[0].price_amount_minor == 410_00  # "Budget Wings" at $410 -> cheapest
    assert all(f.provider_ref.deep_link for f in flights)
    assert all(f.currency == "USD" for f in flights)


def test_normalize_flights_computes_stops_from_leg_count():
    raw = _load("google_flights_sample.json")
    flights = _normalize_flights(raw)
    by_price = {f.price_amount_minor: f for f in flights}
    one_leg = by_price[612_00]
    two_leg = by_price[548_00]
    assert one_leg.stops == 0
    assert two_leg.stops == 1


def test_normalize_hotels_extracts_coordinates_and_review_snippet():
    raw = _load("google_hotels_sample.json")
    hotels = _normalize_hotels(raw)
    assert len(hotels) == 3
    names = {h.name for h in hotels}
    assert {"Hotel Riverside", "Boutique Stay Central", "Grand Palace Hotel"} <= names
    riverside = next(h for h in hotels if h.name == "Hotel Riverside")
    assert riverside.lat == pytest.approx(48.8566)
    assert riverside.price_per_night_amount_minor == 142_00
    assert riverside.review_snippet is not None


def test_normalize_hotels_skips_items_without_coordinates():
    raw = {"properties": [{"name": "No GPS Hotel", "rate_per_night": {"extracted_lowest": 50}}]}
    hotels = _normalize_hotels(raw)
    assert hotels == []


def test_normalize_places_extracts_types_for_vibe_tagging():
    raw = _load("google_maps_sample.json")
    places = _normalize_places(raw)
    assert len(places) == 5
    bar = next(p for p in places if "Sunset" in p.name)
    assert "nightlife" in bar.types


def test_normalize_events_parses_short_dates():
    raw = _load("google_events_sample.json")
    events = _normalize_events(raw)
    assert len(events) == 2
    assert events[0].venue == "Riverside Market"
    assert events[0].date is not None
    assert events[0].date.month == 11
    assert events[0].date.day == 12


def test_normalize_handles_empty_payload_gracefully():
    assert _normalize_flights({}) == []
    assert _normalize_hotels({}) == []
    assert _normalize_places({}) == []
    assert _normalize_events({}) == []


@pytest.mark.asyncio
async def test_search_hotels_cache_separation(monkeypatch):
    from datetime import date
    from app.tools.serpapi import SerpApiClient

    client = SerpApiClient()

    # Fake Redis in-memory storage with TTL support tracking
    storage: dict[str, str] = {}
    ttls: dict[str, int] = {}

    class FakeRedis:
        async def get(self, key: str):
            return storage.get(key)

        async def set(self, key: str, value: str, ex: int = None):
            storage[key] = value
            if ex:
                ttls[key] = ex

    fake_redis = FakeRedis()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(client, "_get_redis", fake_get_redis)

    check_in = date(2026, 11, 1)
    check_out = date(2026, 11, 5)

    # First call: populates cache
    hotels1 = await client.search_hotels(
        city="Paris", lat=48.8566, lng=2.3522, check_in=check_in, check_out=check_out
    )
    assert len(hotels1) > 0

    # Verify separate keys with correct TTLs were populated
    meta_keys = [k for k in storage if k.startswith("serpapi:google_hotels_meta:")]
    price_keys = [k for k in storage if k.startswith("serpapi:google_hotels_price:")]
    assert len(meta_keys) == 1
    assert len(price_keys) == 1

    assert ttls[meta_keys[0]] == client._settings.ttl_hotel_metadata
    assert ttls[price_keys[0]] == client._settings.ttl_hotel_prices

    # Second call with price cache expired: metadata cache hit, fetches fresh price data, updates price cache
    fetch_raw_calls = 0
    original_fetch_raw = client._fetch_raw

    async def counting_fetch_raw(*args, **kwargs):
        nonlocal fetch_raw_calls
        fetch_raw_calls += 1
        return await original_fetch_raw(*args, **kwargs)

    monkeypatch.setattr(client, "_fetch_raw", counting_fetch_raw)

    hotels2 = await client.search_hotels(
        city="Paris", lat=48.8566, lng=2.3522, check_in=check_in, check_out=check_out
    )
    assert len(hotels2) == len(hotels1)
    assert hotels2[0].name == hotels1[0].name
    assert fetch_raw_calls == 1
    assert price_keys[0] in storage  # price cache re-populated

    # Third call with metadata cache expired but price cache hit: metadata re-fetched/re-populated
    del storage[meta_keys[0]]
    fetch_raw_calls = 0

    hotels3 = await client.search_hotels(
        city="Paris", lat=48.8566, lng=2.3522, check_in=check_in, check_out=check_out
    )
    assert len(hotels3) == len(hotels1)
    assert hotels3[0].name == hotels1[0].name
    assert fetch_raw_calls == 1
    assert meta_keys[0] in storage  # metadata cache re-populated

