from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IntegrationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    connection_id: str | None = None
    flow_id: str | None = None
    job_id: str | None = None
    status: str
    message: str
    event_type: str
    operation: str | None = None
    correlation_id: str | None = None
    source_platform: str | None = None
    target_platform: str | None = None
    source_entity: str | None = None
    target_entity: str | None = None
    duration_ms: int | None = None
    error_type: str | None = None
    source_payload_masked: str | None = None
    transformed_payload_masked: str | None = None
    response_payload_masked: str | None = None
    payload_masked: str | None = None
    error_code: str | None = None
    http_status_code: int | None = None
    created_at: datetime
