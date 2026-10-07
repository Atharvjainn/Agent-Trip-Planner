"""
Thin wrapper around SerpApi. This is the only module that should import
serpapi directly - nodes call these functions, never SerpApi's client
directly, so caching/rate-limiting stays in one place.

Confidence level per engine, from research, not assumed uniform:
- google_maps, google_hotels: field names confirmed against SerpApi's
  own docs/examples (gps_coordinates, rating, reviews, price, type,
  thumbnail, hours, operating_hours, extensions; rate_per_night,
  check_in_time, amenities).
- google_travel_explore, google_flights_autocomplete: fully confirmed,
  including a full worked JSON example, during this project's research.
- google_flights, google_events, tripadvisor: request parameters
  confirmed; response field names below are assembled from documented
  field lists and blog examples, not one complete worked JSON example
  the way Explore got. Treat parsing in _normalize_flight/_normalize_event
  as best-effort until checked against a live sandbox call.
- google_maps_directions: request parameters confirmed (start_coords/
  end_coords/travel_mode etc.); the exact response JSON shape was not
  shown in research at all - _normalize_route below is a guess built
  from the terminology SerpApi's own blog post used ("distance",
  "duration"), not a confirmed schema. Verify before relying on it.

Re-check anything above against a live sandbox response before
depending on it in production - SerpApi's exact fields can vary
slightly by place/property type and do drift between updates.
"""
from serpapi import GoogleSearch
from app import config
settings = config.get_settings()
# ---------------------------------------------------------------- places --

def search_attractions(query: str, lat: float | None = None, lon: float | None = None,
                        zoom: str = "13z") -> list:
    params = {
        "engine": "google_maps",
        "q": query,
        "type": "search",
        "api_key": settings.serpapi_key,
    }
    if lat is not None and lon is not None:
        params["ll"] = f"@{lat},{lon},{zoom}"
    results = GoogleSearch(params).get_dict()
    places = results.get("local_results") or results.get("place_results") or []
    if isinstance(places, dict):
        places = [places]
    elif not isinstance(places, list):
        places = []
    return [_normalize_place(p) for p in places if isinstance(p, dict)]


def search_nearby(lat: float, lon: float, category: str, radius_minutes: int) -> list:
    """Used by the in-trip node. `category` is a Maps query like 'park'
    or 'museum'; radius is approximated by zoom level since SerpApi
    doesn't expose a hard distance filter on this engine."""
    zoom = "15z" if radius_minutes <= 20 else "13z"
    return search_attractions(category, lat, lon, zoom=zoom)


def search_tripadvisor(query: str) -> list:
    """Independent second source for grounding a place. Used as a
    FALLBACK in nodes/verify.py - only tried when Google Maps has no
    match - rather than a cross-check on every lookup, to keep this at
    one extra call on the rare miss instead of doubling every
    verification call."""
    params = {"engine": "tripadvisor", "q": query, "api_key": settings.serpapi_key}
    results = GoogleSearch(params).get_dict()
    return [_normalize_tripadvisor_place(loc) for loc in results.get("locations", [])]


# ---------------------------------------------------------------- hotels --

def search_hotels(city: str, check_in: str, check_out: str, lat: float, lon: float,
                   currency: str = "USD") -> list:
    params = {
        "engine": "google_hotels",
        "q": f"hotels in {city}",
        "check_in_date": check_in,
        "check_out_date": check_out,
        "ll": f"@{lat},{lon},13z",
        "currency": currency,  # NOTE: confirmed for google_travel_explore; not
                                 # explicitly confirmed for google_hotels during
                                 # research - verify against a live call.
        "api_key": settings.serpapi_key,
    }
    results = GoogleSearch(params).get_dict()
    return [_normalize_hotel(h, currency) for h in results.get("properties", [])]


def refresh_hotel_price(property_token: str, check_in: str, check_out: str,
                         currency: str = "USD") -> dict | None:
    """Called only for the specific hotel a user is about to see a price
    for - avoids re-searching a whole city just to update one rate."""
    params = {
        "engine": "google_hotels",
        "property_token": property_token,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "currency": currency,
        "api_key": settings.serpapi_key,
    }
    results = GoogleSearch(params).get_dict()
    props = results.get("properties", [])
    return _normalize_hotel(props[0], currency) if props else None


