from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


class SankhyaCredentials(BaseModel):
    model_config = ConfigDict(extra="allow")

    base_url: AnyHttpUrl | str
    environment: Literal["sandbox", "production"] | str = "sandbox"
    auth_mode: Literal["oauth_client_credentials", "legacy_appkey_token"] = "oauth_client_credentials"
    client_id: str | None = None
    client_secret: str | None = None
    x_token: str | None = None
    appkey: str | None = None
    token: str | None = None
    username: str | None = None
    password: str | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    verify_ssl: bool = True
    auth_path: str = "/authenticate"
    gateway_path: str = "/gateway/v1/mge/service.sbr"
    health_path: str = "/health"
    query_path: str = "/query"
    record_path: str = "/records"
    logout_path: str = "/logout"

    @field_validator("environment", mode="before")
    @classmethod
    def _normalize_environment(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"sandbox", "production"}:
            return normalized
        if normalized in {"homologation", "homologacao", "homologação"}:
            return "sandbox"
        raise ValueError("environment must be sandbox or production")


class SankhyaReadOperationConfig(BaseModel):
    operation: str = Field(default="sankhya_load_records", min_length=1)
    entity_name: str = Field(min_length=1)
    fields: list[str] = Field(min_length=1)
    criteria: dict[str, Any] | str | None = None
    limit: int = Field(default=10, ge=1, le=50)
    mode: Literal["mock", "real"] = "mock"

    @field_validator("operation", mode="before")
    @classmethod
    def _normalize_operation(cls, value: Any) -> str:
        return str(value or "").strip()

    @model_validator(mode="after")
    def _validate_fields(self) -> SankhyaReadOperationConfig:
        self.operation = self.operation.strip()
        cleaned_fields = [field.strip() for field in self.fields if field.strip()]
        if not cleaned_fields:
            raise ValueError("fields must not be empty")
        self.fields = cleaned_fields
        return self


class SankhyaAuthResult(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    expires_at: datetime | None = None
    authenticated: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    raw_response_masked: dict[str, Any] = Field(default_factory=dict)


class SankhyaConnectionTestResult(BaseModel):
    success: bool
    status_code: int
    message: str
    connection_id: str | None = None
    tenant_id: str | None = None
    platform: str = "sankhya"
    status: str = "inactive"
    last_test_status: str = "failed"
    operation: str = "connection_test"
    mode: Literal["mock", "real"] = "mock"
    read_check: bool = False
    correlation_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    log_id: str | None = None


class SankhyaReadOperationResult(BaseModel):
    success: bool = True
    operation: str = "sankhya_load_records"
    mode: Literal["mock", "real"] = "mock"
    entity_name: str
    fields: list[str] = Field(default_factory=list)
    criteria: dict[str, Any] | str | None = None
    limit: int = 10
    records_count: int = 0
    records: list[dict[str, Any]] = Field(default_factory=list)
    raw_response_masked: dict[str, Any] = Field(default_factory=dict)


class SankhyaError(BaseModel):
    error_type: str
    message: str
    normalized_message: str
    retryable: bool = False
    raw_error_masked: dict[str, Any] | str | None = None
    http_status_code: int | None = None
    correlation_id: str | None = None
