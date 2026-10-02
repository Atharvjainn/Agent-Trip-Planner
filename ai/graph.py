"""
Wires all nodes into a LangGraph StateGraph.

Two routing decisions happen here, at different levels of granularity:

1. ENTRY routing (route_from_start) - which node handles a brand new
   incoming message. llm.classify_intent gives a coarse answer (new
   trip / adjust the existing plan / greeting / continuing something
   already in progress); "adjust" then does its own, finer
   classification internally (nodes/adjust.py) for a first-time
   adjustment request. The two collecting_flight_* stages are the
   exception: they exist because a bare follow-up ("Mumbai", "March
   15th") isn't enough on its own to reliably re-derive "this is a
   flight search" - adjust_node checks for those stages before
   re-classifying, the same reason "collecting_hotel" below skips
   straight to confirm_hotel_node instead of re-deriving intent from a
   bare hotel selection.

2. CHAINING within one turn (the after_* functions) - once a node has
   what it needs, it moves straight to the next step without waiting
   for another user message. The turn only ends (END) at a node that
   just asked the user something.
"""
from langgraph.graph import StateGraph, END

import llm
from state import TripState
from nodes.router import classify_intent
from nodes.destination import destination_node
from nodes.attractions import attractions_node, confirm_attractions_node
from nodes.hotels import hotels_node, confirm_hotel_node
from nodes.itinerary import itinerary_node
from nodes.adjust import adjust_node


def greeting_node(state: TripState) -> TripState:
    state["turn_response"] = {
        "reply": llm.build_reply(
            context={}, instruction="Greet the user and ask where they'd like to go, or what kind of trip they're after."
        ),
        "stage": "start",
        "ui_component": "text",
        "options": [],
        "requires_user_input": True,
        "input_type": "free_text",
    }
    return state


def route_from_start(state: TripState) -> str:
    intent = classify_intent(state)
    if intent == "greeting":
        return "greeting"
    if intent == "new_trip":
        return "destination"
    if intent == "trip_adjustment":
        return "adjust"
    # continue_flow: resume whatever the last turn was waiting on
    return {
        "start": "greeting",
        "collecting_departure": "destination",
        "collecting_destination": "destination",
        "collecting_attractions": "confirm_attractions",
        "collecting_hotel": "confirm_hotel",
        "itinerary_ready": "itinerary",
        "trip_active": "adjust",
        "collecting_flight_departure": "adjust",
        "collecting_flight_date": "adjust",
    }[state["conversation_stage"]]


def after_destination(state: TripState) -> str:
    return "attractions" if state["conversation_stage"] == "collecting_attractions" else END


def after_confirm_attractions(state: TripState) -> str:
    return "hotels" if state["conversation_stage"] == "collecting_hotel" else END


def after_confirm_hotel(state: TripState) -> str:
    return "itinerary" if state["conversation_stage"] == "itinerary_ready" else END


def build_graph():
    graph = StateGraph(TripState)

    graph.add_node("greeting", greeting_node)
    graph.add_node("destination", destination_node)
    graph.add_node("attractions", attractions_node)
    graph.add_node("confirm_attractions", confirm_attractions_node)
    graph.add_node("hotels", hotels_node)
    graph.add_node("confirm_hotel", confirm_hotel_node)
    graph.add_node("itinerary", itinerary_node)
    graph.add_node("adjust", adjust_node)

    graph.set_conditional_entry_point(
        route_from_start,
        {
            "greeting": "greeting",
            "destination": "destination",
            "adjust": "adjust",
            "confirm_attractions": "confirm_attractions",
            "confirm_hotel": "confirm_hotel",
            "itinerary": "itinerary",
        },
    )

    graph.add_conditional_edges("destination", after_destination, {"attractions": "attractions", END: END})
    graph.add_conditional_edges(
        "confirm_attractions", after_confirm_attractions, {"hotels": "hotels", END: END}
    )
    graph.add_conditional_edges("confirm_hotel", after_confirm_hotel, {"itinerary": "itinerary", END: END})

    graph.add_edge("greeting", END)
    graph.add_edge("attractions", END)
    graph.add_edge("hotels", END)
    graph.add_edge("itinerary", END)
    graph.add_edge("adjust", END)

    return graph.compile()