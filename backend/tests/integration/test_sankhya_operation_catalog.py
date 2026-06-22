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


def _create_catalog_flow(
    client,
    *,
    tenant_id: str,
    source_connection_id: str,
    target_connection_id: str,
    operation_name: str,
    fields: list[str] | None,
    limit: int,
    mode: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "tenant_id": tenant_id,
        "name": operation_name,
        "source_connection_id": source_connection_id,
        "target_connection_id": target_connection_id,
        "source_entity": {
            "sankhya_read_partner": "Parceiro",
            "sankhya_read_product": "Produto",
            "sankhya_read_seller": "Vendedor",
            "sankhya_read_company": "Empresa",
        }[operation_name],
        "target_entity": "InternalMirror",
        "config_json": {
            "operation": operation_name,
            "fields": fields,
            "criteria": None,
            "limit": limit,
            "mode": mode,
        },
        "trigger_type": "manual",
        "active": True,
    }
    response = client.post("/api/v1/flows", json=payload)
    assert response.status_code == 201
    return response.json()


def _create_partner_mapping(client, flow_id: str) -> dict[str, object]:
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


def _build_real_partner_connector() -> SankhyaClient:
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
                                "TIPPESSOA": "J",
                            }
                        ]
                    }
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=str(credentials.base_url))
    return SankhyaClient(credentials=credentials, client=client)


def _build_real_product_connector() -> SankhyaClient:
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
                                "CODPROD": "1",
                                "DESCRPROD": "Produto 1",
                                "REFERENCIA": "REF-1",
                                "MARCA": "Marca 1",
                                "ATIVO": "S",
                            }
                        ]
                    }
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=str(credentials.base_url))
    return SankhyaClient(credentials=credentials, client=client)


def test_list_and_get_sankhya_read_operations(client):
    response = client.get("/api/v1/connectors/sankhya/read-operations")
    assert response.status_code == 200
    operations = response.json()
    assert {item["operation_name"] for item in operations} == {
        "sankhya_read_partner",
        "sankhya_read_product",
        "sankhya_read_seller",
        "sankhya_read_company",
    }

    detail_response = client.get("/api/v1/connectors/sankhya/read-operations/sankhya_read_partner")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["entity_name"] == "Parceiro"
    assert "CGC_CPF" in detail["allowed_fields"]
    assert detail["production_allowed"] is False


def test_validate_catalog_partner_flow_and_block_invalid_inputs(client):
    tenant = _create_tenant(client, name="Catalog Tenant")
    source_connection = _create_connection(client, tenant["id"], "Source")
    target_connection = _create_connection(client, tenant["id"], "Target")

    flow = _create_catalog_flow(
        client,
        tenant_id=tenant["id"],
        source_connection_id=source_connection["id"],
        target_connection_id=target_connection["id"],
        operation_name="sankhya_read_partner",
        fields=["CODPARC", "NOMEPARC", "CGC_CPF"],
        limit=10,
        mode="mock",
    )

    validate_response = client.post(f"/api/v1/flows/{flow['id']}/validate")
    assert validate_response.status_code == 200
    validate_body = validate_response.json()
    assert validate_body["valid"] is True
    assert "operation=sankhya_read_partner" in validate_body["details"]

    invalid_field_response = client.post(
        "/api/v1/flows",
        json={
            "tenant_id": tenant["id"],
            "name": "Invalid Field Flow",
            "source_connection_id": source_connection["id"],
            "target_connection_id": target_connection["id"],
            "source_entity": "Parceiro",
            "target_entity": "InternalMirror",
            "config_json": {
                "operation": "sankhya_read_partner",
                "fields": ["CODPARC", "NOMEPARC", "INVALID"],
                "criteria": None,
                "limit": 10,
                "mode": "mock",
            },
            "trigger_type": "manual",
            "active": True,
        },
    )
    assert invalid_field_response.status_code == 400
    assert "Fields not allowed" in invalid_field_response.json()["detail"]

    invalid_limit_response = client.post(
        "/api/v1/flows",
        json={
            "tenant_id": tenant["id"],
            "name": "Invalid Limit Flow",
            "source_connection_id": source_connection["id"],
            "target_connection_id": target_connection["id"],
            "source_entity": "Parceiro",
            "target_entity": "InternalMirror",
            "config_json": {
                "operation": "sankhya_read_partner",
                "fields": ["CODPARC", "NOMEPARC"],
                "criteria": None,
                "limit": 51,
                "mode": "mock",
            },
            "trigger_type": "manual",
            "active": True,
        },
    )
    assert invalid_limit_response.status_code == 400
    assert "less than or equal to 50" in invalid_limit_response.json()["detail"]


