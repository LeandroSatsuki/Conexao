from __future__ import annotations

from uuid import uuid4

from app.connectors.sankhya.exceptions import SankhyaTimeoutError
from app.database.session import get_session_factory
from app.integrations.runner import IntegrationRunner
from app.models.field_mapping import FieldMapping
from app.models.integration_error import IntegrationError
from app.models.integration_log import IntegrationLog
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


def _create_flow(client, tenant_id: str, source_connection_id: str, target_connection_id: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/flows",
        json={
            "tenant_id": tenant_id,
            "name": "Async Sync",
            "source_connection_id": source_connection_id,
            "target_connection_id": target_connection_id,
            "source_entity": "parceiros",
            "target_entity": "partners",
            "trigger_type": "manual",
            "active": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_mapping(
    client, flow_id: str, source_field: str = "name", target_field: str = "customer_name"
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/flows/{flow_id}/mappings",
        json={
            "source_field": source_field,
            "target_field": target_field,
            "transformation_rule": "trim",
            "default_value": None,
            "required": True,
            "active": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_async_flow_run_processes_job_and_keeps_correlation_id(client, monkeypatch):
    tenant = _create_tenant(client, name="Async Tenant")
    source_connection = _create_connection(client, tenant["id"], "Source")
    target_connection = _create_connection(client, tenant["id"], "Target")
    flow = _create_flow(client, tenant["id"], source_connection["id"], target_connection["id"])
    _create_mapping(client, flow["id"])

    monkeypatch.setattr(
        execute_flow_job, "apply_async", lambda *args, **kwargs: type("Result", (), {"id": "task-123"})()
    )

    run_response = client.post(
        f"/api/v1/flows/{flow['id']}/run",
        json={"source_payload": {"name": "  ACME Ltda  ", "token": "secret-token"}},
    )
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["status"] == "pending"
    assert payload["task_id"] == "task-123"
    assert payload["correlation_id"] is not None

    process_flow_job(payload["job_id"])

    job_response = client.get(f"/api/v1/jobs/{payload['job_id']}")
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "success"
    assert job["correlation_id"] == payload["correlation_id"]
    assert job["transformed_payload"]["customer_name"] == "ACME Ltda"

    logs_response = client.get("/api/v1/logs", params={"tenant_id": tenant["id"]})
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) == 1
    assert logs[0]["correlation_id"] == payload["correlation_id"]
    assert "secret-token" not in logs[0]["payload_masked"]


def test_process_flow_job_missing_flow_marks_failed(client):
    tenant = _create_tenant(client, name="Missing Flow Tenant")
    session = get_session_factory()()
    try:
        job = SyncJob(
            id=str(uuid4()),
            tenant_id=tenant["id"],
            flow_id=str(uuid4()),
            status="pending",
            attempt_count=0,
            max_attempts=3,
            idempotency_key="missing-flow",
            source_payload={"name": "ACME"},
        )
        session.add(job)
        session.commit()
        job_id = job.id
    finally:
        session.close()

    process_flow_job(job_id)

    session = get_session_factory()()
    try:
        persisted = session.get(SyncJob, job_id)
        assert persisted is not None
        assert persisted.status == "failed"
        errors = session.query(IntegrationError).filter(IntegrationError.job_id == job_id).all()
        assert len(errors) == 1
        assert errors[0].error_type == "business_rule_error"
    finally:
        session.close()


def test_process_flow_job_invalid_mapping_marks_failed(client):
    tenant = _create_tenant(client, name="Invalid Mapping Tenant")
    source_connection = _create_connection(client, tenant["id"], "Source")
    target_connection = _create_connection(client, tenant["id"], "Target")
    flow = _create_flow(client, tenant["id"], source_connection["id"], target_connection["id"])

    session = get_session_factory()()
    try:
        bad_mapping = FieldMapping(
            id=str(uuid4()),
            tenant_id=tenant["id"],
            flow_id=flow["id"],
            source_field="name",
            target_field="customer_name",
            transformation_rule="bogus",
            default_value=None,
            required=True,
            active=True,
        )
        session.add(bad_mapping)
        job = SyncJob(
            id=str(uuid4()),
            tenant_id=tenant["id"],
            flow_id=flow["id"],
            status="pending",
            attempt_count=0,
            max_attempts=3,
            idempotency_key="invalid-mapping",
            source_payload={"name": "  ACME Ltda  "},
        )
        session.add(job)
        session.commit()
        job_id = job.id
    finally:
        session.close()

    process_flow_job(job_id)

    session = get_session_factory()()
    try:
        persisted = session.get(SyncJob, job_id)
        assert persisted is not None
        assert persisted.status == "failed"
        errors = session.query(IntegrationError).filter(IntegrationError.job_id == job_id).all()
        assert len(errors) == 1
        assert errors[0].error_type == "mapping_error"
    finally:
        session.close()


def test_process_flow_job_retry_to_dead_letter_and_reprocess(client, monkeypatch):
    tenant = _create_tenant(client, name="Retry Tenant")
    source_connection = _create_connection(client, tenant["id"], "Source")
    target_connection = _create_connection(client, tenant["id"], "Target")
    flow = _create_flow(client, tenant["id"], source_connection["id"], target_connection["id"])
    _create_mapping(client, flow["id"])

    session = get_session_factory()()
    try:
        job = SyncJob(
            id=str(uuid4()),
            tenant_id=tenant["id"],
            flow_id=flow["id"],
            status="pending",
            attempt_count=0,
            max_attempts=3,
            idempotency_key="retry-flow",
            source_payload={"name": "  ACME Ltda  "},
        )
        session.add(job)
        session.commit()
        job_id = job.id
    finally:
        session.close()

    original_execute = IntegrationRunner._simulate_target_execution

    def raise_timeout(*args, **kwargs):
        raise SankhyaTimeoutError("timeout")

    monkeypatch.setattr(IntegrationRunner, "_simulate_target_execution", raise_timeout)
    process_flow_job(job_id)
    process_flow_job(job_id)
    process_flow_job(job_id)

    session = get_session_factory()()
    try:
        persisted = session.get(SyncJob, job_id)
        assert persisted is not None
        assert persisted.status == "dead_letter"
        assert persisted.attempt_count == 3
    finally:
        session.close()

    monkeypatch.setattr(IntegrationRunner, "_simulate_target_execution", original_execute)
    monkeypatch.setattr(
        execute_flow_job,
        "apply_async",
        lambda *args, **kwargs: type("Result", (), {"id": "task-reprocess"})(),
    )
    reprocess_response = client.post(f"/api/v1/jobs/{job_id}/reprocess")
    assert reprocess_response.status_code == 200
    assert reprocess_response.json()["status"] == "pending"

    process_flow_job(job_id)

    session = get_session_factory()()
    try:
        persisted = session.get(SyncJob, job_id)
        assert persisted is not None
        assert persisted.status == "success"
        assert persisted.correlation_id == reprocess_response.json()["correlation_id"]
        logs = session.query(IntegrationLog).filter(IntegrationLog.job_id == job_id).all()
        assert len(logs) >= 5
    finally:
        session.close()
