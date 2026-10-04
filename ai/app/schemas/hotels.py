from __future__ import annotations

from pydantic import Field

from app.schemas.common import CamelModel, GeoPoint, Money, ProviderRef


class SelectedSpotInput(CamelModel):
    """Minimal spot shape the hotel graph needs — not the full SpotOption."""

    id: str
    name: str
    location: GeoPoint


class HotelSearchRequest(CamelModel):
    trip_id: str
    city: str
    selected_spots: list[SelectedSpotInput] = Field(min_length=1)
    stay_budget: Money
    nights: int = Field(ge=1)


class SpotDistance(CamelModel):
    spot_id: str
    spot_name: str
    distance_km: float = Field(ge=0)


class HotelOption(CamelModel):
    provider_ref: ProviderRef
    name: str
    location: GeoPoint
    price_per_night: Money
    rating: float | None = Field(default=None, ge=0, le=5)
    review_snippet: str | None = None
    distances: list[SpotDistance]
    score: float = Field(ge=0, le=1)


class HotelSearchResponse(CamelModel):
    trip_id: str
    options: list[HotelOption] = Field(max_length=15)
    fallback_used: bool = False
