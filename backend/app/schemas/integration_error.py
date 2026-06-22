from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IntegrationErrorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    job_id: str | None = None
    log_id: str | None = None
    error_type: str
    message: str
    details: str | None = None
    created_at: datetime
