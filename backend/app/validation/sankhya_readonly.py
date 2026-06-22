from __future__ import annotations

import argparse
import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.security import mask_payload


@dataclass(frozen=True)
class SankhyaReadonlyValidationSpec:
    operation_name: str
    entity_name: str
    fields: tuple[str, ...]
    limit: int = 10
    target_entity: str = "ValidationMirror"


DEFAULT_READONLY_VALIDATION_SPECS: tuple[SankhyaReadonlyValidationSpec, ...] = (
    SankhyaReadonlyValidationSpec(
        operation_name="sankhya_read_partner",
        entity_name="Parceiro",
        fields=("CODPARC", "NOMEPARC", "CGC_CPF"),
        limit=10,
    ),
    SankhyaReadonlyValidationSpec(
        operation_name="sankhya_read_product",
        entity_name="Produto",
        fields=("CODPROD", "DESCRPROD", "REFERENCIA"),
        limit=10,
    ),
    SankhyaReadonlyValidationSpec(
        operation_name="sankhya_read_seller",
        entity_name="Vendedor",
        fields=("CODVEND", "APELIDO", "ATIVO"),
        limit=10,
    ),
    SankhyaReadonlyValidationSpec(
        operation_name="sankhya_read_company",
        entity_name="Empresa",
        fields=("CODEMP", "RAZAOSOCIAL", "NOMEFANTASIA", "CGC"),
        limit=10,
    ),
)


@dataclass(frozen=True)
class SankhyaReadonlyValidationConfig:
    api_base_url: str
    tenant_name: str
    connection_name: str
    sankhya_base_url: str
    client_id: str
    client_secret: str
    x_token: str
    verify_ssl: bool = True
    timeout_seconds: int = 30
    poll_interval_seconds: float = 1.0
    max_poll_attempts: int = 120
    environment: str = "sandbox"
    report_dir: Path = Path("backend/reports")

    @property
    def report_path_prefix(self) -> str:
        return "sankhya_readonly_validation"


class ValidationOperationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    operation_name: str
    flow_id: str | None = None
    job_id: str | None = None
    status: str
    records_count: int | None = None
    duration_ms: int | None = None
    correlation_id: str | None = None
    error_type: str | None = None
    normalized_message: str | None = None
    log_count: int = 0
    masking_checked: bool = False


class ValidationReportSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_operations: int = 0
    success_count: int = 0
    failed_count: int = 0
    dead_letter_count: int = 0
    all_masking_ok: bool = False
    ready_for_next_stage: bool = False


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    started_at: datetime
    finished_at: datetime
    api_base_url: str
    tenant_name: str
    connection_name: str
    environment: str = "sandbox"
    operations: list[ValidationOperationResult] = Field(default_factory=list)
    summary: ValidationReportSummary


