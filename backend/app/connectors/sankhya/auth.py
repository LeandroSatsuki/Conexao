from __future__ import annotations

from typing import Any

from app.connectors.sankhya.schemas import SankhyaCredentials


def build_auth_headers(credentials: SankhyaCredentials, token: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json", "Content-Type": "application/json"}
    resolved_token = token or credentials.token
    if resolved_token:
        headers["Authorization"] = f"Bearer {resolved_token}"
    if credentials.appkey:
        headers["appkey"] = credentials.appkey
    if credentials.client_id:
        headers["X-Client-Id"] = credentials.client_id
    if credentials.client_secret:
        headers["X-Client-Secret"] = credentials.client_secret
    return headers


def build_auth_payload(credentials: SankhyaCredentials) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if credentials.username:
        payload["username"] = credentials.username
    if credentials.password:
        payload["password"] = credentials.password
    if credentials.client_id:
        payload["client_id"] = credentials.client_id
    if credentials.client_secret:
        payload["client_secret"] = credentials.client_secret
    if credentials.appkey:
        payload["appkey"] = credentials.appkey
    return payload
