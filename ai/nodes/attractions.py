"""
Fetches attractions for the chosen destination and asks the user to
confirm a shortlist. The actual fetch/cache/rank logic lives in
services.fetch_attraction_candidates so nodes/adjust.py can call the
exact same capability later (to extend the trip or replace disliked
items) without duplicating it.
"""
import llm
import services
from state import TripState


def attractions_node(state: TripState) -> TripState:
    city = state["destination_city"]
    candidates = services.fetch_attraction_candidates(city)

    summary_attractions = [
        {
            "name": attr.get("name"),
            "rating": attr.get("rating"),
            "category": attr.get("category"),
        }
        for attr in (candidates or [])
    ]

    state["attraction_candidates"] = candidates
    state["conversation_stage"] = "collecting_attractions"
    state["turn_response"] = {
        "reply": llm.build_reply(
            context={"attractions": summary_attractions},
            instruction="Present these attractions and ask the user to confirm which ones to include.",
        ),
        "stage": "collecting_attractions",
        "ui_component": "attraction_options",
        "options": candidates,
        "requires_user_input": True,
        "input_type": "select_multi",
    }
    return state


def confirm_attractions_node(state: TripState) -> TripState:
    if not state["confirmed_attractions"]:
        picked = llm.select_option(
            state["last_user_message"], state["attraction_candidates"], multi=True
        )
        state["confirmed_attractions"] = picked

    if not state["confirmed_attractions"]:
        state["turn_response"] = {
            "reply": llm.build_reply(
                context={"attractions": state["attraction_candidates"]},
                instruction="The selection wasn't clear - ask again which of these to include.",
            ),
            "stage": "collecting_attractions",
            "ui_component": "attraction_options",
            "options": state["attraction_candidates"],
            "requires_user_input": True,
            "input_type": "select_multi",
        }
        return state

    state["conversation_stage"] = "collecting_hotel"
    state["turn_response"] = {
        "reply": llm.build_reply(
            context={"confirmed_attractions": state["confirmed_attractions"]},
            instruction="Confirm the selection and say we're finding a hotel close to all of it now.",
        ),
        "stage": "collecting_hotel",
        "ui_component": "text",
        "options": [],
        "requires_user_input": False,
        "input_type": "none",
    }
    return state
