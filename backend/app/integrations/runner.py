from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.registry import DEFAULT_CONNECTOR_REGISTRY, ConnectorRegistry
from app.connectors.sankhya.exceptions import (
    SankhyaAuthenticationError,
    SankhyaError,
    SankhyaRateLimitError,
    SankhyaTimeoutError,
)
from app.connectors.sankhya.services import build_connector_from_connection, mask_connection_credentials
from app.core.exceptions import FlowExecutionError
from app.core.security import mask_payload
from app.integrations.idempotency import build_idempotency_key
from app.integrations.mapper import map_fields, mask_payload_for_logging
from app.integrations.validator import validate_required_fields
from app.models.connection import Connection
from app.models.field_mapping import FieldMapping
from app.models.integration_error import IntegrationError
from app.models.integration_flow import IntegrationFlow
from app.models.integration_log import IntegrationLog
from app.models.sync_job import SyncJob


@dataclass(frozen=True)
class ExecutionClassification:
    error_type: str
    normalized_message: str
    retryable: bool


class IntegrationRunner:
    def __init__(self, session: Session, registry: ConnectorRegistry | None = None) -> None:
        self.session = session
        self.registry = registry or DEFAULT_CONNECTOR_REGISTRY

    def build_connector(self, connection: Connection):
        if connection.platform.lower() == "sankhya":
            return build_connector_from_connection(connection)
        raise KeyError(f"Unsupported connector platform: {connection.platform}")

    def prepare_flow_job(
        self,
        *,
        flow: IntegrationFlow,
        source_payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> SyncJob:
        started_at = datetime.now(UTC)
        idempotency_key = build_idempotency_key(
            tenant_id=flow.tenant_id,
            flow_id=flow.id,
            payload=source_payload or {},
        )

        existing_success = self._find_success_job(idempotency_key)
        if existing_success is not None:
            job = self._create_job(
                tenant_id=flow.tenant_id,
                flow_id=flow.id,
                connection_id=flow.source_connection_id,
                status="ignored",
                attempt_count=0,
                idempotency_key=idempotency_key,
                source_payload=source_payload,
                started_at=started_at,
                finished_at=started_at,
                error_message="Duplicate payload already processed successfully",
                correlation_id=correlation_id,
            )
            self._write_execution_log(
                tenant_id=flow.tenant_id,
                flow=flow,
                job=job,
                status="ignored",
                message="Duplicate payload ignored",
                error_type="duplicate_error",
                started_at=started_at,
                correlation_id=correlation_id,
                source_connection=self._safe_load_connection(flow.source_connection_id),
                target_connection=self._safe_load_connection(flow.target_connection_id),
                source_payload=source_payload,
            )
            return job

        return self._create_job(
            tenant_id=flow.tenant_id,
            flow_id=flow.id,
            connection_id=flow.source_connection_id,
            status="pending",
            attempt_count=0,
            idempotency_key=idempotency_key,
            source_payload=source_payload,
            started_at=None,
            correlation_id=correlation_id,
        )

    def execute_job(self, job_id: str, correlation_id: str | None = None) -> SyncJob:
        job = self._load_job(job_id)
        if job.status in {"success", "ignored", "failed", "dead_letter", "cancelled"}:
            return job
        if job.status not in {"pending", "retrying"}:
            raise FlowExecutionError(f"Job {job.id} is not executable in status {job.status}")

        if correlation_id:
            job.correlation_id = correlation_id
        job.correlation_id = job.correlation_id or correlation_id or str(uuid4())

        started_at = datetime.now(UTC)
        if job.started_at is None:
            job.started_at = started_at
        job.attempt_count = (job.attempt_count or 0) + 1
        job.status = "running"
        job.cancel_requested = bool(job.cancel_requested)

        flow = self._load_flow(job.flow_id)
        source_connection = self._load_connection(flow.source_connection_id, flow.tenant_id)
        target_connection = self._load_connection(flow.target_connection_id, flow.tenant_id)

        if job.cancel_requested:
            job.status = "cancelled"
            job.finished_at = started_at
            self._write_execution_log(
                tenant_id=flow.tenant_id,
                flow=flow,
                job=job,
                status="cancelled",
                message="Job cancelled before execution",
                error_type=None,
                started_at=started_at,
                correlation_id=job.correlation_id,
                source_connection=source_connection,
                target_connection=target_connection,
                source_payload=job.source_payload or {},
            )
            return job

        if not flow.active:
            return self._finalize_failure(
                flow=flow,
                job=job,
                started_at=started_at,
                source_connection=source_connection,
                target_connection=target_connection,
                source_payload=job.source_payload or {},
                error_type="business_rule_error",
                error_message="Flow is inactive",
                retryable=False,
            )

        mappings = self._load_mappings(flow.id)
        try:
            required_fields = [mapping.source_field for mapping in mappings if mapping.required]
            missing_required = [
                field_name
                for field_name in required_fields
                if (job.source_payload or {}).get(field_name) in (None, "")
                and not self._has_default_for_field(mappings, field_name)
            ]
            if missing_required:
                raise ValueError(f"Missing required source fields: {', '.join(missing_required)}")
        except ValueError as exc:
            return self._finalize_failure(
                flow=flow,
                job=job,
                started_at=started_at,
                source_connection=source_connection,
                target_connection=target_connection,
                source_payload=job.source_payload or {},
                error_type="validation_error",
                error_message=str(exc),
                retryable=False,
            )

        try:
            transformed_payload = map_fields(
                job.source_payload or {},
                [self._mapping_to_dict(mapping) for mapping in mappings],
            )
        except ValueError as exc:
            return self._finalize_failure(
                flow=flow,
                job=job,
                started_at=started_at,
                source_connection=source_connection,
                target_connection=target_connection,
                source_payload=job.source_payload or {},
                error_type="mapping_error",
                error_message=str(exc),
                retryable=False,
            )

        try:
            validate_required_fields(
                transformed_payload,
                [mapping.target_field for mapping in mappings if mapping.required],
            )
            response_payload = self._simulate_target_execution(
                flow=flow,
                source_connection=source_connection,
                target_connection=target_connection,
                transformed_payload=transformed_payload,
            )
        except Exception as exc:
            classification = self._classify_exception(exc)
            retryable = classification.retryable and job.attempt_count < job.max_attempts
            final_status = "retrying" if retryable else ("dead_letter" if classification.retryable else "failed")
            job.status = final_status
            job.error_message = classification.normalized_message
            job.finished_at = datetime.now(UTC)
            self._write_execution_log(
                tenant_id=flow.tenant_id,
                flow=flow,
                job=job,
                status=final_status,
                message=classification.normalized_message,
                error_type=classification.error_type,
                started_at=started_at,
                correlation_id=job.correlation_id,
                source_connection=source_connection,
                target_connection=target_connection,
                source_payload=job.source_payload or {},
                transformed_payload=transformed_payload,
            )
            self._record_error(
                tenant_id=flow.tenant_id,
                flow=flow,
                job=job,
                error_type=classification.error_type,
                error_message=str(exc),
                normalized_message=classification.normalized_message,
                raw_error=exc,
                retryable=classification.retryable,
                correlation_id=job.correlation_id,
            )
            return job

        job.transformed_payload = transformed_payload
        job.response_payload = response_payload
        job.status = "success"
        job.error_message = None
        job.finished_at = datetime.now(UTC)
        self._write_execution_log(
            tenant_id=flow.tenant_id,
            flow=flow,
            job=job,
            status="success",
            message="Flow executed successfully",
            error_type=None,
            started_at=started_at,
            correlation_id=job.correlation_id,
            source_connection=source_connection,
            target_connection=target_connection,
            source_payload=job.source_payload or {},
            transformed_payload=transformed_payload,
            response_payload=response_payload,
        )
        return job

    def reprocess_job(self, *, job: SyncJob, correlation_id: str | None = None) -> SyncJob:
        if job.status not in {"failed", "dead_letter"}:
            raise FlowExecutionError("Only failed or dead_letter jobs can be reprocessed")

        started_at = datetime.now(UTC)
        job.status = "pending"
        job.cancel_requested = False
        job.attempt_count = 0
        job.started_at = None
        job.finished_at = None
        job.error_message = None
        job.transformed_payload = None
        job.response_payload = None
        job.correlation_id = correlation_id or str(uuid4())

        flow = self._load_flow(job.flow_id)
        source_connection = self._safe_load_connection(flow.source_connection_id)
        target_connection = self._safe_load_connection(flow.target_connection_id)
        self._write_execution_log(
            tenant_id=flow.tenant_id,
            flow=flow,
            job=job,
            status="pending",
            message="Job reprocessed and queued",
            error_type=None,
            started_at=started_at,
            correlation_id=job.correlation_id,
            source_connection=source_connection,
            target_connection=target_connection,
            source_payload=job.source_payload or {},
        )
        return job

    def test_connection(self, connection: Connection, correlation_id: str | None = None) -> dict[str, str | bool]:
        started_at = datetime.now(UTC)
        log_id = str(uuid4())
        connector = None
        try:
            connector = self.build_connector(connection)
            result = connector.test_connection()
            connection.status = "active"
            connection.last_test_status = "success"
            connection.last_test_at = datetime.now(UTC)
            log = self._write_log(
                id=log_id,
                tenant_id=connection.tenant_id,
                connection_id=connection.id,
                flow_id=None,
                job_id=None,
                status="success",
                message="Connection test succeeded",
                source_platform=connection.platform,
                target_platform=connection.platform,
                source_entity=None,
                target_entity=None,
                correlation_id=correlation_id,
                duration_ms=int((datetime.now(UTC) - started_at).total_seconds() * 1000),
                error_type=None,
                payload_masked=json.dumps(mask_connection_credentials(connection) or {}, ensure_ascii=False),
            )
            self.session.add(log)
            return {
                "success": True,
                "message": str(result.get("message", "Connection successful")),
                "connection_id": connection.id,
                "tenant_id": connection.tenant_id,
                "platform": connection.platform,
                "status": connection.status,
                "last_test_status": connection.last_test_status or "success",
                "log_id": log.id,
            }
        except Exception as exc:
            normalized = connector.normalize_error(exc) if connector is not None else self._normalize_exception(exc)
            connection.status = "error"
            connection.last_test_status = "failed"
            connection.last_test_at = datetime.now(UTC)
            log = self._write_log(
                id=log_id,
                tenant_id=connection.tenant_id,
                connection_id=connection.id,
                flow_id=None,
                job_id=None,
                status="failed",
                message=normalized["message"],
                source_platform=connection.platform,
                target_platform=connection.platform,
                source_entity=None,
                target_entity=None,
                correlation_id=correlation_id,
                duration_ms=int((datetime.now(UTC) - started_at).total_seconds() * 1000),
                error_type=normalized["category"],
                payload_masked=json.dumps(mask_connection_credentials(connection) or {}, ensure_ascii=False),
            )
            self.session.add(log)
            return {
                "success": False,
                "message": normalized["message"],
                "connection_id": connection.id,
                "tenant_id": connection.tenant_id,
                "platform": connection.platform,
                "status": connection.status,
                "last_test_status": connection.last_test_status or "failed",
                "log_id": log.id,
            }

    def run_flow(
        self,
        *,
        flow: IntegrationFlow,
        source_payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> SyncJob:
        started_at = datetime.now(UTC)
        source_connection = self._load_connection(flow.source_connection_id, flow.tenant_id)
        target_connection = self._load_connection(flow.target_connection_id, flow.tenant_id)
        mappings = self._load_mappings(flow.id)
        idempotency_key = build_idempotency_key(
            tenant_id=flow.tenant_id,
            flow_id=flow.id,
            payload=source_payload or {},
        )

        if self._find_success_job(idempotency_key) is not None:
            job = self._create_job(
                tenant_id=flow.tenant_id,
                flow_id=flow.id,
                connection_id=flow.source_connection_id,
                status="ignored",
                attempt_count=0,
                idempotency_key=idempotency_key,
                source_payload=source_payload,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                error_message="Duplicate payload already processed successfully",
            )
            self._write_execution_log(
                tenant_id=flow.tenant_id,
                flow=flow,
                job=job,
                status="ignored",
                message="Duplicate payload ignored",
                error_type="duplicate_error",
                started_at=started_at,
                correlation_id=correlation_id,
                source_connection=source_connection,
                target_connection=target_connection,
                source_payload=source_payload,
            )
            return job

        if not flow.active:
            return self._fail_execution(
                flow=flow,
                source_connection=source_connection,
                target_connection=target_connection,
                source_payload=source_payload,
                correlation_id=correlation_id,
                started_at=started_at,
                error_type="business_rule_error",
                error_message="Flow is inactive",
            )

        job = self._create_job(
            tenant_id=flow.tenant_id,
            flow_id=flow.id,
            connection_id=flow.source_connection_id,
            status="running",
            attempt_count=1,
            idempotency_key=idempotency_key,
            source_payload=source_payload,
            started_at=started_at,
        )

        try:
            required_fields = [mapping.source_field for mapping in mappings if mapping.required]
            missing_required = [
                field_name
                for field_name in required_fields
                if source_payload.get(field_name) in (None, "")
                and not self._has_default_for_field(mappings, field_name)
            ]
            if missing_required:
                raise ValueError(f"Missing required source fields: {', '.join(missing_required)}")

            transformed_payload = map_fields(
                source_payload,
                [self._mapping_to_dict(mapping) for mapping in mappings],
            )
            validate_required_fields(
                transformed_payload,
                [mapping.target_field for mapping in mappings if mapping.required],
            )
            response_payload = {
                "accepted": True,
                "simulated": True,
                "transformed_payload": transformed_payload,
            }
            job.transformed_payload = transformed_payload
            job.response_payload = response_payload
            job.status = "success"
            job.error_message = None
            job.finished_at = datetime.now(UTC)
            self._write_execution_log(
                tenant_id=flow.tenant_id,
                flow=flow,
                job=job,
                status="success",
                message="Flow executed successfully",
                error_type=None,
                started_at=started_at,
                correlation_id=correlation_id,
                source_connection=source_connection,
                target_connection=target_connection,
                source_payload=source_payload,
                transformed_payload=transformed_payload,
                response_payload=response_payload,
            )
            return job
        except Exception as exc:
            return self._fail_execution(
                flow=flow,
                source_connection=source_connection,
                target_connection=target_connection,
                source_payload=source_payload,
                correlation_id=correlation_id,
                started_at=started_at,
                error_type=self._normalize_exception(exc)["category"],
                error_message=str(exc),
                job=job,
            )

    def _fail_execution(
        self,
        *,
        flow: IntegrationFlow,
        source_connection: Connection,
        target_connection: Connection,
        source_payload: dict[str, Any],
        correlation_id: str | None,
        started_at: datetime,
        error_type: str,
        error_message: str,
        job: SyncJob | None = None,
    ) -> SyncJob:
        resolved_job = job or self._create_job(
            tenant_id=flow.tenant_id,
            flow_id=flow.id,
            connection_id=flow.source_connection_id,
            status="failed",
            attempt_count=1,
            idempotency_key=build_idempotency_key(
                tenant_id=flow.tenant_id,
                flow_id=flow.id,
                payload=source_payload or {},
            ),
            source_payload=source_payload,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            error_message=error_message,
        )
        resolved_job.status = "failed"
        resolved_job.error_message = error_message
        resolved_job.finished_at = datetime.now(UTC)

        self._write_execution_log(
            tenant_id=flow.tenant_id,
            flow=flow,
            job=resolved_job,
            status="failed",
            message=error_message,
            error_type=error_type,
            started_at=started_at,
            correlation_id=correlation_id,
            source_connection=source_connection,
            target_connection=target_connection,
            source_payload=source_payload,
        )
        self._record_error(
            tenant_id=flow.tenant_id,
            flow=flow,
            job=resolved_job,
            error_type=error_type,
            error_message=error_message,
            normalized_message=error_message,
            raw_error=FlowExecutionError(error_message),
            retryable=False,
            correlation_id=correlation_id,
        )
        return resolved_job

    def _write_log(
        self,
        *,
        id: str,
        tenant_id: str,
        connection_id: str | None,
        flow_id: str | None,
        job_id: str | None,
        status: str,
        message: str,
        source_platform: str | None,
        target_platform: str | None,
        source_entity: str | None,
        target_entity: str | None,
        correlation_id: str | None,
        duration_ms: int | None,
        error_type: str | None,
        payload_masked: str | None,
    ) -> IntegrationLog:
        log = IntegrationLog(
            id=id,
            tenant_id=tenant_id,
            connection_id=connection_id,
            flow_id=flow_id,
            job_id=job_id,
            status=status,
            message=message,
            event_type="connection_test" if connection_id and job_id is None else "flow_execution",
            correlation_id=correlation_id,
            source_platform=source_platform,
            target_platform=target_platform,
            source_entity=source_entity,
            target_entity=target_entity,
            duration_ms=duration_ms,
            error_type=error_type,
            payload_masked=payload_masked,
        )
        return log

    def _create_job(
        self,
        *,
        tenant_id: str,
        flow_id: str,
        connection_id: str | None,
        status: str,
        attempt_count: int,
        idempotency_key: str,
        source_payload: dict[str, Any],
        started_at: datetime | None,
        finished_at: datetime | None = None,
        error_message: str | None = None,
        correlation_id: str | None = None,
    ) -> SyncJob:
        job = SyncJob(
            id=str(uuid4()),
            tenant_id=tenant_id,
            flow_id=flow_id,
            connection_id=connection_id,
            status=status,
            correlation_id=correlation_id,
            attempt_count=attempt_count,
            max_attempts=3,
            idempotency_key=idempotency_key,
            cancel_requested=False,
            source_payload=source_payload,
            started_at=started_at,
            finished_at=finished_at,
            error_message=error_message,
        )
        self.session.add(job)
        self.session.flush()
        return job

    def _write_execution_log(
        self,
        *,
        tenant_id: str,
        flow: IntegrationFlow,
        job: SyncJob,
        status: str,
        message: str,
        error_type: str | None,
        started_at: datetime,
        correlation_id: str | None,
        source_connection: Connection | None,
        target_connection: Connection | None,
        source_payload: dict[str, Any],
        transformed_payload: dict[str, Any] | None = None,
        response_payload: dict[str, Any] | None = None,
    ) -> IntegrationLog:
        duration_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
        payload_to_mask = mask_payload(source_payload)
        source_payload_masked = json.dumps(mask_payload(source_payload), ensure_ascii=False)
        transformed_payload_masked = (
            json.dumps(mask_payload(transformed_payload), ensure_ascii=False)
            if transformed_payload is not None
            else None
        )
        response_payload_masked = (
            json.dumps(mask_payload(response_payload), ensure_ascii=False) if response_payload is not None else None
        )
        if transformed_payload is not None:
            payload_to_mask = {
                "source": payload_to_mask,
                "transformed": mask_payload(transformed_payload),
                "response": mask_payload(response_payload) if response_payload is not None else None,
            }
        log = IntegrationLog(
            id=str(uuid4()),
            tenant_id=tenant_id,
            flow_id=flow.id,
            job_id=job.id,
            status=status,
            message=message,
            event_type="flow_execution",
            correlation_id=correlation_id,
            source_platform=source_connection.platform if source_connection is not None else None,
            target_platform=target_connection.platform if target_connection is not None else None,
            source_entity=flow.source_entity,
            target_entity=flow.target_entity,
            duration_ms=duration_ms,
            error_type=error_type,
            payload_masked=json.dumps(payload_to_mask, ensure_ascii=False),
            source_payload_masked=source_payload_masked,
            transformed_payload_masked=transformed_payload_masked,
            response_payload_masked=response_payload_masked,
        )
        self.session.add(log)
        return log

    def _normalize_exception(self, exc: Exception) -> dict[str, str]:
        classification = self._classify_exception(exc)
        return {"category": classification.error_type, "message": classification.normalized_message}

    def _classify_exception(self, exc: Exception) -> ExecutionClassification:
        if isinstance(exc, SankhyaTimeoutError):
            return ExecutionClassification("timeout_error", str(exc), True)
        if isinstance(exc, SankhyaRateLimitError):
            return ExecutionClassification("rate_limit_error", str(exc), True)
        if isinstance(exc, SankhyaAuthenticationError):
            return ExecutionClassification("authentication_error", str(exc), False)
        if isinstance(exc, SankhyaError):
            return ExecutionClassification("external_api_error", str(exc), True)
        if isinstance(exc, FlowExecutionError):
            return ExecutionClassification("business_rule_error", str(exc), False)
        if isinstance(exc, ValueError):
            return ExecutionClassification("validation_error", str(exc), False)
        return ExecutionClassification("unknown_error", str(exc), False)

    def _load_job(self, job_id: str) -> SyncJob:
        job = self.session.get(SyncJob, job_id)
        if job is None:
            raise FlowExecutionError("Job not found")
        return job

    def _load_flow(self, flow_id: str | None) -> IntegrationFlow:
        if flow_id is None:
            raise FlowExecutionError("Job is not linked to a flow")
        flow = self.session.get(IntegrationFlow, flow_id)
        if flow is None:
            raise FlowExecutionError("Flow not found")
        return flow

    def _safe_load_connection(self, connection_id: str | None) -> Connection | None:
        if connection_id is None:
            return None
        return self.session.get(Connection, connection_id)

    def _simulate_target_execution(
        self,
        *,
        flow: IntegrationFlow,
        source_connection: Connection,
        target_connection: Connection,
        transformed_payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "accepted": True,
            "simulated": True,
            "source_entity": flow.source_entity,
            "target_entity": flow.target_entity,
            "source_connection_id": source_connection.id,
            "target_connection_id": target_connection.id,
            "transformed_payload": transformed_payload,
        }

    def _record_error(
        self,
        *,
        tenant_id: str,
        flow: IntegrationFlow,
        job: SyncJob,
        error_type: str,
        error_message: str,
        normalized_message: str,
        raw_error: Exception,
        retryable: bool,
        correlation_id: str | None,
    ) -> IntegrationError:
        raw_error_masked = json.dumps(mask_payload_for_logging({"error": str(raw_error)}), ensure_ascii=False)
        error = IntegrationError(
            id=str(uuid4()),
            tenant_id=tenant_id,
            flow_id=flow.id,
            job_id=job.id,
            error_type=error_type,
            error_message=error_message,
            normalized_message=normalized_message,
            raw_error_masked=raw_error_masked,
            retryable=retryable,
            correlation_id=correlation_id,
        )
        self.session.add(error)
        return error

    def _finalize_failure(
        self,
        *,
        flow: IntegrationFlow,
        job: SyncJob,
        started_at: datetime,
        source_connection: Connection,
        target_connection: Connection,
        source_payload: dict[str, Any],
        error_type: str,
        error_message: str,
        retryable: bool,
    ) -> SyncJob:
        job.error_message = error_message
        job.finished_at = datetime.now(UTC)
        if retryable and job.attempt_count < job.max_attempts:
            job.status = "retrying"
        elif retryable:
            job.status = "dead_letter"
        else:
            job.status = "failed"
        self._write_execution_log(
            tenant_id=flow.tenant_id,
            flow=flow,
            job=job,
            status=job.status,
            message=error_message,
            error_type=error_type,
            started_at=started_at,
            correlation_id=job.correlation_id,
            source_connection=source_connection,
            target_connection=target_connection,
            source_payload=source_payload,
        )
        self._record_error(
            tenant_id=flow.tenant_id,
            flow=flow,
            job=job,
            error_type=error_type,
            error_message=error_message,
            normalized_message=error_message,
            raw_error=FlowExecutionError(error_message),
            retryable=retryable,
            correlation_id=job.correlation_id,
        )
        return job

    def _load_connection(self, connection_id: str, tenant_id: str) -> Connection:
        connection = self.session.get(Connection, connection_id)
        if connection is None or connection.tenant_id != tenant_id:
            raise FlowExecutionError("Flow references an invalid connection")
        return connection

    def _load_mappings(self, flow_id: str) -> list[FieldMapping]:
        stmt = select(FieldMapping).where(FieldMapping.flow_id == flow_id, FieldMapping.active.is_(True))
        return list(self.session.scalars(stmt).all())

    def _find_success_job(self, idempotency_key: str) -> SyncJob | None:
        stmt = select(SyncJob).where(
            SyncJob.idempotency_key == idempotency_key,
            SyncJob.status == "success",
        )
        return self.session.scalars(stmt).first()

    def _has_default_for_field(self, mappings: list[FieldMapping], source_field: str) -> bool:
        for mapping in mappings:
            if mapping.source_field == source_field and mapping.default_value not in (None, ""):
                return True
        return False

    def _mapping_to_dict(self, mapping: FieldMapping) -> dict[str, Any]:
        return {
            "source_field": mapping.source_field,
            "target_field": mapping.target_field,
            "transformation_rule": mapping.transformation_rule,
            "default_value": mapping.default_value,
            "required": mapping.required,
            "active": mapping.active,
        }
