"""
Classifies the incoming user message into a coarse intent. All the
actual reasoning happens in llm.classify_intent (an OpenJev typed
`choice` decision over the full trip context, not just the raw
message) - this module just exists so graph.py doesn't import llm
directly for routing.
"""
import llm
from state import TripState


def classify_intent(state: TripState) -> str:
    return llm.classify_intent(state)
