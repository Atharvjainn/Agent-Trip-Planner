from __future__ import annotations

from fastapi import APIRouter

from app.graphs import estimate_budget
from app.schemas.budget import BudgetEstimateRequest, BudgetEstimateResponse

router = APIRouter(tags=["budget"])


@router.post("/estimate", response_model=BudgetEstimateResponse)
async def estimate(payload: BudgetEstimateRequest) -> BudgetEstimateResponse:
    return await estimate_budget.run(payload)
