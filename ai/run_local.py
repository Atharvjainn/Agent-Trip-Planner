"""
Minimal local harness for exercising the graph without a frontend or
API layer - a plain REPL that keeps one TripState across turns.

    python run_local.py
"""
from dotenv import load_dotenv
load_dotenv()

from graph import build_graph
from state import TripState


def initial_state(session_id: str) -> TripState:
    return TripState(
        session_id=session_id, user_id=None, conversation_stage="start",
        last_user_message="", destination_city=None, departure_city=None, vibe=None,
        budget_total=None, duration_days=None, currency="INR",
        destination_candidates=[], attraction_candidates=[],
        confirmed_attractions=[], hotel_candidates=[], confirmed_hotel=None,
        itinerary=[], flight_candidates=[], confirmed_flight=None,
        user_location=None, free_minutes=None,
        turn_response={
            "reply": "", "stage": "start", "ui_component": "text",
            "options": [], "requires_user_input": True, "input_type": "free_text",
        },
    )


def _label(opt: dict) -> str:
    if opt.get("name") or opt.get("title"):
        return opt.get("name") or opt.get("title")
    if "departure_airport" in opt:  # a FlightOption - no name/title field
        return f"{opt.get('departure_airport')} -> {opt.get('arrival_airport')}, {opt.get('price')}"
    return str(opt)


def main():
    app = build_graph()
    state = initial_state(session_id="local-test")
    print("Trip planner (type 'quit' to exit)\n")
    while True:
        message = input("you> ").strip()
        if message.lower() == "quit":
            break
        state["last_user_message"] = message
        state = app.invoke(state)
        turn = state["turn_response"]
        print(f"agent> {turn['reply']}")
        for i, opt in enumerate(turn["options"], start=1):
            print(f"   {i}. {_label(opt)}")


if __name__ == "__main__":
    main()