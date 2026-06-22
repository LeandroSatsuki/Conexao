from __future__ import annotations

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class SankhyaCredentials(BaseModel):
    model_config = ConfigDict(extra="allow")

    base_url: AnyHttpUrl | str
    appkey: str | None = None
    token: str | None = None
    username: str | None = None
    password: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    environment: str = "production"
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    auth_path: str = "/auth/login"
    health_path: str = "/health"
    query_path: str = "/query"
    record_path: str = "/records"
    logout_path: str = "/logout"


class SankhyaAuthResult(BaseModel):
    token: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    authenticated: bool = False
