from __future__ import annotations

from fastapi import APIRouter

from app.graphs import recommend_destinations
from app.schemas.destinations import DestinationRecommendRequest, DestinationRecommendResponse

router = APIRouter(tags=["destinations"])


@router.post("/recommend", response_model=DestinationRecommendResponse)
async def recommend(payload: DestinationRecommendRequest) -> DestinationRecommendResponse:
    return await recommend_destinations.run(payload)