# ------------------------------------------------------------- flights --

def search_flight_autocomplete(query: str) -> list:
    """Resolves free-text like 'Mumbai' into Google Travel's location
    IDs and airport codes - departure_id (Explore, Flights) can't take
    arbitrary city text directly, this is what makes it able to."""
    params = {"engine": "google_flights_autocomplete", "q": query, "api_key": settings.serpapi_key}
    results = GoogleSearch(params).get_dict()
    return results.get("suggestions", [])


def _get_best_autocomplete_match(suggestions: list, query_text: str) -> dict | None:
    if not suggestions:
        return None
    q_lower = query_text.strip().lower()
    for item in suggestions:
        name_lower = (item.get("name") or "").lower()
        if item.get("type") == "city" and (q_lower in name_lower or name_lower in q_lower):
            return item
    for item in suggestions:
        if item.get("type") == "city":
            return item
    return suggestions[0]


def resolve_valid_airport_codes(location_text: str) -> set:
    if len(location_text) == 3 and location_text.isupper():
        return {location_text}
    suggestions = search_flight_autocomplete(location_text)
    if not suggestions:
        return set()
    best = _get_best_autocomplete_match(suggestions, location_text)
    codes = set()
    if best:
        for apt in best.get("airports", []) or []:
            if apt.get("id"):
                codes.add(apt["id"])
            if apt.get("code"):
                codes.add(apt["code"])
        best_id = best.get("id", "")
        if len(best_id) == 3 and best_id.isupper():
            codes.add(best_id)
    return codes


def resolve_departure_id(city_text: str) -> str | None:
    """Prefers the city-level location id (covers every airport serving
    that city) over one specific airport. Returns None - not a guess -
    if nothing matches, so the caller can ask the user to clarify."""
    if len(city_text) == 3 and city_text.isupper():
        return city_text  # already an IATA airport code
    suggestions = search_flight_autocomplete(city_text)
    if not suggestions:
        return None
    top = _get_best_autocomplete_match(suggestions, city_text)
    if not top:
        return None
    if top.get("id"):
        return top["id"]
    airports = top.get("airports") or []
    return airports[0]["id"] if airports else None


def resolve_airport_options(location_text: str) -> list:
    """Resolves location text into real airport options via Google Flights
    autocomplete. If location_text is already a 3-letter IATA code, returns
    it directly."""
    if len(location_text) == 3 and location_text.isupper():
        return [{"id": location_text, "name": location_text, "code": location_text}]

    suggestions = search_flight_autocomplete(location_text)
    if not suggestions:
        return []

    options = []
    seen_ids = set()

    for item in suggestions:
        airports = item.get("airports") or []
        for apt in airports:
            apt_id = apt.get("id") or apt.get("code")
            apt_name = apt.get("title") or apt.get("name") or apt_id
            if apt_id and apt_id not in seen_ids:
                seen_ids.add(apt_id)
                options.append({
                    "id": apt_id,
                    "name": f"{apt_id} - {apt_name}" if apt_name and not str(apt_name).startswith(apt_id) else (apt_name or apt_id),
                    "code": apt_id,
                })

        item_id = item.get("id")
        item_type = str(item.get("type") or "").lower()
        if item_id and item_id not in seen_ids:
            if item_type == "airport" or (len(item_id) == 3 and item_id.isupper()):
                seen_ids.add(item_id)
                item_name = item.get("title") or item.get("name") or item_id
                options.append({
                    "id": item_id,
                    "name": f"{item_id} - {item_name}" if item_name and not str(item_name).startswith(item_id) else (item_name or item_id),
                    "code": item_id,
                })

    return options


