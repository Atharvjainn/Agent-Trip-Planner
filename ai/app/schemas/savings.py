from __future__ import annotations

from app.schemas.common import CamelModel, Money


class SelectionSnapshot(CamelModel):
    """Whatever has been chosen so far — enough for a strategy to reason
    about, without the AI service touching Prisma (root AGENTS.md §4.4)."""

    flight_price: Money | None = None
    hotel_price_per_night: Money | None = None
    nights: int | None = None
    stay_budget: Money | None = None


class SavingsSuggestRequest(CamelModel):
    trip_id: str
    selections: SelectionSnapshot


class SavingSuggestion(CamelModel):
    strategy_id: str
    title: str
    description: str
    estimated_savings: Money


class SavingsSuggestResponse(CamelModel):
    trip_id: str
    suggestions: list[SavingSuggestion]
    fallback_used: bool = False
