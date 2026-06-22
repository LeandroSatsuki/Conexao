from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.registry import DEFAULT_CONNECTOR_REGISTRY, ConnectorRegistry
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


class IntegrationRunner:
    def __init__(self, session: Session, registry: ConnectorRegistry | None = None) -> None:
        self.session = session
        self.registry = registry or DEFAULT_CONNECTOR_REGISTRY

    def build_connector(self, connection: Connection):
        if connection.platform.lower() == "sankhya":
            return build_connector_from_connection(connection)
        raise KeyError(f"Unsupported connector platform: {connection.platform}")

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
        error = IntegrationError(
            id=str(uuid4()),
            tenant_id=flow.tenant_id,
            job_id=resolved_job.id,
            error_type=error_type,
            message=error_message,
            details=json.dumps(mask_payload_for_logging(source_payload), ensure_ascii=False),
        )
        self.session.add(error)
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
        started_at: datetime,
        finished_at: datetime | None = None,
        error_message: str | None = None,
    ) -> SyncJob:
        job = SyncJob(
            id=str(uuid4()),
            tenant_id=tenant_id,
            flow_id=flow_id,
            connection_id=connection_id,
            status=status,
            attempt_count=attempt_count,
            max_attempts=3,
            idempotency_key=idempotency_key,
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
        source_connection: Connection,
        target_connection: Connection,
        source_payload: dict[str, Any],
        transformed_payload: dict[str, Any] | None = None,
        response_payload: dict[str, Any] | None = None,
    ) -> IntegrationLog:
        duration_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
        payload_to_mask = mask_payload(source_payload)
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
            source_platform=source_connection.platform,
            target_platform=target_connection.platform,
            source_entity=flow.source_entity,
            target_entity=flow.target_entity,
            duration_ms=duration_ms,
            error_type=error_type,
            payload_masked=json.dumps(payload_to_mask, ensure_ascii=False),
        )
        self.session.add(log)
        return log

    def _normalize_exception(self, exc: Exception) -> dict[str, str]:
        if isinstance(exc, ValueError):
            return {"category": "validation_error", "message": str(exc)}
        if isinstance(exc, FlowExecutionError):
            return {"category": "business_rule_error", "message": str(exc)}
        return {"category": "unknown_error", "message": str(exc)}

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
