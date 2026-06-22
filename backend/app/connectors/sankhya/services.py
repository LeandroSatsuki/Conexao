from __future__ import annotations

import json
from typing import Any

from app.connectors.sankhya.auth import strict_mask_payload
from app.connectors.sankhya.catalog import (
    SankhyaReadOperationDefinition,
    SankhyaReadOperationResolution,
    get_read_operation,
    list_read_operations,
    validate_read_operation_resolution,
)
from app.connectors.sankhya.catalog import (
    resolve_read_operation_request as _resolve_read_operation_request,
)
from app.connectors.sankhya.client import SankhyaClient
from app.connectors.sankhya.schemas import SankhyaCredentials, SankhyaReadOperationConfig
from app.core.config import get_settings
from app.core.encryption import decrypt_secret
from app.models.connection import Connection


def decode_credentials(connection: Connection) -> SankhyaCredentials:
    raw = decrypt_secret(connection.credentials_encrypted)
    data = json.loads(raw) if raw else {}
    settings = get_settings()
    data.setdefault("base_url", connection.base_url)
    data.setdefault("environment", connection.environment or settings.sankhya_default_environment)
    data.setdefault("timeout_seconds", settings.sankhya_auth_timeout_seconds)
    data.setdefault("verify_ssl", True)
    data.setdefault("auth_mode", "oauth_client_credentials")
    return SankhyaCredentials.model_validate(data)


def build_connector_from_connection(connection: Connection) -> SankhyaClient:
    credentials = decode_credentials(connection)
    return SankhyaClient(credentials=credentials)


def mask_connection_credentials(connection: Connection) -> dict[str, Any] | None:
    try:
        raw = decrypt_secret(connection.credentials_encrypted)
        if not raw:
            return None
        data = json.loads(raw)
        return strict_mask_payload(data)
    except Exception:
        return {"credentials": "***"}


def extract_read_operation_config(
    config_json: dict[str, Any] | None,
    *,
    source_entity: str | None = None,
) -> SankhyaReadOperationConfig | None:
    resolution = _resolve_read_operation_request(config_json, source_entity=source_entity)
    if resolution is None:
        return None
    return resolution.config


def resolve_read_operation_request(
    config_json: dict[str, Any] | None,
    *,
    source_entity: str | None = None,
) -> SankhyaReadOperationResolution | None:
    return _resolve_read_operation_request(config_json, source_entity=source_entity)


def get_catalog_read_operation(operation_name: str) -> SankhyaReadOperationDefinition | None:
    return get_read_operation(operation_name)


def list_catalog_read_operations() -> list[SankhyaReadOperationDefinition]:
    return list_read_operations()


def validate_catalog_read_operation(
    resolution: SankhyaReadOperationResolution,
    *,
    connection_environment: str | None = None,
) -> list[str]:
    return validate_read_operation_resolution(resolution, connection_environment=connection_environment)
