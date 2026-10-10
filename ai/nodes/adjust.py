"""
Handles every "something about the plan needs to change" case - a
weather delay, a longer stay than planned, an itinerary that isn't
working out, or a hotel the user wants swapped. These are the same
underlying operations whether they happen before departure or mid-trip,
so they aren't split by conversation_stage - only by *what kind* of
change is needed (llm.classify_adjustment_type), which reasons over the
full trip context rather than the raw message alone.

Each handler calls the same services.* functions the initial planning
nodes use, with exclude_place_ids set so a "find something else" never
re-surfaces something already visited or already rejected.
"""
import config
import llm
import services
from tools import weather as weather_tool
from tools.geo import centroid
from nodes.verify import verify_and_enrich
from state import TripState

NEARBY_CATEGORY_QUERY = {
    "nature": "park OR natural attraction",
    "food": "cheap eats OR street food",
    "culture": "museum OR gallery",
    "shopping": "local market OR shopping street",
}


def adjust_node(state: TripState) -> TripState:
    # When a handler needs a follow-up answer (a bare city name, a bare
    # date) that alone wouldn't reliably re-classify to the right
    # adjustment, it sets one of these stages instead of leaving
    # classification to guess from an ambiguous fragment on the next
    # turn - checked BEFORE calling llm.classify_adjustment_type, the
    # same way graph.py's continue_flow routes "collecting_hotel"
    # straight to confirm_hotel_node rather than re-deriving intent from
    # a bare selection. Built here, not at module level, so it can
    # reference _handle_find_flight directly - that function is defined
    # further down this file, after this one.
    stage_shortcuts = {
        "collecting_flight_departure": _handle_find_flight,
        "collecting_flight_date": _handle_find_flight,
    }
    if state["conversation_stage"] in stage_shortcuts:
        return stage_shortcuts[state["conversation_stage"]](state)

    adjustment = llm.classify_adjustment_type(state)
    handler = {
        "nearby_exploration": _handle_nearby_exploration,
        "reschedule_day": _handle_reschedule_day,
        "extend_trip": _handle_extend_trip,
        "replace_itinerary_items": _handle_replace_items,
        "change_hotel": _handle_change_hotel,
        "find_flight": _handle_find_flight,
    }[adjustment]
    return handler(state)


def _handle_nearby_exploration(state: TripState) -> TripState:
    loc = state.get("user_location")
    # T5: if no stored location, try to extract one from this message
    # (e.g. "near Baga Beach" → geocode via SerpApi to lat/lon)
    if not loc:
        slots = llm.extract_trip_slots(state["last_user_message"])
        raw_loc = slots.get("current_location")
        if isinstance(raw_loc, dict) and "lat" in raw_loc and "lon" in raw_loc:
            loc = raw_loc
        elif isinstance(raw_loc, str) and raw_loc:
            match = next((a for a in state.get("confirmed_attractions", []) if raw_loc.lower() in a.get("name", "").lower() or a.get("name", "").lower() in raw_loc.lower()), None)
            if match and "lat" in match and "lon" in match:
                loc = {"lat": match["lat"], "lon": match["lon"], "name": match["name"]}
            elif state.get("confirmed_hotel") and "lat" in state["confirmed_hotel"]:
                loc = {"lat": state["confirmed_hotel"]["lat"], "lon": state["confirmed_hotel"]["lon"]}
            elif state.get("confirmed_attractions") and "lat" in state["confirmed_attractions"][0]:
                loc = {"lat": state["confirmed_attractions"][0]["lat"], "lon": state["confirmed_attractions"][0]["lon"]}
        elif state.get("confirmed_hotel") and "lat" in state["confirmed_hotel"]:
            loc = {"lat": state["confirmed_hotel"]["lat"], "lon": state["confirmed_hotel"]["lon"]}
        elif state.get("confirmed_attractions") and "lat" in state.get("confirmed_attractions", [{}])[0]:
            loc = {"lat": state["confirmed_attractions"][0]["lat"], "lon": state["confirmed_attractions"][0]["lon"]}
        if loc:
            state["user_location"] = loc

    if not loc:
        state["turn_response"] = _ask_free_text(state, llm.build_reply(
            context={}, instruction="Ask the user to share their current location so we can find something nearby."
        ))
        return state

    if not state.get("free_minutes"):
        slots = llm.extract_trip_slots(state["last_user_message"])
        if slots.get("free_minutes"):
            state["free_minutes"] = slots["free_minutes"]
    minutes = state.get("free_minutes") or 60

    weather = weather_tool.current_weather(loc["lat"], loc["lon"])
    category = llm.classify_nearby_category(state["last_user_message"], weather)

    visited = {a["place_id"] for a in state["confirmed_attractions"]}
    results = services.fetch_nearby(
        loc["lat"], loc["lon"], NEARBY_CATEGORY_QUERY[category], minutes, exclude_place_ids=visited
    )
    verified, _ = verify_and_enrich(
        state["destination_city"], [r["name"] for r in results[:5]], loc["lat"], loc["lon"]
    )

    state["turn_response"] = {
        "reply": llm.build_reply(
            context={"weather": weather, "free_minutes": minutes, "options": verified[:4]},
            instruction="Suggest these nearby options, mentioning the weather and time available in one line.",
        ),
        "stage": state["conversation_stage"],
        "ui_component": "nearby_options",
        "options": verified[:4],
        "requires_user_input": True,
        "input_type": "select_one",
    }
    return state


