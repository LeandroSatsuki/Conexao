from __future__ import annotations

import json

import httpx

from app.connectors.sankhya.client import SankhyaClient
from app.connectors.sankhya.schemas import SankhyaCredentials


def test_sankhya_client_test_connection_uses_mock_transport():
    seen_requests: list[tuple[str, str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append((request.method, request.url.path, request.headers.get("authorization")))
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://sankhya.example")
    sankhya = SankhyaClient(
        credentials=SankhyaCredentials(
            base_url="https://sankhya.example",
            token="token-123",
            appkey="appkey-456",
        ),
        client=client,
    )

    result = sankhya.test_connection()

    assert result["success"] is True
    assert result["status_code"] == 200
    assert seen_requests == [("GET", "/health", "Bearer token-123")]
    sankhya.close()


def test_sankhya_client_authenticate_can_exchange_credentials_for_token():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            body = json.loads(request.content.decode("utf-8"))
            assert body["username"] == "user"
            assert body["password"] == "pass"
            return httpx.Response(200, json={"token": "fresh-token"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://sankhya.example")
    sankhya = SankhyaClient(
        credentials=SankhyaCredentials(
            base_url="https://sankhya.example",
            username="user",
            password="pass",
        ),
        client=client,
    )

    auth = sankhya.authenticate()

    assert auth.authenticated is True
    assert auth.token == "fresh-token"
    assert auth.headers["Authorization"] == "Bearer fresh-token"
    sankhya.close()
