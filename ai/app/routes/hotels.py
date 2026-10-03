from __future__ import annotations

from fastapi import APIRouter

from app.graphs import search_hotels
from app.schemas.hotels import HotelSearchRequest, HotelSearchResponse

router = APIRouter(tags=["hotels"])


@router.post("/search", response_model=HotelSearchResponse)
async def search(payload: HotelSearchRequest) -> HotelSearchResponse:
    return await search_hotels.run(payload)
