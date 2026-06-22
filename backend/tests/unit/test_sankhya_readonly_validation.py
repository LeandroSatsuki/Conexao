from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.validation.sankhya_readonly import (
    DEFAULT_READONLY_VALIDATION_SPECS,
    SankhyaReadonlyValidationConfig,
    load_validation_config,
    main,
    run_validation,
    write_validation_report,
)


class FakeValidationApiClient:
    def __init__(
        self,
        *,
        statuses: dict[str, str] | None = None,
        secret_message_operations: set[str] | None = None,
    ) -> None:
        self.statuses = statuses or {}
        self.secret_message_operations = secret_message_operations or set()
        self.tenants: list[dict[str, object]] = []
        self.connections: list[dict[str, object]] = []
        self.flows: list[dict[str, object]] = []
        self.jobs: dict[str, dict[str, object]] = {}
        self.logs: list[dict[str, object]] = []

    def health(self) -> dict[str, object]:
        return {"status": "ok", "database": "ok", "redis": "ok"}

    def list_tenants(self) -> list[dict[str, object]]:
        return list(self.tenants)

    def create_tenant(self, *, name: str, document: str | None = None, status: str = "active") -> dict[str, object]:
        tenant = {
            "id": f"tenant-{len(self.tenants) + 1}",
            "name": name,
            "document": document,
            "status": status,
        }
        self.tenants.append(tenant)
        return tenant

    def list_connections(self, tenant_id: str) -> list[dict[str, object]]:
        return [connection for connection in self.connections if connection["tenant_id"] == tenant_id]

    def create_connection(self, payload: dict[str, object]) -> dict[str, object]:
        connection = dict(payload)
        connection["id"] = f"connection-{len(self.connections) + 1}"
        self.connections.append(connection)
        return connection

    def list_flows(self, tenant_id: str) -> list[dict[str, object]]:
        return [flow for flow in self.flows if flow["tenant_id"] == tenant_id]

    def create_flow(self, payload: dict[str, object]) -> dict[str, object]:
        flow = dict(payload)
        flow["id"] = f"flow-{len(self.flows) + 1}"
        self.flows.append(flow)
        return flow

    def run_flow(self, flow_id: str) -> dict[str, object]:
        flow = next(flow for flow in self.flows if flow["id"] == flow_id)
        operation_name = str((flow["config_json"] or {}).get("operation"))
        status = self.statuses.get(operation_name, "success")
        job_id = f"job-{operation_name}"
        correlation_id = f"corr-{operation_name}"
        now = "2026-06-22T12:00:00+00:00"
        error_message = (
            "client_secret=client-secret x_token=x-token access_token=access-token-123 bearer token=legacy-token"
            if operation_name in self.secret_message_operations
            else "Operation completed"
        )
        job = {
            "id": job_id,
            "tenant_id": flow["tenant_id"],
            "flow_id": flow_id,
            "connection_id": flow["source_connection_id"],
            "status": status,
            "correlation_id": correlation_id,
            "attempt_count": 1,
            "max_attempts": 3,
            "idempotency_key": f"idem-{operation_name}",
            "cancel_requested": False,
            "records_count": 1 if status == "success" else 0,
            "source_payload": {"operation_config": flow["config_json"]},
            "transformed_payload": {"records": [{"NOMEPARC": "ACME Ltda"}]},
            "response_payload": {"records": [{"NOMEPARC": "ACME Ltda"}], "records_count": 1},
            "error_message": error_message if status != "success" else None,
            "started_at": now,
            "finished_at": now,
            "created_at": now,
            "updated_at": now,
        }
        self.jobs[job_id] = job
        self.logs.append(
            {
                "id": f"log-{operation_name}",
                "tenant_id": flow["tenant_id"],
                "connection_id": flow["source_connection_id"],
                "flow_id": flow_id,
                "job_id": job_id,
                "status": status,
                "message": error_message if status != "success" else "Operation completed",
                "event_type": "integration_execution",
                "operation": operation_name,
                "mode": "real",
                "correlation_id": correlation_id,
                "source_platform": "sankhya",
                "target_platform": "sankhya",
                "source_entity": flow["source_entity"],
                "target_entity": flow["target_entity"],
                "duration_ms": 123,
                "records_count": 1 if status == "success" else 0,
                "error_type": "external_api_error" if status in {"failed", "dead_letter"} else None,
                "payload_masked": json.dumps({"operation": operation_name}, ensure_ascii=False),
                "created_at": now,
            }
        )
        return {
            "job_id": job_id,
            "flow_id": flow_id,
            "tenant_id": flow["tenant_id"],
            "status": "pending",
            "task_id": f"task-{operation_name}",
            "correlation_id": correlation_id,
            "idempotency_key": f"idem-{operation_name}",
            "message": "Job queued",
        }

    def get_job(self, job_id: str) -> dict[str, object]:
        return dict(self.jobs[job_id])

    def list_logs(self, tenant_id: str, limit: int = 500) -> list[dict[str, object]]:
        return [log for log in self.logs if log["tenant_id"] == tenant_id][:limit]


