from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from app.schemas.common import CamelModel, Money, budget_categories


class BudgetEstimateRequest(CamelModel):
    trip_id: str
    budget_total: Money
    is_international: bool
    duration_days: int = Field(ge=1)
    vibes: list[str] = Field(default_factory=list)


class CategoryAllocation(CamelModel):
    category: str
    amount: Money

    @field_validator("category")
    @classmethod
    def _known_category(cls, v: str) -> str:
        allowed = budget_categories()
        if v not in allowed:
            raise ValueError(f"unknown budget category {v!r}, must be one of {allowed}")
        return v


class BudgetEstimateResponse(CamelModel):
    trip_id: str
    currency: str
    allocations: list[CategoryAllocation]
    explanation: str
    fallback_used: bool = False

    @model_validator(mode="after")
    def _sum_matches_total_is_checked_upstream(self) -> BudgetEstimateResponse:
        # The actual "sum equals total exactly" invariant (ai/AGENT.md
        # "Budget estimate rules") is enforced in app/rules/budget.py /
        # app/graphs/estimate_budget.py BEFORE this model is constructed —
        # by the time we build this response the numbers are already valid.
        # We re-check here too, cheaply, as a last line of defense.
        categories = {a.category for a in self.allocations}
        if categories != set(budget_categories()):
            raise ValueError(
                f"allocation must cover every category exactly once, got {sorted(categories)}"
            )
        return self
