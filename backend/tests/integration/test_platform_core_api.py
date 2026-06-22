from __future__ import annotations

from uuid import uuid4

from app.database.session import get_session_factory
from app.models.sync_job import SyncJob
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
            "environment": "homologation",
            "base_url": "https://sankhya.example",
            "credentials": {
                "token": "token-123",
                "appkey": "appkey-456",
                "username": "user",
                "password": "password",
            },
        },
    )
    assert response.status_code == 201
    return response.json()


def test_tenant_crud_and_blocked_delete_when_linked(client):
    tenant = _create_tenant(client)

    list_response = client.get("/api/v1/tenants")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(f"/api/v1/tenants/{tenant['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Tenant A"

    patch_response = client.patch(
        f"/api/v1/tenants/{tenant['id']}",
        json={"status": "inactive", "document": "00000000000000"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "inactive"

    delete_response = client.delete(f"/api/v1/tenants/{tenant['id']}")
    assert delete_response.status_code == 204

    linked_tenant = _create_tenant(client, name="Linked Tenant")
    _create_connection(client, linked_tenant["id"], "Linked Connection")
    blocked_delete = client.delete(f"/api/v1/tenants/{linked_tenant['id']}")
    assert blocked_delete.status_code == 409


def test_flow_mapping_job_run_and_idempotency(client, monkeypatch):
    tenant = _create_tenant(client, name="Flow Tenant")
    source_connection = _create_connection(client, tenant["id"], "Source")
    target_connection = _create_connection(client, tenant["id"], "Target")

    flow_response = client.post(
        "/api/v1/flows",
        json={
            "tenant_id": tenant["id"],
            "name": "Partners Sync",
            "source_connection_id": source_connection["id"],
            "target_connection_id": target_connection["id"],
            "source_entity": "parceiros",
            "target_entity": "partners",
            "trigger_type": "manual",
            "schedule_cron": None,
            "active": True,
        },
    )
    assert flow_response.status_code == 201
    flow = flow_response.json()

    list_response = client.get("/api/v1/flows", params={"tenant_id": tenant["id"]})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    mapping_response = client.post(
        f"/api/v1/flows/{flow['id']}/mappings",
        json={
            "source_field": "name",
            "target_field": "customer_name",
            "transformation_rule": "trim",
            "default_value": None,
            "required": True,
            "active": True,
        },
    )
    assert mapping_response.status_code == 201
    mapping = mapping_response.json()
    assert mapping["tenant_id"] == tenant["id"]

    invalid_mapping_response = client.post(
        f"/api/v1/flows/{flow['id']}/mappings",
        json={
            "source_field": "email",
            "target_field": "email_target",
            "transformation_rule": "not_supported",
            "default_value": None,
            "required": False,
            "active": True,
        },
    )
    assert invalid_mapping_response.status_code == 422

    run_payload = {
        "source_payload": {
            "name": "  ACME Ltda  ",
            "token": "secret-token",
            "password": "secret-password",
        }
    }
    monkeypatch.setattr(
        execute_flow_job, "apply_async", lambda *args, **kwargs: type("Result", (), {"id": "task-123"})()
    )

    run_response = client.post(f"/api/v1/flows/{flow['id']}/run", json=run_payload)
    assert run_response.status_code == 200
    job = run_response.json()
    assert job["status"] == "pending"
    assert job["task_id"] == "task-123"
    assert job["correlation_id"] is not None

    process_flow_job(job["job_id"])

    job_detail_response = client.get(f"/api/v1/jobs/{job['job_id']}")
    assert job_detail_response.status_code == 200
    assert job_detail_response.json()["status"] == "success"

    duplicate_response = client.post(f"/api/v1/flows/{flow['id']}/run", json=run_payload)
    assert duplicate_response.status_code == 200
    duplicate_job = duplicate_response.json()
    assert duplicate_job["status"] == "ignored"

    jobs_response = client.get("/api/v1/jobs", params={"tenant_id": tenant["id"]})
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert [item["status"] for item in jobs] == ["ignored", "success"]

    logs_response = client.get("/api/v1/logs", params={"tenant_id": tenant["id"]})
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) == 2
    assert logs[0]["duration_ms"] is not None
    assert logs[0]["source_platform"] == "sankhya"
    assert logs[0]["target_platform"] == "sankhya"
    assert "secret-token" not in logs[0]["payload_masked"]
    assert "secret-password" not in logs[0]["payload_masked"]

    flow_patch_response = client.patch(f"/api/v1/flows/{flow['id']}", json={"active": False})
    assert flow_patch_response.status_code == 200
    assert flow_patch_response.json()["active"] is False


def test_flow_rejects_cross_tenant_connections(client):
    source_tenant = _create_tenant(client, name="Source Tenant")
    target_tenant = _create_tenant(client, name="Target Tenant")
    source_connection = _create_connection(client, source_tenant["id"], "Source")
    target_connection = _create_connection(client, target_tenant["id"], "Target")

    response = client.post(
        "/api/v1/flows",
        json={
            "tenant_id": source_tenant["id"],
            "name": "Invalid Flow",
            "source_connection_id": source_connection["id"],
            "target_connection_id": target_connection["id"],
            "source_entity": "parceiros",
            "target_entity": "partners",
            "trigger_type": "manual",
            "active": True,
        },
    )
    assert response.status_code == 400


def test_pending_job_can_be_cancelled(client):
    tenant = _create_tenant(client, name="Cancel Tenant")
    source_connection = _create_connection(client, tenant["id"], "Source")
    target_connection = _create_connection(client, tenant["id"], "Target")

    flow_response = client.post(
        "/api/v1/flows",
        json={
            "tenant_id": tenant["id"],
            "name": "Cancel Flow",
            "source_connection_id": source_connection["id"],
            "target_connection_id": target_connection["id"],
            "source_entity": "pedidos",
            "target_entity": "orders",
            "trigger_type": "manual",
            "active": True,
        },
    )
    flow_id = flow_response.json()["id"]

    session = get_session_factory()()
    try:
        pending_job = SyncJob(
            id=str(uuid4()),
            tenant_id=tenant["id"],
            flow_id=flow_id,
            status="pending",
            attempt_count=0,
            max_attempts=3,
            idempotency_key="manual-pending-job",
            source_payload={},
        )
        session.add(pending_job)
        session.commit()
        job_id = pending_job.id
    finally:
        session.close()

    cancel_response = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    detail_response = client.get(f"/api/v1/jobs/{job_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "cancelled"
