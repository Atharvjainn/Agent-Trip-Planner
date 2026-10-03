"""
ai/AGENT.md graph table, suggest_savings:
  run registered SavingStrategy list (currently empty).
  Fallback: empty list.

root AGENTS.md §8: do not implement specific strategies until they're
written in docs/cost-strategies.md. This graph is the full, real,
end-to-end wiring for the job — only the strategy list itself is empty.
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.rules.saving_strategies import run_all
from app.schemas.savings import SavingsSuggestRequest, SavingsSuggestResponse, SavingSuggestion


class SavingsState(TypedDict, total=False):
    request: SavingsSuggestRequest
    suggestions: list[SavingSuggestion]


async def node_run_strategies(state: SavingsState) -> dict:
    req = state["request"]
    suggestions = run_all(req.selections)
    return {"suggestions": suggestions}


def build_graph():
    graph = StateGraph(SavingsState)
    graph.add_node("run_strategies", node_run_strategies)
    graph.set_entry_point("run_strategies")
    graph.add_edge("run_strategies", END)
    return graph.compile()


_compiled = None


async def run(request: SavingsSuggestRequest) -> SavingsSuggestResponse:
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    result = await _compiled.ainvoke({"request": request})
    return SavingsSuggestResponse(
        trip_id=request.trip_id, suggestions=result["suggestions"], fallback_used=False
    )
