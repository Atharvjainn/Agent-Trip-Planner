from __future__ import annotations

from app.schemas.common import CamelModel, GeoPoint, Money
from app.schemas.hotels import SelectedSpotInput


class SummaryBuildRequest(CamelModel):
    trip_id: str
    city: str
    hotel_location: GeoPoint
    selected_spots: list[SelectedSpotInput]
    flight_price: Money
    hotel_total_price: Money
    nights: int


class CommuteEstimate(CamelModel):
    daily_distance_km: float
    daily_cost: Money
    trip_total_cost: Money
    mode: str  # auto | cab | metro | walk


class SummaryBuildResponse(CamelModel):
    trip_id: str
    narrative: str
    commute: CommuteEstimate
    fallback_used: bool = False
