from __future__ import annotations

import json
from typing import Any

from app.connectors.sankhya.client import SankhyaClient
from app.connectors.sankhya.schemas import SankhyaCredentials
from app.core.encryption import decrypt_secret
from app.models.connection import Connection


def decode_credentials(connection: Connection) -> SankhyaCredentials:
    raw = decrypt_secret(connection.credentials_encrypted)
    data = json.loads(raw) if raw else {}
    data.setdefault("base_url", connection.base_url)
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
        masked: dict[str, Any] = {}
        for key, value in data.items():
            if key.lower() in {"token", "password", "client_secret", "appkey"}:
                masked[key] = "***"
            else:
                masked[key] = value
        return masked
    except Exception:
        return {"credentials": "***"}
