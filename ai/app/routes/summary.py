from __future__ import annotations

from fastapi import APIRouter

from app.graphs import build_summary
from app.schemas.summary import SummaryBuildRequest, SummaryBuildResponse

router = APIRouter(tags=["summary"])


@router.post("/build", response_model=SummaryBuildResponse)
async def build(payload: SummaryBuildRequest) -> SummaryBuildResponse:
    return await build_summary.run(payload)
