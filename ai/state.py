"""
Shared state schema for the trip planning LangGraph.

TripState is the single object threaded through every node. It is split
into three areas on purpose:

1. collected inputs   - what the user has told us / selected so far
2. working data        - what we've fetched from SerpApi / the knowledge graph
3. turn_response       - the outward-facing contract. Every node writes into
   this before handing control back, so no matter which node ran, the
   frontend (once it exists) always receives the same shape: a reply to
   show, what UI component to render, the structured options behind it,
   and whether the turn is waiting on the user. This is the piece that
   makes wrapping all of this in an API later a thin layer instead of a
   redesign.
"""

from __future__ import annotations
from typing import TypedDict, Literal, Optional
from typing_extensions import NotRequired


class Coordinates(TypedDict):
    lat: float
    lon: float


class AttractionOption(TypedDict):
    place_id: str
    name: str
    lat: float
    lon: float
    rating: NotRequired[float]
    review_count: NotRequired[int]
    price_tier: NotRequired[str]
    category: NotRequired[str]
    thumbnail: NotRequired[str]
    best_time_hint: NotRequired[str]
    hours: NotRequired[str]              # e.g. "Today: 10:00 AM - 8:00 PM" - real, from google_maps
    operating_hours: NotRequired[dict]    # full weekly schedule, if returned
    extensions: NotRequired[list]         # raw highlights (e.g. "Wheelchair accessible entrance") -
                                            # unfiltered, see tools/serpapi_client.py's normalizer comment
    verified: bool
    source: Literal["cache", "live"]      # where the DATA came from
    verified_by: NotRequired[list]        # which provider(s) confirmed it exists -
                                            # "google_maps" and/or "tripadvisor" (fallback)


class HotelOption(TypedDict):
    place_id: str
    name: str
    lat: float
    lon: float
    rate_per_night: NotRequired[float]
    currency: NotRequired[str]
    star_rating: NotRequired[float]
    amenities: NotRequired[list]
    distance_km_from_cluster: NotRequired[float]
    thumbnail: NotRequired[str]
    price_is_fresh: NotRequired[bool]


class FlightOption(TypedDict):
    is_best: bool
    price: NotRequired[float]
    total_duration_minutes: NotRequired[int]
    departure_airport: NotRequired[str]
    departure_time: NotRequired[str]
    arrival_airport: NotRequired[str]
    arrival_time: NotRequired[str]
    airline: NotRequired[str]
    number_of_stops: NotRequired[int]
    often_delayed: NotRequired[bool]      # historical statistic, NOT live flight status -
                                            # SerpApi has no live tracking, see AGENT.md
    typical_price_range: NotRequired[list]
    price_level: NotRequired[str]
    departure_token: NotRequired[str]


class DayPlan(TypedDict):
    day: int
    stops: list  # list of {place_id, name, notes, travel_minutes_from_previous}


class TurnResponse(TypedDict):
    reply: str
    stage: str
    ui_component: Literal[
        "text", "destination_options", "attraction_options",
        "hotel_options", "flight_options", "itinerary", "nearby_options", "error",
    ]
    options: list
    requires_user_input: bool
    input_type: Literal["free_text", "select_one", "select_multi", "confirm", "none"]


class TripState(TypedDict):
    # conversation bookkeeping
    session_id: str
    user_id: Optional[str]
    conversation_stage: Literal[
        "start", "collecting_departure", "collecting_destination", "collecting_attractions",
        "collecting_hotel", "itinerary_ready", "trip_active",
        "collecting_flight_departure", "collecting_flight_date",
    ]
    last_user_message: str

    # collected inputs
    destination_city: Optional[str]
    departure_city: Optional[str]  # needed by services.fetch_destination_recommendations
    vibe: Optional[str]
    budget_total: Optional[float]
    duration_days: Optional[int]
    currency: str

    # working data
    destination_candidates: list
    attraction_candidates: list
    confirmed_attractions: list
    hotel_candidates: list
    confirmed_hotel: Optional[dict]
    itinerary: list
    flight_candidates: list          # FlightOption list - populated on demand via the
                                       # find_flight adjustment, not part of the main pipeline
    confirmed_flight: Optional[dict]

    # in-trip
    user_location: Optional[Coordinates]
    free_minutes: Optional[int]

    # outward contract
    turn_response: TurnResponse