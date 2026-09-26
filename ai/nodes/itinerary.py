"""
Greedy day-wise clustering (tools.geo.cluster_by_day) - not a real
routing solver, deliberately. This is the node to upgrade first if
there's time left over after the agent behavior itself is solid.

Two things layered on top of the base clustering, both additive rather
than changing how the grouping/ordering itself is decided:
- services.attach_travel_times attaches a REAL travel time to each stop
  from the one before it, using Google Maps Directions - called once
  per already-decided consecutive pair, not during the clustering
  search (see that function's docstring for why the split matters).
- services.fetch_events surfaces real festivals/concerts happening at
  the destination, passed into the reply's context so it can be
  mentioned - not added as itinerary stops themselves, since matching
  an event to a specific day/slot isn't attempted here.
"""
import config
import llm
import services
from tools.geo import cluster_by_day
from state import TripState


def itinerary_node(state: TripState) -> TripState:
    attractions = state["confirmed_attractions"]
    days = state.get("duration_days") or config.DEFAULT_TRIP_DURATION_DAYS

    clustered = cluster_by_day(attractions, days)
    itinerary = []
    for i, day_places in enumerate(clustered, start=1):
        stops = [
            {
                "place_id": a["place_id"],
                "name": a["name"],
                "lat": a.get("lat"),
                "lon": a.get("lon"),
                "notes": a.get("best_time_hint", ""),
                "hours": a.get("hours"),  # real, from google_maps - see serpapi_client's normalizer
            }
            for a in day_places
        ]
        itinerary.append({"day": i, "stops": stops})

    itinerary = services.attach_travel_times(itinerary)
    events = services.fetch_events(state["destination_city"])

    state["itinerary"] = itinerary
    state["conversation_stage"] = "trip_active"
    state["turn_response"] = {
        "reply": llm.build_reply(
            context={"itinerary": itinerary, "events_during_trip": events},
            instruction=(
                "Present this day-by-day plan briefly, including travel time between stops "
                "where it's available. If any of the listed events look relevant, mention one "
                "or two - otherwise skip that. Mention the user can ask things like 'I've got 2 "
                "hours free, what's nearby?' once they're on the trip."
            ),
        ),
        "stage": "trip_active",
        "ui_component": "itinerary",
        "options": itinerary,
        "requires_user_input": False,
        "input_type": "none",
    }
    return state