def _handle_reschedule_day(state: TripState) -> TripState:
    """
    A delay/weather pushes a planned day to a different date - the
    places stay the same, so this is itinerary bookkeeping, not a new
    search. NOT FULLY IMPLEMENTED: figuring out *which* day the user
    means (by date, by "today", by activity name) needs its own
    disambiguation step against state["itinerary"], and if the
    postponement pushes past the current hotel's checkout date, the
    hotel needs `serpapi_client.refresh_hotel_price` for the new date
    range. Both are left as a clear next step rather than guessed at -
    the one wrong thing to do here is silently move a day without
    checking whether the hotel booking still covers it.
    """
    slots = llm.extract_trip_slots(state["last_user_message"])
    postpone_days = slots.get("postpone_days")

    state["turn_response"] = _ask_free_text(state, llm.build_reply(
        context={"itinerary": state["itinerary"], "postpone_days": postpone_days},
        instruction="Confirm which day is being moved and to when, since that isn't certain yet.",
    ))
    return state


def _handle_extend_trip(state: TripState) -> TripState:
    slots = llm.extract_trip_slots(state["last_user_message"])
    ext_days = slots.get("duration_days")
    if ext_days and isinstance(ext_days, (int, float)):
        state["duration_days"] = (state.get("duration_days") or 0) + int(ext_days)
    already_seen = {a["place_id"] for a in state["confirmed_attractions"]} | {
        c["place_id"] for c in state["attraction_candidates"]
    }
    extra = services.fetch_attraction_candidates(
        state["destination_city"], exclude_place_ids=already_seen, limit=4
    )
    state["attraction_candidates"] = extra
    state["turn_response"] = {
        "reply": llm.build_reply(
            context={"extra_options": extra},
            instruction="Say we can fill the extra day and present these new options to pick from.",
        ),
        "stage": state["conversation_stage"],
        "ui_component": "attraction_options",
        "options": extra,
        "requires_user_input": True,
        "input_type": "select_multi",
    }
    return state


