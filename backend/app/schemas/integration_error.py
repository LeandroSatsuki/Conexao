from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IntegrationErrorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    flow_id: str | None = None
    job_id: str | None = None
    log_id: str | None = None
    error_type: str
    error_message: str
    normalized_message: str
    raw_error_masked: str | None = None
    retryable: bool = False
    correlation_id: str | None = None
    created_at: datetime
