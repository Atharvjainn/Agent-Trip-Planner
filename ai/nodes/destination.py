"""
Handles two situations:
1) the user already named (or just named) a destination -> move on
2) they didn't -> recommend real destinations via
   services.fetch_destination_recommendations (Google Travel Explore),
   never a static list.

Google Travel Explore requires a departure point - that's a real
constraint of the underlying API, not a design choice - so if we don't
have one yet, this node asks for it explicitly rather than guessing a
default city, the same way it already asks rather than guessing a
destination.

Slot extraction, vibe classification, and matching a follow-up message
against previously shown options all go through llm.py - nothing here
pattern-matches the user's text itself.
"""
import llm
import services
from state import TripState


def destination_node(state: TripState) -> TripState:
    _fill_known_slots(state)

    if not state.get("destination_city") and state.get("destination_candidates"):
        picked = llm.select_option(state["last_user_message"], state["destination_candidates"])
        if picked:
            state["destination_city"] = picked[0]["name"]

    if state.get("destination_city"):
        state["conversation_stage"] = "collecting_attractions"
        state["turn_response"] = {
            "reply": llm.build_reply(
                context={"destination_city": state["destination_city"]},
                instruction="Confirm the destination and say we're about to find places to visit there.",
            ),
            "stage": "collecting_attractions",
            "ui_component": "text",
            "options": [],
            "requires_user_input": False,
            "input_type": "none",
        }
        return state

    if not state.get("departure_city"):
        state["conversation_stage"] = "collecting_departure"
        state["turn_response"] = {
            "reply": llm.build_reply(
                context={},
                instruction="Ask where the user is starting their trip from - real destination "
                            "suggestions need a departure point.",
            ),
            "stage": "collecting_departure",
            "ui_component": "text",
            "options": [],
            "requires_user_input": True,
            "input_type": "free_text",
        }
        return state

    if state.get("conversation_stage") == "collecting_departure_airport" and state.get("departure_airport_options"):
        picked = llm.select_option(state["last_user_message"], state["departure_airport_options"])
        if picked:
            state["departure_airport"] = picked[0]["id"]
        else:
            state["turn_response"] = {
                "reply": llm.build_reply(
                    context={"options": state["departure_airport_options"]},
                    instruction="Ask the user to pick one of the listed airport options or choose 'Any airport'.",
                ),
                "stage": "collecting_departure_airport",
                "ui_component": "airport_options",
                "options": state["departure_airport_options"],
                "requires_user_input": True,
                "input_type": "select_one",
            }
            return state

    if not state.get("departure_airport"):
        airport_options = services.fetch_departure_airport_options(state["departure_city"])
        if not airport_options:
            state["departure_city"] = None
            state["conversation_stage"] = "collecting_departure"
            state["turn_response"] = {
                "reply": llm.build_reply(
                    context={"invalid_departure": state.get("last_user_message")},
                    instruction="Say that departure city/airport wasn't recognized and ask for a clearer city name or airport code.",
                ),
                "stage": "collecting_departure",
                "ui_component": "text",
                "options": [],
                "requires_user_input": True,
                "input_type": "free_text",
            }
            return state

        if len(airport_options) == 1 and airport_options[0]["id"] == state["departure_city"].upper():
            state["departure_airport"] = airport_options[0]["id"]
        else:
            any_option = {"id": "ANY", "name": "Any airport", "code": "ANY"}
            options_to_show = airport_options + [any_option]
            state["departure_airport_options"] = options_to_show
            state["conversation_stage"] = "collecting_departure_airport"
            state["turn_response"] = {
                "reply": llm.build_reply(
                    context={"departure_city": state["departure_city"], "options": options_to_show},
                    instruction="Present these real airport options for the departure city, plus an 'Any airport' option, and ask the user to select one.",
                ),
                "stage": "collecting_departure_airport",
                "ui_component": "airport_options",
                "options": options_to_show,
                "requires_user_input": True,
                "input_type": "select_one",
            }
            return state

    dep_id = state["departure_city"] if state.get("departure_airport") == "ANY" else (state.get("departure_airport") or state["departure_city"])
    interest = llm.classify_explore_interest(state["last_user_message"], state.get("vibe"))
    candidates = services.fetch_destination_recommendations(
        dep_id, interest=interest, currency=state["currency"]
    )

    if candidates is None:
        state["departure_city"] = None
        state["departure_airport"] = None
        state["conversation_stage"] = "collecting_departure"
        state["turn_response"] = {
            "reply": llm.build_reply(
                context={"departure_city": state["departure_city"]},
                instruction="Say that departure city/airport wasn't recognized and ask for a "
                            "clearer one - a city name or an airport code.",
            ),
            "stage": "collecting_departure",
            "ui_component": "text",
            "options": [],
            "requires_user_input": True,
            "input_type": "free_text",
        }
        return state

    state["destination_candidates"] = candidates
    state["turn_response"] = {
        "reply": llm.build_reply(
            context={"candidates": candidates, "vibe": state.get("vibe"),
                      "departure_city": state["departure_city"]},
            instruction="Present these real destination options, including their flight/hotel "
                        "price estimates, and ask the user to pick one or name somewhere else.",
        ),
        "stage": "collecting_destination",
        "ui_component": "destination_options",
        "options": candidates,
        "requires_user_input": True,
        "input_type": "select_one",
    }
    return state


def _fill_known_slots(state: TripState) -> None:
    slots = llm.extract_trip_slots(state["last_user_message"])
    for key in ("destination_city", "departure_city", "budget_total", "duration_days"):
        if slots.get(key) is not None and not state.get(key):
            state[key] = slots[key]

    if not state.get("vibe"):
        vibe = llm.classify_vibe(state["last_user_message"])
        if vibe:
            state["vibe"] = vibe