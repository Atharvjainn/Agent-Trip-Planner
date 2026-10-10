"""
Reusable search+cache+rank capabilities. This is the piece that makes
the same underlying operation ("find attractions in this city",
"find hotels near this cluster") usable both during initial planning
(nodes/attractions.py, nodes/hotels.py) and for a mid-trip or pre-trip
change (nodes/adjust.py) - the cache-first + rank logic exists exactly
once, and every caller can exclude place_ids it doesn't want repeated
(already visited, already rejected).
"""
from __future__ import annotations
from datetime import date, timedelta

import config
from graphdb import repository as repo
from tools import serpapi_client
from tools.geo import haversine_km


def fetch_attraction_candidates(city: str, exclude_place_ids: set | None = None,
                                 limit: int = config.MAX_ATTRACTIONS_SHOWN) -> list:
    exclude_place_ids = exclude_place_ids or set()
    cached = repo.get_cached_attractions(city, limit=limit + len(exclude_place_ids))
    if cached:
        candidates = [dict(c, source="cache", verified=True) for c in cached]
    else:
        live = serpapi_client.search_attractions(f"tourist attractions in {city}")
        for place in live:
            place["source"], place["verified"] = "live", True
        repo.write_attractions(city, live)
        candidates = live

    filtered = [c for c in candidates if c.get("place_id") not in exclude_place_ids]
    return filtered[:limit]


def fetch_hotel_candidates(city: str, lat: float, lon: float, budget_total: float | None = None,
                            nights: int | None = None, exclude_place_ids: set | None = None,
                            currency: str = "USD", limit: int = config.MAX_HOTELS_SHOWN) -> list:
    exclude_place_ids = exclude_place_ids or set()
    nights = nights or config.DEFAULT_TRIP_DURATION_DAYS

    # KNOWN LIMITATION, flagged rather than silently wrong: the cache
    # doesn't key on currency at all (graphdb/repository.py stores one
    # rate per hotel, not one per currency). A hotel cached by an
    # earlier USD search and read here by an INR search will show a USD
    # number under an "INR" label until confirm_hotel_node's
    # refresh_hotel_price call corrects it for the specific hotel the
    # user actually picks - the same "estimate now, refreshed before you
    # commit" pattern already used for price staleness, just not yet
    # extended to currency. A real fix needs the cache keyed by
    # (city, currency), not attempted here.
    cached = repo.get_cached_hotels(city, limit=limit + len(exclude_place_ids))
    if cached:
        candidates = cached
    else:
        check_in = date.today().isoformat()
        check_out = (date.today() + timedelta(days=nights)).isoformat()
        candidates = serpapi_client.search_hotels(city, check_in, check_out, lat, lon, currency=currency)
        repo.write_hotels(city, candidates)

    for hotel in candidates:
        hotel["distance_km_from_cluster"] = haversine_km(lat, lon, hotel["lat"], hotel["lon"])

    if budget_total:
        per_night_cap = budget_total * config.HOTEL_BUDGET_FRACTION / nights
        within_budget = [
            h for h in candidates
            if not h.get("rate_per_night") or h["rate_per_night"] <= per_night_cap
        ]
        # If the budget cap filters everything out (e.g. all SerpApi results are
        # above cap) show the full set anyway — the caller's reply context can
        # note they're over budget; showing nothing is strictly worse.
        candidates = within_budget if within_budget else candidates

    filtered = [h for h in candidates if h.get("place_id") not in exclude_place_ids]
    return sorted(filtered, key=lambda h: h["distance_km_from_cluster"])[:limit]


def fetch_departure_airport_options(location_text: str) -> list:
    """
    Thin wrapper around serpapi_client.resolve_airport_options to fetch
    real airport options for a departure location string.
    """
    return serpapi_client.resolve_airport_options(location_text)


def fetch_destination_recommendations(departure_city: str, interest: str | None = None,
                                       currency: str = "USD", limit: int = 4) -> list | None:
    """
    Real destination recommendations via Google Travel Explore - never a
    static list. Returns None specifically (not []) when departure_city
    couldn't be resolved to a real airport/location, so the caller can
    tell "no good matches" apart from "we don't know where you're
    flying from" and ask again instead of silently showing nothing.
    Deliberately not cached in the knowledge graph: unlike city
    attractions, this result is departure-point- and price-dependent,
    so it's far less reusable across different users than
    fetch_attraction_candidates is.
    """
    departure_id = serpapi_client.resolve_departure_id(departure_city)
    if not departure_id:
        return None
    return serpapi_client.search_explore_destinations(
        departure_id, interest=interest, currency=currency, limit=limit
    )


def fetch_flight_options(departure_city: str, arrival_city: str, outbound_date: str,
                          return_date: str | None = None, currency: str = "USD") -> list | None:
    """
    Real, bookable flights - not Explore's rough estimate. Returns None
    (not []) when either city couldn't be resolved to a real
    airport/location, same distinction fetch_destination_recommendations
    makes, for the same reason. Not cached, for the same reason Explore
    results aren't: price- and date-specific, poor reuse across users.
    """
    departure_id = serpapi_client.resolve_departure_id(departure_city)
    arrival_id = serpapi_client.resolve_departure_id(arrival_city)  # same resolution logic either direction
    if not departure_id or not arrival_id:
        return None
    raw_flights = serpapi_client.search_flights(
        departure_id, arrival_id, outbound_date, return_date=return_date, currency=currency
    )
    if not raw_flights:
        return raw_flights

    expected_arrival_airports = serpapi_client.resolve_valid_airport_codes(arrival_city)
    expected_departure_airports = serpapi_client.resolve_valid_airport_codes(departure_city)

    filtered_flights = []
    for flight in raw_flights:
        arr_apt = flight.get("arrival_airport")
        dep_apt = flight.get("departure_airport")
        if expected_arrival_airports and arr_apt and arr_apt not in expected_arrival_airports:
            continue
        if expected_departure_airports and dep_apt and dep_apt not in expected_departure_airports:
            continue
        filtered_flights.append(flight)

    return filtered_flights


def attach_travel_times(day_plans: list) -> list:
    """
    Called AFTER tools.geo.cluster_by_day has already decided grouping
    and order by straight-line distance - this attaches a real
    Directions-based travel time to each stop from the one before it,
    one call per consecutive pair, not during the clustering search
    itself (see get_directions' docstring for why that split matters).
    Mutates and returns day_plans; a stop with no coordinates on either
    side (e.g. a Tripadvisor-fallback-only verified place) is left
    without a travel time rather than guessed.
    """
    for day in day_plans:
        stops = day.get("stops", [])
        for i in range(1, len(stops)):
            prev, curr = stops[i - 1], stops[i]
            if None in (prev.get("lat"), prev.get("lon"), curr.get("lat"), curr.get("lon")):
                continue
            route = serpapi_client.get_directions(prev["lat"], prev["lon"], curr["lat"], curr["lon"])
            curr["travel_minutes_from_previous"] = route.get("duration_minutes") if route else None
    return day_plans


def fetch_events(city: str) -> list:
    return serpapi_client.search_events(city)


def fetch_nearby(lat: float, lon: float, category_query: str, radius_minutes: int,
                  exclude_place_ids: set | None = None, limit: int = 5) -> list:
    exclude_place_ids = exclude_place_ids or set()
    results = serpapi_client.search_nearby(lat, lon, category_query, radius_minutes)
    return [r for r in results if r.get("place_id") not in exclude_place_ids][:limit]