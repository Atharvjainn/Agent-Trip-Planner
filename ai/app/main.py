"""
Internal HTTP endpoints called by apps/api worker.
"""
from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from pathlib import Path
import sys

_ai_dir = str(Path(__file__).resolve().parent.parent)
if _ai_dir not in sys.path:
    sys.path.insert(0, _ai_dir)

from app.config import get_settings
from app.routes import budget, chat, destinations, flights, hotels, savings, spots, summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("services.ai.main")

app = FastAPI(title="Travel & Local Discovery -- AI service", version="0.1.0")


async def require_internal_key(x_internal_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not x_internal_key or x_internal_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing X-Internal-Key"
        )


internal_router_dependencies = [Depends(require_internal_key)]

app.include_router(chat.router, dependencies=internal_router_dependencies)
app.include_router(
    destinations.router, prefix="/internal/destinations", dependencies=internal_router_dependencies
)
app.include_router(budget.router, prefix="/internal/budget", dependencies=internal_router_dependencies)
app.include_router(spots.router, prefix="/internal/spots", dependencies=internal_router_dependencies)
app.include_router(flights.router, prefix="/internal/flights", dependencies=internal_router_dependencies)
app.include_router(hotels.router, prefix="/internal/hotels", dependencies=internal_router_dependencies)
app.include_router(savings.router, prefix="/internal/savings", dependencies=internal_router_dependencies)
app.include_router(summary.router, prefix="/internal/summary", dependencies=internal_router_dependencies)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc: ValidationError) -> JSONResponse:
    logger.error("response_validation_failed", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "internal_schema_validation_failed"})
