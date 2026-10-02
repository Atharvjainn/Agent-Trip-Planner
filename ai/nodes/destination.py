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

    interest = llm.classify_explore_interest(state["last_user_message"], state.get("vibe"))
    candidates = services.fetch_destination_recommendations(
        state["departure_city"], interest=interest, currency=state["currency"]
    )

    if candidates is None:
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