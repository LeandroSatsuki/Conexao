from __future__ import annotations

import httpx

from app.connectors.sankhya.client import SankhyaClient
from app.connectors.sankhya.schemas import SankhyaCredentials
from app.workers.tasks import execute_flow_job, process_flow_job


def _create_tenant(client, name: str = "Tenant A", document: str = "12345678000190") -> dict[str, object]:
    response = client.post(
        "/api/v1/tenants",
        json={"name": name, "document": document, "status": "active"},
    )
    assert response.status_code == 201
    return response.json()


def _create_connection(client, tenant_id: str, name: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/connections",
        json={
            "tenant_id": tenant_id,
            "name": name,
            "platform": "sankhya",
            "environment": "sandbox",
            "base_url": "https://api.sandbox.sankhya.com.br",
            "credentials": {
                "client_id": "client-id",
                "client_secret": "client-secret",
                "x_token": "x-token-789",
                "auth_mode": "oauth_client_credentials",
                "verify_ssl": True,
            },
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_read_only_flow(
    client,
    tenant_id: str,
    source_connection_id: str,
    target_connection_id: str,
    *,
    mode: str,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/flows",
        json={
            "tenant_id": tenant_id,
            "name": "Sankhya Read Only Flow",
            "source_connection_id": source_connection_id,
            "target_connection_id": target_connection_id,
            "source_entity": "Parceiro",
            "target_entity": "PartnerMirror",
            "config_json": {
                "operation": "sankhya_load_records",
                "entity_name": "Parceiro",
                "fields": ["CODPARC", "NOMEPARC", "CGC_CPF"],
                "criteria": None,
                "limit": 10,
                "mode": mode,
            },
            "trigger_type": "manual",
            "active": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_mapping(client, flow_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/flows/{flow_id}/mappings",
        json={
            "source_field": "NOMEPARC",
            "target_field": "customer_name",
            "transformation_rule": "trim",
            "default_value": None,
            "required": True,
            "active": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def _build_real_sankhya_connector() -> SankhyaClient:
    credentials = SankhyaCredentials(
        base_url="https://api.sandbox.sankhya.com.br",
        environment="sandbox",
        auth_mode="oauth_client_credentials",
        client_id="client-id",
        client_secret="client-secret",
        x_token="x-token-789",
        timeout_seconds=5,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/authenticate":
            return httpx.Response(200, json={"access_token": "access-123", "expires_in": 60})
        if request.url.path == "/gateway/v1/mge/service.sbr":
            return httpx.Response(
                200,
                json={
                    "responseBody": {
                        "entities": [
                            {
                                "CODPARC": "1",
                                "NOMEPARC": "  ACME Ltda  ",
                                "CGC_CPF": "12345678901",
                            }
                        ]
                    }
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url=str(credentials.base_url))
    return SankhyaClient(credentials=credentials, client=client)


def test_sankhya_read_only_flow_mock_mode_processes_as_success(client, monkeypatch):
    tenant = _create_tenant(client, name="Read Mock Tenant")
    source_connection = _create_connection(client, tenant["id"], "Source")
    target_connection = _create_connection(client, tenant["id"], "Target")
    flow = _create_read_only_flow(
        client,
        tenant["id"],
        source_connection["id"],
        target_connection["id"],
        mode="mock",
    )
    _create_mapping(client, flow["id"])

    monkeypatch.setattr(
        execute_flow_job, "apply_async", lambda *args, **kwargs: type("Result", (), {"id": "task-mock"})()
    )

    run_response = client.post(f"/api/v1/flows/{flow['id']}/run", json={"source_payload": {}})
    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["status"] == "pending"
    assert run_body["task_id"] == "task-mock"

    process_flow_job(run_body["job_id"])

    job_response = client.get(f"/api/v1/jobs/{run_body['job_id']}")
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "success"
    assert job["records_count"] == 1
    assert job["response_payload"]["mode"] == "mock"
    assert job["transformed_payload"]["records"][0]["customer_name"] == "mock-nomeparc"

    logs_response = client.get("/api/v1/logs", params={"tenant_id": tenant["id"]})
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) == 1
    assert logs[0]["operation"] == "sankhya_load_records"
    assert logs[0]["mode"] == "mock"
    assert logs[0]["records_count"] == 1


def test_sankhya_read_only_flow_real_mode_processes_with_mock_http(client, monkeypatch):
    tenant = _create_tenant(client, name="Read Real Tenant")
    source_connection = _create_connection(client, tenant["id"], "Source")
    target_connection = _create_connection(client, tenant["id"], "Target")
    flow = _create_read_only_flow(
        client,
        tenant["id"],
        source_connection["id"],
        target_connection["id"],
        mode="real",
    )
    _create_mapping(client, flow["id"])

    monkeypatch.setattr(
        "app.integrations.runner.build_connector_from_connection",
        lambda connection: _build_real_sankhya_connector(),
    )
    monkeypatch.setattr(
        execute_flow_job, "apply_async", lambda *args, **kwargs: type("Result", (), {"id": "task-real"})()
    )

    run_response = client.post(f"/api/v1/flows/{flow['id']}/run", json={"source_payload": {}})
    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["status"] == "pending"
    assert run_body["task_id"] == "task-real"

    process_flow_job(run_body["job_id"])

    job_response = client.get(f"/api/v1/jobs/{run_body['job_id']}")
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "success"
    assert job["records_count"] == 1
    assert job["response_payload"]["records_count"] == 1
    assert job["response_payload"]["records"][0]["CGC_CPF"] != "12345678901"
    assert job["transformed_payload"]["records"][0]["customer_name"] == "ACME Ltda"

    logs_response = client.get("/api/v1/logs", params={"tenant_id": tenant["id"]})
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) == 1
    assert logs[0]["operation"] == "sankhya_load_records"
    assert logs[0]["mode"] == "real"
    assert logs[0]["records_count"] == 1
    payload_masked = logs[0]["payload_masked"]
    assert "client-secret" not in payload_masked
    assert "x-token-789" not in payload_masked
    assert "access-123" not in payload_masked
