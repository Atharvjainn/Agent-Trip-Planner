"""
ai/AGENT.md graph table, build_summary:
  selections -> commute estimate between hotel and spots -> LLM short
  narrative.
  Fallback: template narrative.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import Field

from app.llm.prompts.build_summary import SYSTEM, build_prompt
from app.llm.provider import LLMAllProvidersFailed, LLMProvider
from app.rules.commute import estimate_commute
from app.schemas.common import CamelModel, Money
from app.schemas.summary import CommuteEstimate, SummaryBuildRequest, SummaryBuildResponse
from app.tools.geo import Point


class _LlmNarrativeResult(CamelModel):
    narrative: str = Field(max_length=800)


@dataclass
class SummaryDeps:
    llm: LLMProvider


def default_deps() -> SummaryDeps:
    return SummaryDeps(llm=LLMProvider())


class SummaryState(TypedDict, total=False):
    request: SummaryBuildRequest
    deps: SummaryDeps
    commute: CommuteEstimate
    narrative: str
    fallback_used: bool


async def node_commute(state: SummaryState) -> dict:
    req = state["request"]
    hotel = Point(lat=req.hotel_location.lat, lng=req.hotel_location.lng)
    spots = [Point(lat=s.location.lat, lng=s.location.lng) for s in req.selected_spots]
    est = estimate_commute(hotel=hotel, spots=spots, nights=req.nights, city_tier=None)
    commute = CommuteEstimate(
        daily_distance_km=round(est.daily_distance_km, 2),
        daily_cost=Money(amount_minor=est.daily_cost_minor, currency=req.flight_price.currency),
        trip_total_cost=Money(amount_minor=est.trip_total_cost_minor, currency=req.flight_price.currency),
        mode=est.mode,
    )
    return {"commute": commute}


def _format_money(m: Money) -> str:
    return f"{m.amount_minor / 100:.2f} {m.currency}"


def _template_narrative(req: SummaryBuildRequest, commute: CommuteEstimate) -> str:
    spot_names = ", ".join(s.name for s in req.selected_spots) or "your chosen spots"
    return (
        f"Your {req.nights}-night trip to {req.city} is ready. You'll explore "
        f"{spot_names}, with flights estimated at {_format_money(req.flight_price)} and "
        f"your stay at {_format_money(req.hotel_total_price)}. Local commute between your "
        f"hotel and spots is estimated at {_format_money(commute.trip_total_cost)} for the "
        f"whole trip — all figures are estimates."
    )


async def node_narrative(state: SummaryState) -> dict:
    req = state["request"]
    deps = state["deps"]
    commute = state["commute"]

    try:
        prompt = build_prompt(
            city=req.city,
            nights=req.nights,
            spot_names=[s.name for s in req.selected_spots],
            flight_price_text=_format_money(req.flight_price),
            hotel_total_text=_format_money(req.hotel_total_price),
            commute_total_text=_format_money(commute.trip_total_cost),
        )
        result = await deps.llm.structured(
            "build_summary.narrative", prompt, _LlmNarrativeResult, system=SYSTEM
        )
        return {"narrative": result.narrative, "fallback_used": False}
    except LLMAllProvidersFailed:
        return {"narrative": _template_narrative(req, commute), "fallback_used": True}


def build_graph():
    graph = StateGraph(SummaryState)
    graph.add_node("commute", node_commute)
    graph.add_node("narrative", node_narrative)
    graph.set_entry_point("commute")
    graph.add_edge("commute", "narrative")
    graph.add_edge("narrative", END)
    return graph.compile()


_compiled = None


async def run(request: SummaryBuildRequest, deps: SummaryDeps | None = None) -> SummaryBuildResponse:
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    result = await _compiled.ainvoke({"request": request, "deps": deps or default_deps()})
    return SummaryBuildResponse(
        trip_id=request.trip_id,
        narrative=result["narrative"],
        commute=result["commute"],
        fallback_used=result.get("fallback_used", False),
    )
