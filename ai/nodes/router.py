import time
import llm
from state import TripState

_ROUTING_MS_STORE: dict[str, float] = {}


def classify_intent(state: TripState) -> str:
    t0 = time.perf_counter()
    intent = llm.classify_intent(state)
    t1 = time.perf_counter()
    ms = round((t1 - t0) * 1000, 2)
    state["_routing_ms"] = ms
    sid = state.get("session_id")
    if sid:
        _ROUTING_MS_STORE[sid] = ms
    return intent


def get_routing_ms(session_id: str) -> float | None:
    return _ROUTING_MS_STORE.pop(session_id, None)
