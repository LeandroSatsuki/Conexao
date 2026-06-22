from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TenantBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    document: str | None = Field(default=None, max_length=30)
    status: str = Field(default="active")


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    document: str | None = Field(default=None, max_length=30)
    status: str | None = Field(default=None)


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    document: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
