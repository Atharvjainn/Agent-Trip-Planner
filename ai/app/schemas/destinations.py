from __future__ import annotations

from datetime import date

from pydantic import Field, field_validator

from app.schemas.common import CamelModel, Money, vibe_tags


class DestinationRecommendRequest(CamelModel):
    trip_id: str
    source: str  # IATA code or city name, as entered in step 2
    start_date: date
    end_date: date
    travelers: int = Field(ge=1)
    budget_total: Money
    vibes: list[str]

    @field_validator("vibes")
    @classmethod
    def _known_vibes(cls, v: list[str]) -> list[str]:
        allowed = set(vibe_tags())
        unknown = [tag for tag in v if tag not in allowed]
        if unknown:
            raise ValueError(f"unknown vibe tags: {unknown}")
        return v


class DestinationOption(CamelModel):
    city: str
    country: str
    estimated_flight_price: Money
    vibe_match_score: float = Field(ge=0, le=1)
    reason: str  # LLM-written (or generic fallback) one-liner
    source: str  # "llm" | "knowledge_graph" — lets the frontend/QA tell real ranking from fallback


class DestinationRecommendResponse(CamelModel):
    trip_id: str
    options: list[DestinationOption] = Field(max_length=5)
    fallback_used: bool = False