def _build_config(tmp_path: Path) -> SankhyaReadonlyValidationConfig:
    return SankhyaReadonlyValidationConfig(
        api_base_url="http://localhost:8000",
        tenant_name="Preferenza Homologacao",
        connection_name="Sankhya Sandbox Validation",
        sankhya_base_url="https://api.sandbox.sankhya.com.br",
        client_id="client-id",
        client_secret="client-secret",
        x_token="x-token",
        verify_ssl=True,
        timeout_seconds=30,
        poll_interval_seconds=0,
        max_poll_attempts=3,
        report_dir=tmp_path,
    )


def test_load_validation_config_requires_required_credentials():
    with pytest.raises(ValueError, match="SANKHYA_CLIENT_SECRET|SANKHYA_X_TOKEN"):
        load_validation_config(
            env={
                "CONNECTOR_API_BASE_URL": "http://localhost:8000",
                "SANKHYA_BASE_URL": "https://api.sandbox.sankhya.com.br",
                "SANKHYA_CLIENT_ID": "client-id",
            }
        )


def test_run_validation_generates_sanitized_report_and_continues_after_one_failure(tmp_path):
    fake_client = FakeValidationApiClient(
        statuses={
            "sankhya_read_partner": "success",
            "sankhya_read_product": "failed",
            "sankhya_read_seller": "dead_letter",
            "sankhya_read_company": "success",
        },
        secret_message_operations={"sankhya_read_product"},
    )
    config = _build_config(tmp_path)

    report = run_validation(config, api_client=fake_client)
    report_path = write_validation_report(report, tmp_path)
    report_json = report_path.read_text(encoding="utf-8")

    assert report.summary.total_operations == 4
    assert report.summary.success_count == 2
    assert report.summary.failed_count == 1
    assert report.summary.dead_letter_count == 1
    assert report.summary.all_masking_ok is False
    assert report.summary.ready_for_next_stage is False
    assert len(report.operations) == 4
    assert any(operation.status == "failed" for operation in report.operations)
    assert any(operation.status == "dead_letter" for operation in report.operations)
    assert "client-secret" not in report_json
    assert "x-token" not in report_json
    assert "access_token" in report_json
    assert "***" in report_json

    product_result = next(result for result in report.operations if result.operation_name == "sankhya_read_product")
    assert product_result.status == "failed"
    assert product_result.normalized_message is not None
    assert "client-secret" not in product_result.normalized_message
    assert "access-token-123" not in product_result.normalized_message


def test_run_validation_marks_ready_when_everything_succeeds(tmp_path):
    fake_client = FakeValidationApiClient()
    config = _build_config(tmp_path)

    report = run_validation(config, api_client=fake_client)

    assert report.summary.total_operations == len(DEFAULT_READONLY_VALIDATION_SPECS)
    assert report.summary.success_count == len(DEFAULT_READONLY_VALIDATION_SPECS)
    assert report.summary.failed_count == 0
    assert report.summary.dead_letter_count == 0
    assert report.summary.all_masking_ok is True
    assert report.summary.ready_for_next_stage is True
    assert all(result.status == "success" for result in report.operations)


def test_cli_does_not_print_secrets(tmp_path, capsys):
    fake_client = FakeValidationApiClient(
        statuses={"sankhya_read_product": "failed"},
        secret_message_operations={"sankhya_read_product"},
    )
    report_dir = tmp_path / "reports"
    exit_code = main(
        [
            "--connector-api-base-url",
            "http://localhost:8000",
            "--validation-tenant-name",
            "Preferenza Homologacao",
            "--connection-name",
            "Sankhya Sandbox Validation",
            "--sankhya-base-url",
            "https://api.sandbox.sankhya.com.br",
            "--sankhya-client-id",
            "client-id",
            "--sankhya-client-secret",
            "client-secret",
            "--sankhya-x-token",
            "x-token",
            "--report-dir",
            str(report_dir),
        ],
        api_client=fake_client,
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "client-secret" not in captured.out
    assert "x-token" not in captured.out
    assert "access_token" not in captured.out.lower()
    assert report_dir.exists()
