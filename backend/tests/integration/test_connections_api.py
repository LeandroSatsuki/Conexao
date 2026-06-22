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
        lambda self: {"success": True, "status_code": 200, "message": "ok", "details": {}},
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
            },
        },
    )
    connection_id = create_response.json()["id"]

    test_response = client.post(
        f"/api/v1/connections/{connection_id}/test",
        params={"tenant_id": "tenant-1"},
    )

    assert test_response.status_code == 200
    body = test_response.json()
    assert body["success"] is True
    assert body["last_test_status"] == "success"

    logs_response = client.get("/api/v1/logs", params={"tenant_id": "tenant-1"})
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) == 1
    assert logs[0]["event_type"] == "connection_test"
    assert logs[0]["status"] == "success"