def search_explore_destinations(departure_id: str, interest: str | None = None,
                                 currency: str = "USD", limit: int = 4) -> list:
    """Real destination recommendations - names, coordinates, images,
    and live flight/hotel price estimates - via Google Travel Explore.
    Never a static list: this is the only source destination.py uses
    when the user hasn't named a place themselves."""
    params = {
        "engine": "google_travel_explore",
        "departure_id": departure_id,
        "currency": currency,
        "api_key": settings.serpapi_key,
    }
    if interest and interest != "0":
        params["interest"] = interest
    results = GoogleSearch(params).get_dict()
    return [_normalize_destination(d, currency) for d in results.get("destinations", [])[:limit]]


def search_flights(departure_id: str, arrival_id: str, outbound_date: str,
                    return_date: str | None = None, currency: str = "USD") -> list:
    """Real, bookable flight search - unlike Explore's rough per-route
    estimate, this gives actual priced itineraries with times, layovers,
    and airline. Combines best_flights + other_flights into one list,
    each entry tagged with the route's overall price_insights so the
    caller can say whether a given fare is a good deal."""
    params = {
        "engine": "google_flights",
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "currency": currency,
        "api_key": settings.serpapi_key,
    }
    if return_date:
        params["return_date"] = return_date
    else:
        params["type"] = "2"  # one way
    results = GoogleSearch(params).get_dict()
    insights = results.get("price_insights") or {}
    flights = [_normalize_flight(f, is_best=True) for f in results.get("best_flights", []) or []]
    flights += [_normalize_flight(f, is_best=False) for f in results.get("other_flights", []) or []]
    for flight in flights:
        flight["typical_price_range"] = insights.get("typical_price_range")
        flight["price_level"] = insights.get("price_level")
    return flights


# ------------------------------------------------------------- directions --

def get_directions(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float,
                    travel_mode: str = "Best") -> dict | None:
    """Real travel time/distance between two points. Used to attach an
    actual duration to consecutive itinerary stops AFTER
    tools.geo.cluster_by_day has already decided the grouping and order
    by straight-line distance - calling this engine inside the
    clustering search itself would be O(n^2) calls for what's currently
    a free haversine calculation."""
    params = {
        "engine": "google_maps_directions",
        "start_coords": f"{origin_lat},{origin_lon}",
        "end_coords": f"{dest_lat},{dest_lon}",
        "travel_mode": travel_mode,
        "api_key": settings.serpapi_key,
    }
    results = GoogleSearch(params).get_dict()
    return _normalize_route(results)


# ---------------------------------------------------------------- events --

def search_events(city: str, limit: int = settings.cap_events) -> list:
    """Real events (festivals, concerts, exhibitions) at a destination -
    used to enrich the itinerary reply, not to pick a destination.
    Filtering to a specific trip's exact dates wasn't confirmed as
    reliable during research (SerpApi's htichips filter offers
    date:today/date:tomorrow, not an arbitrary date range) - this
    returns whatever Google Events currently lists for the city, which
    in practice skews toward near-term events."""
    params = {"engine": "google_events", "q": f"Events in {city}", "api_key": settings.serpapi_key}
    results = GoogleSearch(params).get_dict()
    return [_normalize_event(e) for e in results.get("events_results", [])[:limit]]


# --------------------------------------------------------------- normalizers --

def _normalize_place(p: dict) -> dict:
    if not isinstance(p, dict):
        return {"name": str(p)}
    coords = p.get("gps_coordinates", {}) if isinstance(p.get("gps_coordinates"), dict) else {}
    place_type = p.get("type")
    return {
        "place_id": p.get("data_id") or p.get("place_id"),
        "name": p.get("title"),
        "lat": coords.get("latitude"),
        "lon": coords.get("longitude"),
        "rating": p.get("rating"),
        "review_count": p.get("reviews"),
        "price_tier": p.get("price"),
        "category": place_type[0] if isinstance(place_type, list) else place_type,
        "thumbnail": p.get("thumbnail"),
        "hours": p.get("hours"),
        "operating_hours": p.get("operating_hours"),
        # Raw, unfiltered on purpose - keyword-filtering this list for
        # "accessibility-looking" entries would be exactly the kind of
        # hardcoded semantic guessing this project moved away from.
        # llm.build_reply already gets the full context dict and can
        # surface a relevant entry (e.g. "wheelchair accessible") when
        # it's actually relevant, reasoning over the real list rather
        # than a keyword match against it.
        "extensions": p.get("extensions") or [],
    }


