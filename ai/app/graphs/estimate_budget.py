"""
ai/AGENT.md graph table, estimate_budget:
  rules split -> LLM adjust with explanation -> validate.
  Fallback: rules split only.

ai/AGENT.md "Budget estimate rules": the LLM may adjust each category by
at most +/-15 percentage points and must return an explanation.
Validation after the LLM: all amounts >= 0, integers in minor units, sum
equals the total exactly. If validation fails, return the rules split.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import Field

from app.llm.prompts.estimate_budget import SYSTEM, build_prompt
from app.llm.provider import LLMAllProvidersFailed, LLMProvider
from app.rules.budget import (
    CATEGORIES,
    default_split_pct,
    split_to_amounts,
    validate_amounts,
    validate_llm_adjustment,
)
from app.rules.budget import LlmAdjustment as RulesLlmAdjustment
from app.schemas.budget import (
    BudgetEstimateRequest,
    BudgetEstimateResponse,
    CategoryAllocation,
)
from app.schemas.common import CamelModel, Money

logger = logging.getLogger("services.ai.graphs.estimate_budget")

DEFAULT_EXPLANATION = (
    "Using the standard allocation for this trip type and length — no adjustment was needed."
)


class _LlmAdjustResult(CamelModel):
    adjusted_pct: dict[str, int]
    explanation: str = Field(max_length=500)


@dataclass
class BudgetDeps:
    llm: LLMProvider


def default_deps() -> BudgetDeps:
    return BudgetDeps(llm=LLMProvider())


class BudgetState(TypedDict, total=False):
    request: BudgetEstimateRequest
    deps: BudgetDeps
    base_pct: dict[str, int]
    final_pct: dict[str, int]
    explanation: str
    fallback_used: bool
    allocations: list[CategoryAllocation]


async def node_base_split(state: BudgetState) -> dict:
    req = state["request"]
    base_pct = default_split_pct(is_international=req.is_international, duration_days=req.duration_days)
    return {"base_pct": base_pct}


async def node_llm_adjust(state: BudgetState) -> dict:
    req = state["request"]
    deps = state["deps"]
    base_pct = state["base_pct"]

    try:
        prompt = build_prompt(
            base_split_pct=base_pct,
            is_international=req.is_international,
            duration_days=req.duration_days,
            vibes=req.vibes,
        )
        result = await deps.llm.structured(
            "estimate_budget.adjust", prompt, _LlmAdjustResult, system=SYSTEM
        )
        adjustment = RulesLlmAdjustment(adjusted_pct=result.adjusted_pct, explanation=result.explanation)
        if not validate_llm_adjustment(base_pct, adjustment):
            logger.info("estimate_budget: LLM adjustment failed validation, using rules split")
            return {"final_pct": base_pct, "explanation": DEFAULT_EXPLANATION, "fallback_used": True}
        return {
            "final_pct": adjustment.adjusted_pct,
            "explanation": adjustment.explanation,
            "fallback_used": False,
        }
    except LLMAllProvidersFailed:
        logger.info("estimate_budget: LLM unavailable, using rules split")
        return {"final_pct": base_pct, "explanation": DEFAULT_EXPLANATION, "fallback_used": True}


async def node_finalize(state: BudgetState) -> dict:
    req = state["request"]
    amounts = split_to_amounts(req.budget_total.amount_minor, state["final_pct"])
    if not validate_amounts(req.budget_total.amount_minor, amounts):
        # Should be unreachable given split_to_amounts' construction, but
        # this is the hard backstop called out in ai/AGENT.md: "If
        # validation fails, return the rules split."
        logger.warning("estimate_budget: amount validation failed unexpectedly, forcing rules split")
        amounts = split_to_amounts(req.budget_total.amount_minor, state["base_pct"])
        state = {**state, "explanation": DEFAULT_EXPLANATION, "fallback_used": True}

    allocations = [
        CategoryAllocation(
            category=cat, amount=Money(amount_minor=amounts[cat], currency=req.budget_total.currency)
        )
        for cat in CATEGORIES
    ]
    return {
        "allocations": allocations,
        "explanation": state["explanation"],
        "fallback_used": state["fallback_used"],
    }


def build_graph():
    graph = StateGraph(BudgetState)
    graph.add_node("base_split", node_base_split)
    graph.add_node("llm_adjust", node_llm_adjust)
    graph.add_node("finalize", node_finalize)
    graph.set_entry_point("base_split")
    graph.add_edge("base_split", "llm_adjust")
    graph.add_edge("llm_adjust", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


_compiled = None


async def run(request: BudgetEstimateRequest, deps: BudgetDeps | None = None) -> BudgetEstimateResponse:
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    result = await _compiled.ainvoke({"request": request, "deps": deps or default_deps()})
    return BudgetEstimateResponse(
        trip_id=request.trip_id,
        currency=request.budget_total.currency,
        allocations=result["allocations"],
        explanation=result["explanation"],
        fallback_used=result["fallback_used"],
    )
