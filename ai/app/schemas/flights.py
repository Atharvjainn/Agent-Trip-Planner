from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from app.schemas.common import CamelModel, Money, ProviderRef


class FlightSearchRequest(CamelModel):
    trip_id: str
    source: str
    destination: str
    start_date: date
    end_date: date
    travelers: int = Field(ge=1)
    flights_budget: Money


class FlightLeg(CamelModel):
    airline: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departs_at: datetime
    arrives_at: datetime


class FlightOption(CamelModel):
    provider_ref: ProviderRef
    outbound: list[FlightLeg]
    inbound: list[FlightLeg] = Field(default_factory=list)
    price: Money
    stops: int = Field(ge=0)
    total_duration_minutes: int = Field(ge=0)


class FlightSearchResponse(CamelModel):
    trip_id: str
    options: list[FlightOption] = Field(max_length=10)
    fallback_used: bool = False
