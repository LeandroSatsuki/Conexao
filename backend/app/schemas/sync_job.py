from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FlowRunRequest(BaseModel):
    source_payload: dict[str, Any] = Field(default_factory=dict)


class SyncJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    flow_id: str | None = None
    connection_id: str | None = None
    status: str
    attempt_count: int
    max_attempts: int
    idempotency_key: str | None = None
    source_payload: dict[str, Any] | None = None
    transformed_payload: dict[str, Any] | None = None
    response_payload: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SyncJobCancelResponse(BaseModel):
    id: str
    status: str
    message: str
