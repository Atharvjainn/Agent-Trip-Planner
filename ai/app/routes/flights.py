from __future__ import annotations

from fastapi import APIRouter

from app.graphs import search_flights
from app.schemas.flights import FlightSearchRequest, FlightSearchResponse

router = APIRouter(tags=["flights"])


@router.post("/search", response_model=FlightSearchResponse)
async def search(payload: FlightSearchRequest) -> FlightSearchResponse:
    return await search_flights.run(payload)
