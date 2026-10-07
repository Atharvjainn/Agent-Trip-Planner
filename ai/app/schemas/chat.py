from __future__ import annotations

from typing import Any, Optional
from pydantic import Field
from app.schemas.common import CamelModel, GeoPoint


class ChatRequest(CamelModel):
    trip_id: str = Field(..., description="Caller-provided trip ID from main backend")
    message: str = Field(..., description="User chat message")
    session_id: Optional[str] = Field(None, description="Optional session identifier, defaults to trip_id")
    user_id: Optional[str] = Field(None, description="Optional user ID")
    user_location: Optional[GeoPoint] = Field(None, description="Optional current GPS location of user")
    existing_state: Optional[dict[str, Any]] = Field(None, description="Optional pre-existing trip state")


class TurnResponseModel(CamelModel):
    reply: str
    stage: str
    ui_component: str
    options: list[dict[str, Any]] = Field(default_factory=list)
    requires_user_input: bool
    input_type: str


class ChatMetricsModel(CamelModel):
    total_ms: float
    routing_ms: Optional[float] = None
    graph_exec_ms: float


class ChatResponse(CamelModel):
    trip_id: str
    session_id: str
    conversation_stage: str
    trip_status: str = Field(..., description="Canonical TripStatus mapped from conversation_stage and trip state")
    turn_response: TurnResponseModel
    state_summary: dict[str, Any] = Field(default_factory=dict)
    metrics: Optional[ChatMetricsModel] = None
