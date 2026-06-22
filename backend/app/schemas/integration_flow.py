from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FlowTriggerType = Literal["manual", "scheduled"]


class IntegrationFlowBase(BaseModel):
    tenant_id: str
    name: str
    source_connection_id: str
    target_connection_id: str
    source_entity: str
    target_entity: str
    config_json: dict[str, Any] | None = None
    trigger_type: FlowTriggerType
    schedule_cron: str | None = None
    active: bool = True


class IntegrationFlowCreate(IntegrationFlowBase):
    pass


class IntegrationFlowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    source_connection_id: str | None = None
    target_connection_id: str | None = None
    source_entity: str | None = None
    target_entity: str | None = None
    config_json: dict[str, Any] | None = None
    trigger_type: FlowTriggerType | None = None
    schedule_cron: str | None = None
    active: bool | None = None


class IntegrationFlowRead(IntegrationFlowBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
