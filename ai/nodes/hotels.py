"""
Hotel search prioritizes proximity to the confirmed attraction cluster,
then budget. The fetch/cache/rank logic lives in
services.fetch_hotel_candidates so nodes/adjust.py's change_hotel
handler calls the same capability instead of duplicating it.
"""
from datetime import date, timedelta

import config
import llm
import services
from tools.geo import centroid
from tools import serpapi_client
from state import TripState

_CONFIRM_YES = {"yes", "yeah", "yep", "sure", "confirm", "book", "ok", "okay",
                "sounds good", "go ahead", "do it", "confirmed", "proceed"}
_CONFIRM_NO  = {"no", "nope", "nah", "cancel", "different", "change", "other",
                "another", "back", "wait", "not this one"}


def hotels_node(state: TripState) -> TripState:
    city = state["destination_city"]
    attractions = state["confirmed_attractions"]
    lat, lon = centroid([(a["lat"], a["lon"]) for a in attractions])
    nights = state.get("duration_days") or config.DEFAULT_TRIP_DURATION_DAYS

    ranked = services.fetch_hotel_candidates(
        city, lat, lon, budget_total=state.get("budget_total"), nights=nights,
        currency=state["currency"],
    )

    state["hotel_candidates"] = ranked
    state["turn_response"] = {
        "reply": llm.build_reply(
            context={"hotels": ranked, "budget_total": state.get("budget_total")},
            instruction="Present these hotels - all close to the places already picked - and ask the user to choose one.",
        ),
        "stage": "collecting_hotel",
        "ui_component": "hotel_options",
        "options": ranked,
        "requires_user_input": True,
        "input_type": "select_one",
    }
    return state


def confirm_hotel_node(state: TripState) -> TripState:
    if not state.get("confirmed_hotel"):
        picked = llm.select_option(state["last_user_message"], state["hotel_candidates"])
        if picked:
            state["confirmed_hotel"] = picked[0]

    hotel = state.get("confirmed_hotel")
    if not hotel:
        state["turn_response"] = {
            "reply": llm.build_reply(
                context={"hotels": state["hotel_candidates"]},
                instruction="The choice wasn't clear - ask again which hotel to book.",
            ),
            "stage": "collecting_hotel",
            "ui_component": "hotel_options",
            "options": state["hotel_candidates"],
            "requires_user_input": True,
            "input_type": "select_one",
        }
        return state

    # If we already asked for confirmation, process the yes/no answer
    if state.get("conversation_stage") == "confirming_hotel":
        msg_lower = state["last_user_message"].strip().lower()
        if any(w in msg_lower for w in _CONFIRM_NO):
            # User changed their mind — go back to selection
            state["confirmed_hotel"] = None
            state["conversation_stage"] = "collecting_hotel"
            state["turn_response"] = {
                "reply": llm.build_reply(
                    context={"hotels": state["hotel_candidates"]},
                    instruction="The user wants a different hotel. Show the options again and ask them to choose.",
                ),
                "stage": "collecting_hotel",
                "ui_component": "hotel_options",
                "options": state["hotel_candidates"],
                "requires_user_input": True,
                "input_type": "select_one",
            }
            return state
        # Default: treat as yes (confirmed)
        hotel["mock_confirmed"] = True
        state["conversation_stage"] = "itinerary_ready"
        state["turn_response"] = {
            "reply": llm.build_reply(
                context={"confirmed_hotel": hotel},
                instruction=(
                    "Tell the user their hotel is confirmed (DEMO/MOCK only — no real "
                    "reservation or payment was made). Now building the day-by-day itinerary."
                ),
            ),
            "stage": "itinerary_ready",
            "ui_component": "text",
            "options": [],
            "requires_user_input": False,
            "input_type": "none",
        }
        return state

    # First visit: refresh price, then ask for booking confirmation
    nights = state.get("duration_days") or config.DEFAULT_TRIP_DURATION_DAYS
    fresh = serpapi_client.refresh_hotel_price(
        hotel["place_id"],
        check_in=date.today().isoformat(),
        check_out=(date.today() + timedelta(days=nights)).isoformat(),
        currency=state["currency"],
    )
    if fresh:
        hotel.update(fresh)

    state["conversation_stage"] = "confirming_hotel"
    state["turn_response"] = {
        "reply": llm.build_reply(
            context={"hotel": hotel, "nights": nights, "currency": state["currency"]},
            instruction=(
                "Summarise the selected hotel: name, price per night, total cost for the stay. "
                "Then ask the user to confirm (yes/no). Do not claim any real reservation "
                "or payment — this is a demo booking flow only."
            ),
        ),
        "stage": "confirming_hotel",
        "ui_component": "text",
        "options": [],
        "requires_user_input": True,
        "input_type": "confirm",
    }
    return state