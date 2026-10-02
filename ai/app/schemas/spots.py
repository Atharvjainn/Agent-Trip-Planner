from __future__ import annotations

from datetime import date

from pydantic import Field, field_validator

from app.schemas.common import CamelModel, GeoPoint, ProviderRef, VibeScore, vibe_tags


class SpotDiscoverRequest(CamelModel):
    trip_id: str
    city: str
    country: str
    start_date: date
    end_date: date
    vibes: list[str]

    @field_validator("vibes")
    @classmethod
    def _known_vibes(cls, v: list[str]) -> list[str]:
        allowed = set(vibe_tags())
        unknown = [tag for tag in v if tag not in allowed]
        if unknown:
            raise ValueError(f"unknown vibe tags: {unknown}")
        return v


class SpotEvent(CamelModel):
    name: str
    # Field renamed from the wire name "date" to avoid a pydantic
    # postponed-annotation gotcha: a field literally named `date`
    # annotated `date | None` shadows the imported `date` type while
    # pydantic resolves the forward ref, raising
    # "unsupported operand type(s) for |: 'NoneType' and 'NoneType'".
    # `populate_by_name=True` (via CamelModel) plus the explicit alias
    # keeps the wire contract as `"date"` either way.
    event_date: date | None = Field(default=None, alias="date")
    venue: str | None = None


class SpotOption(CamelModel):
    provider_ref: ProviderRef
    name: str
    location: GeoPoint
    rating: float | None = Field(default=None, ge=0, le=5)
    vibe_scores: list[VibeScore]
    matching_event: SpotEvent | None = None
    tag_source: str  # "llm" | "keyword_match" — see ai/AGENT.md discover_spots fallback


class SpotDiscoverResponse(CamelModel):
    trip_id: str
    spots: list[SpotOption]
    fallback_used: bool = False
