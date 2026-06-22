from __future__ import annotations

from app.connectors.sankhya.client import SankhyaClient


def test_create_and_list_connections_mask_credentials(client):
    response = client.post(
        "/api/v1/connections",
        json={
            "tenant_id": "tenant-1",
            "tenant_name": "Preferenza",
            "name": "Sankhya Produção",
            "platform": "sankhya",
            "environment": "production",
            "base_url": "https://sankhya.example",
            "credentials": {
                "token": "token-123",
                "appkey": "appkey-456",
                "username": "user",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == "tenant-1"
    assert body["credentials_masked"]["token"] == "***"
    assert body["credentials_masked"]["appkey"] == "***"

    list_response = client.get("/api/v1/connections", params={"tenant_id": "tenant-1"})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_test_connection_creates_log(client, monkeypatch):
    monkeypatch.setattr(
        SankhyaClient,
        "test_connection",
        lambda self, *args, **kwargs: {
            "success": True,
            "status_code": 200,
            "message": "ok",
            "mode": kwargs.get("mode", "mock"),
            "read_check": kwargs.get("read_check", False),
            "operation": "connection_test",
            "details": {"mock": True},
        },
    )

    create_response = client.post(
        "/api/v1/connections",
        json={
            "tenant_id": "tenant-1",
            "name": "Sankhya Homologação",
            "platform": "sankhya",
            "environment": "homologation",
            "base_url": "https://sankhya.example",
            "credentials": {
                "token": "token-123",
                "appkey": "appkey-456",
                "client_secret": "client-secret",
                "x_token": "x-token-789",
            },
        },
    )
    connection_id = create_response.json()["id"]

    test_response = client.post(
        f"/api/v1/connections/{connection_id}/test",
        params={"tenant_id": "tenant-1", "mode": "mock", "read_check": False},
    )

    assert test_response.status_code == 200
    body = test_response.json()
    assert body["success"] is True
    assert body["last_test_status"] == "success"
    assert body["mode"] == "mock"
    assert body["read_check"] is False
    assert body["correlation_id"] is not None

    logs_response = client.get("/api/v1/logs", params={"tenant_id": "tenant-1"})
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) == 1
    assert logs[0]["event_type"] == "connection_test"
    assert logs[0]["operation"] == "connection_test"
    assert logs[0]["status"] == "success"
    assert "token-123" not in logs[0]["payload_masked"]
    assert "client-secret" not in logs[0]["payload_masked"]
    assert "x-token-789" not in logs[0]["payload_masked"]


def test_test_connection_real_mode_calls_connector(client, monkeypatch):
    seen_kwargs: dict[str, object] = {}

    def fake_test_connection(self, *args, **kwargs):
        seen_kwargs.update(kwargs)
        return {
            "success": True,
            "status_code": 200,
            "message": "ok",
            "mode": kwargs.get("mode", "real"),
            "read_check": kwargs.get("read_check", True),
            "operation": "connection_test",
            "details": {"auth": {"authenticated": True}},
        }

    monkeypatch.setattr(SankhyaClient, "test_connection", fake_test_connection)

    create_response = client.post(
        "/api/v1/connections",
        json={
            "tenant_id": "tenant-1",
            "name": "Sankhya Homologação",
            "platform": "sankhya",
            "environment": "sandbox",
            "base_url": "https://api.sandbox.sankhya.com.br",
            "credentials": {
                "client_id": "client-id",
                "client_secret": "client-secret",
                "x_token": "x-token-789",
                "auth_mode": "oauth_client_credentials",
            },
        },
    )
    connection_id = create_response.json()["id"]

    test_response = client.post(
        f"/api/v1/connections/{connection_id}/test",
        params={"tenant_id": "tenant-1", "mode": "real", "read_check": True},
    )

    assert test_response.status_code == 200
    body = test_response.json()
    assert body["mode"] == "real"
    assert body["read_check"] is True
    assert seen_kwargs["mode"] == "real"
    assert seen_kwargs["read_check"] is True
