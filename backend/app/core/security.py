from __future__ import annotations

from typing import Any

from app.core.encryption import mask_secret

SENSITIVE_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "password",
    "client_secret",
    "x_token",
    "secret",
    "appkey",
    "api_key",
    "bearer",
    "authorization",
    "cpf",
    "cnpj",
    "cgc",
    "cgc_cpf",
    "cpf_cnpj",
}


def mask_payload(value: Any) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS:
                masked[key] = mask_secret(item)
            else:
                masked[key] = mask_payload(item)
        return masked
    if isinstance(value, list):
        return [mask_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_payload(item) for item in value)
    return value