def _handle_replace_items(state: TripState) -> TripState:
    already_seen = {a["place_id"] for a in state["confirmed_attractions"]} | {
        c["place_id"] for c in state["attraction_candidates"]
    }
    alternatives = services.fetch_attraction_candidates(
        state["destination_city"], exclude_place_ids=already_seen, limit=4
    )
    state["attraction_candidates"] = alternatives
    state["turn_response"] = {
        "reply": llm.build_reply(
            context={"alternatives": alternatives},
            instruction="Say we found different options and ask which of these to swap in.",
        ),
        "stage": state["conversation_stage"],
        "ui_component": "attraction_options",
        "options": alternatives,
        "requires_user_input": True,
        "input_type": "select_multi",
    }
    return state


def _handle_change_hotel(state: TripState) -> TripState:
    slots = llm.extract_trip_slots(state["last_user_message"])
    if slots.get("budget_total"):
        from app.schemas.common import float_to_money_dict
        m_dict = float_to_money_dict(slots["budget_total"], state.get("currency", "INR") or "INR")
        if m_dict:
            state["budget_total"] = m_dict["amountMinor"]

    exclude = {state["confirmed_hotel"]["place_id"]} if state.get("confirmed_hotel") else set()
    attractions = state["confirmed_attractions"]
    if attractions:
        lat, lon = centroid([(a["lat"], a["lon"]) for a in attractions])
    else:
        lat, lon = state["hotel_candidates"][0]["lat"], state["hotel_candidates"][0]["lon"]

    alternatives = services.fetch_hotel_candidates(
        state["destination_city"], lat, lon,
        budget_total=state.get("budget_total"), exclude_place_ids=exclude,
        currency=state["currency"],
    )
    state["hotel_candidates"] = alternatives
    state["confirmed_hotel"] = None
    state["conversation_stage"] = "collecting_hotel"  # T4: so next turn → confirm_hotel_node
    state["turn_response"] = {
        "reply": llm.build_reply(
            context={"hotels": alternatives, "budget_total": state.get("budget_total")},
            instruction="Present these alternative hotels and ask the user to pick one.",
        ),
        "stage": "collecting_hotel",
        "ui_component": "hotel_options",
        "options": alternatives,
        "requires_user_input": True,
        "input_type": "select_one",
    }
    return state


def _handle_find_flight(state: TripState) -> TripState:
    """
    Real, bookable flights via Google Flights - not Explore's rough
    estimate. Deliberately an on-demand adjustment rather than a stage
    in the main planning pipeline (destination -> attractions -> hotel
    -> itinerary): flights weren't part of the original planning flow,
    and Explore already covers the "give me a rough idea" case during
    destination selection. This is for when the user actually wants to
    book, or check, a specific route.
    """
    if not state.get("destination_city"):
        state["turn_response"] = _ask_free_text(state, llm.build_reply(
            context={},
            instruction="Say a destination needs to be picked first before searching flights, "
                        "and ask where they want to go.",
        ))
        return state

    if not state.get("departure_city"):
        state["conversation_stage"] = "collecting_flight_departure"
        state["turn_response"] = _ask_free_text(state, llm.build_reply(
            context={}, instruction="Ask where the user would be flying from.",
        ))
        return state

    # T3b: reuse previously collected dates; only ask if neither source has them
    slots = llm.extract_trip_slots(state["last_user_message"])
    outbound_date = (slots.get("outbound_date")
                     or state.get("outbound_date"))       # persisted from destination flow
    return_date   = (slots.get("return_date")
                     or state.get("return_date"))

    if not outbound_date:
        state["conversation_stage"] = "collecting_flight_date"
        state["turn_response"] = _ask_free_text(state, llm.build_reply(
            context={}, instruction="Ask what date the user wants to depart.",
        ))
        return state

    # T2: if we're already in confirming_flight, handle the yes/no answer
    if state.get("conversation_stage") == "confirming_flight":
        return _handle_confirm_flight(state)

    flights = services.fetch_flight_options(
        state["departure_city"], state["destination_city"], outbound_date,
        return_date=return_date, currency=state["currency"],
    )

    if flights is None:
        state["turn_response"] = _ask_free_text(state, llm.build_reply(
            context={"departure_city": state["departure_city"],
                      "destination_city": state["destination_city"]},
            instruction="Say one of those cities/airports wasn't recognized and ask for a clearer one.",
        ))
        return state

    # T2: try to select from candidates if user already named a flight in this message
    top = flights[:config.MAX_FLIGHTS_SHOWN]
    state["flight_candidates"] = top

    # Check if user already named one in this turn (e.g. "book the cheapest")
    picked = llm.select_option(state["last_user_message"], top)
    if picked:
        state["confirmed_flight"] = dict(picked[0], mock_confirmed=False)
        state["conversation_stage"] = "confirming_flight"
        state["turn_response"] = _flight_confirmation_prompt(state)
        return state

    state["turn_response"] = {
        "reply": llm.build_reply(
            context={"flights": top},
            instruction="Present these real flight options - price, whether it looks like a good "
                        "deal against the typical price range, and flag any with a history of "
                        "delays over 30 minutes (a historical statistic, not a live status check).",
        ),
        "stage": state["conversation_stage"],
        "ui_component": "flight_options",
        "options": top,
        "requires_user_input": True,
        "input_type": "select_one",
    }
    return state