class ValidationApiClientProtocol(Protocol):
    def health(self) -> dict[str, Any]: ...

    def list_tenants(self) -> list[dict[str, Any]]: ...

    def create_tenant(self, *, name: str, document: str | None = None, status: str = "active") -> dict[str, Any]: ...

    def list_connections(self, tenant_id: str) -> list[dict[str, Any]]: ...

    def create_connection(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def list_flows(self, tenant_id: str) -> list[dict[str, Any]]: ...

    def create_flow(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def run_flow(self, flow_id: str) -> dict[str, Any]: ...

    def get_job(self, job_id: str) -> dict[str, Any]: ...

    def list_logs(self, tenant_id: str, limit: int = 500) -> list[dict[str, Any]]: ...


class SankhyaReadonlyValidationApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: int = 30,
        verify_ssl: bool = True,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            verify=verify_ssl,
            transport=transport,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SankhyaReadonlyValidationApiClient:
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self.close()

    @classmethod
    def from_config(
        cls,
        config: SankhyaReadonlyValidationConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> SankhyaReadonlyValidationApiClient:
        return cls(
            base_url=config.api_base_url,
            timeout_seconds=config.timeout_seconds,
            verify_ssl=config.verify_ssl,
            transport=transport,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        response = self._client.request(method, path, params=params, json=json_body)
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    def health(self) -> dict[str, Any]:
        return self._request_json("GET", "/health")

    def list_tenants(self) -> list[dict[str, Any]]:
        return list(self._request_json("GET", "/api/v1/tenants"))

    def create_tenant(self, *, name: str, document: str | None = None, status: str = "active") -> dict[str, Any]:
        payload = {"name": name, "document": document, "status": status}
        return dict(self._request_json("POST", "/api/v1/tenants", json_body=payload))

    def list_connections(self, tenant_id: str) -> list[dict[str, Any]]:
        return list(self._request_json("GET", "/api/v1/connections", params={"tenant_id": tenant_id}))

    def create_connection(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(self._request_json("POST", "/api/v1/connections", json_body=payload))

    def list_flows(self, tenant_id: str) -> list[dict[str, Any]]:
        return list(self._request_json("GET", "/api/v1/flows", params={"tenant_id": tenant_id}))

    def create_flow(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(self._request_json("POST", "/api/v1/flows", json_body=payload))

    def run_flow(self, flow_id: str) -> dict[str, Any]:
        return dict(self._request_json("POST", f"/api/v1/flows/{flow_id}/run", json_body={"source_payload": {}}))

    def get_job(self, job_id: str) -> dict[str, Any]:
        return dict(self._request_json("GET", f"/api/v1/jobs/{job_id}"))

    def list_logs(self, tenant_id: str, limit: int = 500) -> list[dict[str, Any]]:
        return list(self._request_json("GET", "/api/v1/logs", params={"tenant_id": tenant_id, "limit": limit}))


def _parse_bool(value: Any, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _required(value: str | None, label: str) -> str:
    resolved = (value or "").strip()
    if not resolved:
        raise ValueError(f"Missing required value: {label}")
    return resolved


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def load_validation_config(
    env: Mapping[str, str | None] | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> SankhyaReadonlyValidationConfig:
    source_env = env or {}
    source_overrides = overrides or {}

    def read(name: str, default: Any | None = None) -> Any:
        if name in source_overrides and source_overrides[name] is not None:
            return source_overrides[name]
        value = source_env.get(name)
        if value is not None and value != "":
            return value
        return default

    api_base_url = _normalize_base_url(str(read("CONNECTOR_API_BASE_URL", "http://localhost:8000")))
    tenant_name = str(read("VALIDATION_TENANT_NAME", "Preferenza Homologacao"))
    connection_name = str(read("SANKHYA_VALIDATION_CONNECTION_NAME", "Sankhya Sandbox Validation"))

    sankhya_base_url = _normalize_base_url(_required(read("SANKHYA_BASE_URL"), "SANKHYA_BASE_URL"))
    client_id = _required(read("SANKHYA_CLIENT_ID"), "SANKHYA_CLIENT_ID")
    client_secret = _required(read("SANKHYA_CLIENT_SECRET"), "SANKHYA_CLIENT_SECRET")
    x_token = _required(read("SANKHYA_X_TOKEN"), "SANKHYA_X_TOKEN")

    verify_ssl = _parse_bool(read("SANKHYA_VERIFY_SSL", True), default=True)
    timeout_seconds = int(read("SANKHYA_TIMEOUT_SECONDS", 30))
    poll_interval_seconds = float(read("VALIDATION_POLL_INTERVAL_SECONDS", 1.0))
    max_poll_attempts = int(read("VALIDATION_MAX_POLL_ATTEMPTS", 120))
    report_dir_raw = str(read("VALIDATION_REPORT_DIR", Path(__file__).resolve().parents[2] / "reports"))
    report_dir = Path(report_dir_raw)

    return SankhyaReadonlyValidationConfig(
        api_base_url=api_base_url,
        tenant_name=tenant_name,
        connection_name=connection_name,
        sankhya_base_url=sankhya_base_url,
        client_id=client_id,
        client_secret=client_secret,
        x_token=x_token,
        verify_ssl=verify_ssl,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        max_poll_attempts=max_poll_attempts,
        report_dir=report_dir,
    )


def _safe_text(value: Any, *, secrets: list[str]) -> str | None:
    if value is None:
        return None
    text = str(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    text = re.sub(r"(?i)(access_token\s*[:=]\s*)([^\s,;\"']+)", r"\1***", text)
    text = re.sub(r"(?i)(refresh_token\s*[:=]\s*)([^\s,;\"']+)", r"\1***", text)
    text = re.sub(r"(?i)(client_secret\s*[:=]\s*)([^\s,;\"']+)", r"\1***", text)
    text = re.sub(r"(?i)(x_token\s*[:=]\s*)([^\s,;\"']+)", r"\1***", text)
    text = re.sub(r"(?i)(authorization\s*[:=]\s*)([^\s,;\"']+)", r"\1***", text)
    text = re.sub(r"(?i)(bearer\s+)([^\s,;\"']+)", r"\1***", text)
    return text


def _safe_payload(value: Any, *, secrets: list[str]) -> Any:
    masked = mask_payload(value)
    if isinstance(masked, dict):
        return {key: _safe_payload(item, secrets=secrets) for key, item in masked.items()}
    if isinstance(masked, list):
        return [_safe_payload(item, secrets=secrets) for item in masked]
    if isinstance(masked, tuple):
        return tuple(_safe_payload(item, secrets=secrets) for item in masked)
    if isinstance(masked, str):
        return _safe_text(masked, secrets=secrets)
    return masked


def _contains_raw_secret(value: Any, secrets: list[str]) -> bool:
    if value is None:
        return False
    text = json.dumps(value, ensure_ascii=False, default=str)
    for secret in secrets:
        if secret and secret in text:
            return True
    return False


def _is_terminal_job_status(status: str | None) -> bool:
    return status in {"success", "failed", "dead_letter", "cancelled", "ignored"}


def _operation_payload(spec: SankhyaReadonlyValidationSpec) -> dict[str, Any]:
    return {
        "tenant_id": "",
        "name": f"Validation - {spec.operation_name}",
        "source_connection_id": "",
        "target_connection_id": "",
        "source_entity": spec.entity_name,
        "target_entity": spec.target_entity,
        "config_json": {
            "operation": spec.operation_name,
            "fields": list(spec.fields),
            "criteria": None,
            "limit": spec.limit,
            "mode": "real",
        },
        "trigger_type": "manual",
        "active": True,
    }


def _find_by_name(items: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for item in items:
        if str(item.get("name") or "").strip() == name:
            return item
    return None


def _find_connection(
    items: list[dict[str, Any]],
    *,
    name: str,
    base_url: str,
    environment: str,
) -> dict[str, Any] | None:
    for item in items:
        if str(item.get("name") or "").strip() != name:
            continue
        if str(item.get("base_url") or "").rstrip("/") != base_url.rstrip("/"):
            continue
        if str(item.get("environment") or "").strip().lower() != environment.lower():
            continue
        if str(item.get("platform") or "").strip().lower() != "sankhya":
            continue
        return item
    return None


def _find_flow(
    items: list[dict[str, Any]],
    *,
    name: str,
    operation_name: str,
    source_connection_id: str,
    target_connection_id: str,
) -> dict[str, Any] | None:
    for item in items:
        config_json = item.get("config_json") or {}
        if str(item.get("name") or "").strip() != name:
            continue
        if str(config_json.get("operation") or "").strip() != operation_name:
            continue
        if str(item.get("source_connection_id") or "") != source_connection_id:
            continue
        if str(item.get("target_connection_id") or "") != target_connection_id:
            continue
        return item
    return None


def _create_or_reuse_tenant(
    client: ValidationApiClientProtocol,
    config: SankhyaReadonlyValidationConfig,
) -> dict[str, Any]:
    tenant = _find_by_name(client.list_tenants(), config.tenant_name)
    if tenant is not None:
        return tenant
    return client.create_tenant(name=config.tenant_name, document=None, status="active")


def _create_or_reuse_connection(
    client: ValidationApiClientProtocol,
    config: SankhyaReadonlyValidationConfig,
    tenant_id: str,
) -> dict[str, Any]:
    connection = _find_connection(
        client.list_connections(tenant_id),
        name=config.connection_name,
        base_url=config.sankhya_base_url,
        environment=config.environment,
    )
    if connection is not None:
        return connection
    payload = {
        "tenant_id": tenant_id,
        "tenant_name": config.tenant_name,
        "name": config.connection_name,
        "platform": "sankhya",
        "environment": config.environment,
        "base_url": config.sankhya_base_url,
        "credentials": {
            "base_url": config.sankhya_base_url,
            "environment": config.environment,
            "auth_mode": "oauth_client_credentials",
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "x_token": config.x_token,
            "timeout_seconds": config.timeout_seconds,
            "verify_ssl": config.verify_ssl,
        },
    }
    return client.create_connection(payload)


def _create_or_reuse_flow(
    client: ValidationApiClientProtocol,
    *,
    tenant_id: str,
    connection_id: str,
    spec: SankhyaReadonlyValidationSpec,
) -> dict[str, Any]:
    flow_name = f"Validation - {spec.operation_name}"
    existing = _find_flow(
        client.list_flows(tenant_id),
        name=flow_name,
        operation_name=spec.operation_name,
        source_connection_id=connection_id,
        target_connection_id=connection_id,
    )
    if existing is not None:
        return existing

    payload = _operation_payload(spec)
    payload["tenant_id"] = tenant_id
    payload["source_connection_id"] = connection_id
    payload["target_connection_id"] = connection_id
    return client.create_flow(payload)


def _poll_job_until_terminal(
    client: ValidationApiClientProtocol,
    *,
    job_id: str,
    max_attempts: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    last_job: dict[str, Any] | None = None
    for _ in range(max_attempts):
        last_job = client.get_job(job_id)
        if _is_terminal_job_status(str(last_job.get("status") or "")):
            return last_job
        time.sleep(poll_interval_seconds)
    raise TimeoutError(f"Job {job_id} did not reach a terminal status")


def _collect_logs_for_job(
    client: ValidationApiClientProtocol,
    *,
    tenant_id: str,
    job_id: str,
) -> list[dict[str, Any]]:
    logs = client.list_logs(tenant_id, limit=500)
    return [log for log in logs if str(log.get("job_id") or "") == job_id]


def _extract_duration_ms(job: dict[str, Any], logs: list[dict[str, Any]]) -> int | None:
    latest_log = logs[0] if logs else None
    if latest_log is not None and latest_log.get("duration_ms") is not None:
        return int(latest_log["duration_ms"])

    started_at = job.get("started_at")
    finished_at = job.get("finished_at")
    if not started_at or not finished_at:
        return None

    try:
        started = datetime.fromisoformat(str(started_at))
        finished = datetime.fromisoformat(str(finished_at))
    except ValueError:
        return None
    return max(0, int((finished - started).total_seconds() * 1000))


def _extract_normalized_message(job: dict[str, Any], logs: list[dict[str, Any]], *, secrets: list[str]) -> str | None:
    if logs:
        message = logs[0].get("message")
        if message is not None:
            return _safe_text(message, secrets=secrets)
    return _safe_text(job.get("error_message"), secrets=secrets)


def _extract_error_type(job: dict[str, Any], logs: list[dict[str, Any]]) -> str | None:
    if logs and logs[0].get("error_type"):
        return str(logs[0]["error_type"])
    status = str(job.get("status") or "")
    if status in {"failed", "dead_letter", "retrying"}:
        return "unknown_error"
    return None


def _extract_correlation_id(job: dict[str, Any], logs: list[dict[str, Any]]) -> str | None:
    correlation_id = job.get("correlation_id")
    if correlation_id:
        return str(correlation_id)
    for log in logs:
        correlation_id = log.get("correlation_id")
        if correlation_id:
            return str(correlation_id)
    return None


def _masking_checked(job: dict[str, Any], logs: list[dict[str, Any]], *, secrets: list[str]) -> bool:
    raw_sections: list[Any] = [
        job.get("error_message"),
        job.get("source_payload"),
        job.get("transformed_payload"),
        job.get("response_payload"),
        [log.get("message") for log in logs],
        [log.get("payload_masked") for log in logs],
        [log.get("source_payload_masked") for log in logs],
        [log.get("transformed_payload_masked") for log in logs],
        [log.get("response_payload_masked") for log in logs],
    ]
    return not any(_contains_raw_secret(section, secrets) for section in raw_sections)


def run_validation(
    config: SankhyaReadonlyValidationConfig,
    *,
    api_client: ValidationApiClientProtocol | None = None,
) -> ValidationReport:
    started_at = datetime.now(UTC)
    secrets = [config.client_secret, config.x_token]
    close_client = False
    client = api_client
    if client is None:
        client = SankhyaReadonlyValidationApiClient.from_config(config)
        close_client = True

    try:
        health = client.health()
        if str(health.get("status") or "").lower() not in {"ok", "healthy"}:
            raise RuntimeError(f"API health check failed: {health.get('status')}")

        tenant = _create_or_reuse_tenant(client, config)
        connection = _create_or_reuse_connection(client, config, tenant["id"])

        operation_results: list[ValidationOperationResult] = []
        for spec in DEFAULT_READONLY_VALIDATION_SPECS:
            flow: dict[str, Any] | None = None
            job: dict[str, Any] | None = None
            logs: list[dict[str, Any]] = []
            try:
                flow = _create_or_reuse_flow(client, tenant_id=tenant["id"], connection_id=connection["id"], spec=spec)
                run_response = client.run_flow(flow["id"])
                job = _poll_job_until_terminal(
                    client,
                    job_id=str(run_response["job_id"]),
                    max_attempts=config.max_poll_attempts,
                    poll_interval_seconds=config.poll_interval_seconds,
                )
                logs = _collect_logs_for_job(client, tenant_id=tenant["id"], job_id=job["id"])
                operation_results.append(
                    ValidationOperationResult(
                        operation_name=spec.operation_name,
                        flow_id=str(flow["id"]),
                        job_id=str(job["id"]),
                        status=str(job.get("status") or "unknown"),
                        records_count=job.get("records_count"),
                        duration_ms=_extract_duration_ms(job, logs),
                        correlation_id=_extract_correlation_id(job, logs),
                        error_type=_extract_error_type(job, logs),
                        normalized_message=_extract_normalized_message(job, logs, secrets=secrets),
                        log_count=len(logs),
                        masking_checked=_masking_checked(job, logs, secrets=secrets),
                    )
                )
            except Exception as exc:
                normalized_message = _safe_text(exc, secrets=secrets)
                operation_results.append(
                    ValidationOperationResult(
                        operation_name=spec.operation_name,
                        flow_id=str(flow["id"]) if flow else None,
                        job_id=str(job["id"]) if job else None,
                        status="failed",
                        error_type=_classify_validation_exception(exc),
                        normalized_message=normalized_message,
                        log_count=len(logs),
                        masking_checked=(
                            not _contains_raw_secret(normalized_message, secrets) if normalized_message else True
                        ),
                    )
                )

        summary = _build_summary(operation_results)
        finished_at = datetime.now(UTC)
        return ValidationReport(
            started_at=started_at,
            finished_at=finished_at,
            api_base_url=config.api_base_url,
            tenant_name=config.tenant_name,
            connection_name=config.connection_name,
            environment=config.environment,
            operations=operation_results,
            summary=summary,
        )
    finally:
        if close_client and client is not None:
            close = getattr(client, "close", None)
            if callable(close):
                close()


def _classify_validation_exception(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return "validation_error"
    if isinstance(exc, TimeoutError):
        return "timeout_error"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout_error"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 401:
            return "authentication_error"
        if status == 403:
            return "authorization_error"
        if status == 429:
            return "rate_limit_error"
        if 500 <= status <= 599:
            return "external_api_error"
        if 400 <= status <= 499:
            return "validation_error"
        return "unknown_error"
    if isinstance(exc, httpx.RequestError):
        return "external_api_error"
    return "unknown_error"


def _build_summary(results: list[ValidationOperationResult]) -> ValidationReportSummary:
    summary = ValidationReportSummary(
        total_operations=len(results),
        success_count=sum(1 for result in results if result.status == "success"),
        failed_count=sum(1 for result in results if result.status not in {"success", "dead_letter"}),
        dead_letter_count=sum(1 for result in results if result.status == "dead_letter"),
        all_masking_ok=all(result.masking_checked for result in results),
    )
    summary.ready_for_next_stage = (
        summary.total_operations > 0 and summary.success_count == summary.total_operations and summary.all_masking_ok
    )
    return summary


def build_report_path(report_dir: Path, started_at: datetime) -> Path:
    timestamp = started_at.astimezone(UTC).strftime("%Y%m%d_%H%M%S")
    return report_dir / f"sankhya_readonly_validation_{timestamp}.json"


def write_validation_report(report: ValidationReport, report_dir: Path | str) -> Path:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = build_report_path(output_dir, report.started_at)
    report_path.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Sankhya read-only operations in homologation")
    parser.add_argument("--connector-api-base-url", default=None)
    parser.add_argument("--validation-tenant-name", default=None)
    parser.add_argument("--connection-name", default=None)
    parser.add_argument("--sankhya-base-url", default=None)
    parser.add_argument("--sankhya-client-id", default=None)
    parser.add_argument("--sankhya-client-secret", default=None)
    parser.add_argument("--sankhya-x-token", default=None)
    parser.add_argument("--verify-ssl", default=None)
    parser.add_argument("--timeout-seconds", default=None, type=int)
    parser.add_argument("--poll-interval-seconds", default=None, type=float)
    parser.add_argument("--max-poll-attempts", default=None, type=int)
    parser.add_argument("--report-dir", default=None)
    return parser


def _args_to_overrides(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "CONNECTOR_API_BASE_URL": args.connector_api_base_url,
        "VALIDATION_TENANT_NAME": args.validation_tenant_name,
        "SANKHYA_VALIDATION_CONNECTION_NAME": args.connection_name,
        "SANKHYA_BASE_URL": args.sankhya_base_url,
        "SANKHYA_CLIENT_ID": args.sankhya_client_id,
        "SANKHYA_CLIENT_SECRET": args.sankhya_client_secret,
        "SANKHYA_X_TOKEN": args.sankhya_x_token,
        "SANKHYA_VERIFY_SSL": args.verify_ssl,
        "SANKHYA_TIMEOUT_SECONDS": args.timeout_seconds,
        "VALIDATION_POLL_INTERVAL_SECONDS": args.poll_interval_seconds,
        "VALIDATION_MAX_POLL_ATTEMPTS": args.max_poll_attempts,
        "VALIDATION_REPORT_DIR": args.report_dir,
    }


def main(argv: list[str] | None = None, *, api_client: ValidationApiClientProtocol | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_validation_config(overrides=_args_to_overrides(args))
        report = run_validation(config, api_client=api_client)
        report_path = write_validation_report(report, config.report_dir)
        print(f"Validation completed. Report written to {report_path}")
        print(
            "Summary: "
            f"total={report.summary.total_operations}, "
            f"success={report.summary.success_count}, "
            f"failed={report.summary.failed_count}, "
            f"dead_letter={report.summary.dead_letter_count}, "
            f"ready_for_next_stage={report.summary.ready_for_next_stage}"
        )
        return 0
    except Exception as exc:
        print(_safe_text(exc, secrets=[]))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
