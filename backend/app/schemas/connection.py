from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConnectionCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    tenant_name: str | None = Field(default="Preferenza")
    name: str = Field(min_length=1, max_length=200)
    platform: str = Field(min_length=1, max_length=100)
    environment: str = Field(default="production", max_length=50)
    base_url: str = Field(min_length=1, max_length=500)
    credentials: dict[str, Any] = Field(default_factory=dict)


class ConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    platform: str
    environment: str
    base_url: str
    status: str
    last_test_status: str | None = None
    last_test_at: datetime | None = None
    credentials_masked: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    connection_id: str
    tenant_id: str
    platform: str
    status: str
    last_test_status: str
    log_id: str | None = None