def test_catalog_partner_flow_mock_executes(client, monkeypatch):
    tenant = _create_tenant(client, name="Partner Mock Tenant")
    source_connection = _create_connection(client, tenant["id"], "Source")
    target_connection = _create_connection(client, tenant["id"], "Target")
    flow = _create_catalog_flow(
        client,
        tenant_id=tenant["id"],
        source_connection_id=source_connection["id"],
        target_connection_id=target_connection["id"],
        operation_name="sankhya_read_partner",
        fields=["CODPARC", "NOMEPARC", "CGC_CPF"],
        limit=10,
        mode="mock",
    )
    _create_partner_mapping(client, flow["id"])

    monkeypatch.setattr(
        execute_flow_job, "apply_async", lambda *args, **kwargs: type("Result", (), {"id": "task-mock"})()
    )

    run_response = client.post(f"/api/v1/flows/{flow['id']}/run", json={"source_payload": {}})
    assert run_response.status_code == 200
    body = run_response.json()
    assert body["status"] == "pending"
    assert body["task_id"] == "task-mock"

    process_flow_job(body["job_id"])

    job_response = client.get(f"/api/v1/jobs/{body['job_id']}")
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "success"
    assert job["records_count"] == 1
    assert job["response_payload"]["operation"] == "sankhya_read_partner"
    assert job["response_payload"]["records"][0]["CGC_CPF"] == "***"
    assert job["transformed_payload"]["records"][0]["customer_name"] == "mock-nomeparc"

    logs_response = client.get("/api/v1/logs", params={"tenant_id": tenant["id"]})
    assert logs_response.status_code == 200
    log = logs_response.json()[0]
    assert log["operation"] == "sankhya_read_partner"
    assert log["mode"] == "mock"
    assert log["records_count"] == 1
    assert "12345678901" not in log["response_payload_masked"]


def test_catalog_partner_flow_real_executes_with_mock_http(client, monkeypatch):
    tenant = _create_tenant(client, name="Partner Real Tenant")
    source_connection = _create_connection(client, tenant["id"], "Source")
    target_connection = _create_connection(client, tenant["id"], "Target")
    flow = _create_catalog_flow(
        client,
        tenant_id=tenant["id"],
        source_connection_id=source_connection["id"],
        target_connection_id=target_connection["id"],
        operation_name="sankhya_read_partner",
        fields=["CODPARC", "NOMEPARC", "CGC_CPF"],
        limit=10,
        mode="real",
    )
    _create_partner_mapping(client, flow["id"])

    monkeypatch.setattr(
        "app.integrations.runner.build_connector_from_connection",
        lambda connection: _build_real_partner_connector(),
    )
    monkeypatch.setattr(
        execute_flow_job, "apply_async", lambda *args, **kwargs: type("Result", (), {"id": "task-real"})()
    )

    run_response = client.post(f"/api/v1/flows/{flow['id']}/run", json={"source_payload": {}})
    assert run_response.status_code == 200
    body = run_response.json()
    assert body["status"] == "pending"
    assert body["task_id"] == "task-real"

    process_flow_job(body["job_id"])

    job_response = client.get(f"/api/v1/jobs/{body['job_id']}")
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "success"
    assert job["response_payload"]["operation"] == "sankhya_read_partner"
    assert job["response_payload"]["records"][0]["CGC_CPF"] == "***"
    assert job["transformed_payload"]["records"][0]["customer_name"] == "ACME Ltda"

    logs_response = client.get("/api/v1/logs", params={"tenant_id": tenant["id"]})
    assert logs_response.status_code == 200
    log = logs_response.json()[0]
    assert log["operation"] == "sankhya_read_partner"
    assert log["mode"] == "real"
    assert "client-secret" not in log["payload_masked"]
    assert "x-token-789" not in log["payload_masked"]


def test_catalog_product_flow_without_sensitive_fields(client, monkeypatch):
    tenant = _create_tenant(client, name="Product Tenant")
    source_connection = _create_connection(client, tenant["id"], "Source")
    target_connection = _create_connection(client, tenant["id"], "Target")
    flow = _create_catalog_flow(
        client,
        tenant_id=tenant["id"],
        source_connection_id=source_connection["id"],
        target_connection_id=target_connection["id"],
        operation_name="sankhya_read_product",
        fields=["CODPROD", "DESCRPROD", "ATIVO"],
        limit=10,
        mode="mock",
    )

    monkeypatch.setattr(
        execute_flow_job, "apply_async", lambda *args, **kwargs: type("Result", (), {"id": "task-product"})()
    )

    run_response = client.post(f"/api/v1/flows/{flow['id']}/run", json={"source_payload": {}})
    assert run_response.status_code == 200
    body = run_response.json()
    assert body["task_id"] == "task-product"

    process_flow_job(body["job_id"])

    job_response = client.get(f"/api/v1/jobs/{body['job_id']}")
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "success"
    assert job["response_payload"]["records"][0]["CODPROD"] == "mock-codprod"
    assert job["response_payload"]["records"][0]["DESCRPROD"] == "mock-descrprod"