def _normalize_destination(d: dict, currency: str) -> dict:
    coords = d.get("gps_coordinates", {})
    return {
        "place_id": d.get("destination_id"),
        "name": d.get("name"),
        "country": d.get("country"),
        "lat": coords.get("latitude"),
        "lon": coords.get("longitude"),
        "thumbnail": d.get("thumbnail"),
        "flight_price": d.get("flight_price"),
        "hotel_price": d.get("hotel_price"),
        "currency": currency,
        "start_date": d.get("start_date"),
        "end_date": d.get("end_date"),
    }


def _normalize_hotel(h: dict, currency: str) -> dict:
    coords = h.get("gps_coordinates", {})
    rate = h.get("rate_per_night") or {}
    images = h.get("images") or []
    return {
        "place_id": h.get("property_token"),
        "name": h.get("name"),
        "lat": coords.get("latitude"),
        "lon": coords.get("longitude"),
        "rate_per_night": rate.get("extracted_lowest"),
        "currency": currency,
        "star_rating": h.get("extracted_hotel_class"),
        "amenities": h.get("amenities", []),
        "thumbnail": images[0].get("thumbnail") if images else None,
        "check_in_time": h.get("check_in_time"),
        "check_out_time": h.get("check_out_time"),
    }


def _normalize_flight(f: dict, is_best: bool) -> dict:
    legs = f.get("flights") or []
    first_leg = legs[0] if legs else {}
    last_leg = legs[-1] if legs else {}
    return {
        "is_best": is_best,
        "price": f.get("price"),
        "total_duration_minutes": f.get("total_duration"),
        "departure_airport": (first_leg.get("departure_airport") or {}).get("id"),
        "departure_time": (first_leg.get("departure_airport") or {}).get("time"),
        "arrival_airport": (last_leg.get("arrival_airport") or {}).get("id"),
        "arrival_time": (last_leg.get("arrival_airport") or {}).get("time"),
        "airline": first_leg.get("airline"),
        "number_of_stops": max(len(legs) - 1, 0),
        # Best-effort: seen in one documented example without full
        # surrounding context on which level of the response carries it.
        "often_delayed": first_leg.get("often_delayed_by_over_30_min", False),
        "departure_token": f.get("departure_token"),  # needed to fetch return leg of a round trip
    }


def _normalize_route(results: dict) -> dict | None:
    """Best-effort - see module docstring. Tries a couple of plausible
    top-level shapes; returns None rather than a wrong guess if neither
    matches, so callers can tell 'no route data' apart from 'this route
    is 0 minutes'."""
    routes = results.get("routes") or results.get("directions") or []
    if not routes:
        return None
    route = routes[0]
    distance = route.get("distance")
    duration = route.get("duration")
    return {
        "distance_text": distance.get("text") if isinstance(distance, dict) else distance,
        "duration_minutes": duration.get("value") if isinstance(duration, dict) else None,
        "duration_text": duration.get("text") if isinstance(duration, dict) else duration,
    }


def _normalize_event(e: dict) -> dict:
    date_info = e.get("date") or {}
    venue = e.get("venue") or {}
    return {
        "title": e.get("title"),
        "when": date_info.get("when") or date_info.get("start_date"),
        "venue": venue.get("name"),
        "thumbnail": e.get("thumbnail"),
        "link": e.get("link"),
    }


def _normalize_tripadvisor_place(loc: dict) -> dict:
    return {
        "place_id": loc.get("place_id") or loc.get("location_id"),
        "name": loc.get("title"),
        "rating": loc.get("rating"),
        "review_count": loc.get("reviews"),
        "description": loc.get("description"),
        "thumbnail": loc.get("thumbnail"),
        # Tripadvisor's confirmed Search API fields (title, description,
        # rating, reviews, location, thumbnail, highlighted_overview)
        # don't reliably include coordinates the way Maps does - left
        # unset rather than guessed. A place grounded only via this
        # fallback can be shown to the user but can't be used for
        # distance-based clustering.
        "lat": None,
        "lon": None,
    }