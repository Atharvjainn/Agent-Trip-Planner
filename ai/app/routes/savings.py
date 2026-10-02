from __future__ import annotations

from fastapi import APIRouter

from app.graphs import suggest_savings
from app.schemas.savings import SavingsSuggestRequest, SavingsSuggestResponse

router = APIRouter(tags=["savings"])


@router.post("/suggest", response_model=SavingsSuggestResponse)
async def suggest(payload: SavingsSuggestRequest) -> SavingsSuggestResponse:
    return await suggest_savings.run(payload)
