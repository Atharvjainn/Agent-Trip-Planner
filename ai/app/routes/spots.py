from __future__ import annotations

from fastapi import APIRouter

from app.graphs import discover_spots
from app.schemas.spots import SpotDiscoverRequest, SpotDiscoverResponse

router = APIRouter(tags=["spots"])


@router.post("/discover", response_model=SpotDiscoverResponse)
async def discover(payload: SpotDiscoverRequest) -> SpotDiscoverResponse:
    return await discover_spots.run(payload)
