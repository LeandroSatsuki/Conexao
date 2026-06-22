from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.connectors.sankhya.schemas import SankhyaAuthResult, SankhyaCredentials

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
}


def strict_mask_payload(value: Any) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS:
                masked[key] = "***"
            else:
                masked[key] = strict_mask_payload(item)
        return masked
    if isinstance(value, list):
        return [strict_mask_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(strict_mask_payload(item) for item in value)
    return value


def build_auth_request_headers(credentials: SankhyaCredentials) -> dict[str, str]:
    headers: dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    if credentials.x_token:
        headers["X-Token"] = credentials.x_token
    return headers


def build_auth_headers(credentials: SankhyaCredentials, token: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def build_auth_payload(credentials: SankhyaCredentials) -> dict[str, str]:
    payload: dict[str, str] = {
        "grant_type": "client_credentials",
    }
    if credentials.client_id:
        payload["client_id"] = credentials.client_id
    if credentials.client_secret:
        payload["client_secret"] = credentials.client_secret
    if credentials.auth_mode == "legacy_appkey_token":
        if credentials.username:
            payload["username"] = credentials.username
        if credentials.password:
            payload["password"] = credentials.password
        if credentials.appkey:
            payload["appkey"] = credentials.appkey
        if credentials.token:
            payload["token"] = credentials.token
    return payload


def build_auth_result(response_data: dict[str, Any], credentials: SankhyaCredentials) -> SankhyaAuthResult:
    access_token = response_data.get("access_token") or response_data.get("token")
    expires_in = response_data.get("expires_in")
    expires_at = None
    if isinstance(expires_in, int):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    return SankhyaAuthResult(
        access_token=str(access_token),
        token_type=str(response_data.get("token_type") or "Bearer"),
        expires_in=expires_in if isinstance(expires_in, int) else None,
        expires_at=expires_at,
        authenticated=True,
        headers=build_auth_headers(credentials, str(access_token)),
        raw_response_masked=strict_mask_payload(response_data),
    )