_CONFIRM_YES = {"yes", "yeah", "yep", "sure", "confirm", "book", "ok", "okay",
                "sounds good", "go ahead", "do it", "confirmed", "proceed"}
_CONFIRM_NO  = {"no", "nope", "nah", "cancel", "different", "change", "other",
                "another", "back", "wait", "not this one"}


def _flight_confirmation_prompt(state: TripState) -> dict:
    """Build the turn_response that asks the user to confirm the selected flight."""
    flight = state["confirmed_flight"]
    return {
        "reply": llm.build_reply(
            context={"flight": flight},
            instruction=(
                "Summarise the selected flight: airline, departure/arrival time, price, stops. "
                "Ask the user to confirm (yes/no). Do not claim any real booking or payment — "
                "this is a demo booking flow only."
            ),
        ),
        "stage": "confirming_flight",
        "ui_component": "text",
        "options": [],
        "requires_user_input": True,
        "input_type": "confirm",
    }


def _handle_confirm_flight(state: TripState) -> TripState:
    """Process a yes/no answer when conversation_stage == confirming_flight."""
    msg_lower = state["last_user_message"].strip().lower()
    flight = state.get("confirmed_flight") or {}

    if any(w in msg_lower for w in _CONFIRM_NO):
        # User wants a different flight — go back to options
        state["confirmed_flight"] = None
        state["conversation_stage"] = "trip_active"
        state["turn_response"] = {
            "reply": llm.build_reply(
                context={"flights": state["flight_candidates"]},
                instruction="The user wants a different flight. Show the options again and ask them to choose.",
            ),
            "stage": "trip_active",
            "ui_component": "flight_options",
            "options": state["flight_candidates"],
            "requires_user_input": True,
            "input_type": "select_one",
        }
        return state

    # Default: yes — mark mock confirmed
    flight["mock_confirmed"] = True
    state["confirmed_flight"] = flight
    state["conversation_stage"] = "trip_active"
    state["turn_response"] = {
        "reply": llm.build_reply(
            context={"flight": flight},
            instruction=(
                "Tell the user their flight is mock-confirmed (DEMO only — no real booking or payment "
                "was made). Summarise the booking details briefly. Remind them they can still ask about "
                "hotels, itinerary, or nearby exploration."
            ),
        ),
        "stage": "trip_active",
        "ui_component": "text",
        "options": [],
        "requires_user_input": False,
        "input_type": "none",
    }
    return state


def _ask_free_text(state: TripState, reply: str) -> dict:
    return {
        "reply": reply, "stage": state["conversation_stage"], "ui_component": "text",
        "options": [], "requires_user_input": True, "input_type": "free_text",
    }