from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.security import mask_payload
from app.database.session import get_session_factory
from app.integrations.mapper import mask_payload_for_logging
from app.integrations.retry_policy import calculate_backoff
from app.integrations.runner import IntegrationRunner
from app.models.integration_error import IntegrationError
from app.models.integration_log import IntegrationLog
from app.models.sync_job import SyncJob
from app.workers.celery_app import create_celery_app

celery_app = create_celery_app()


def process_flow_job(job_id: str) -> SyncJob:
    session = get_session_factory()()
    try:
        runner = IntegrationRunner(session)
        job = runner.execute_job(job_id)
        session.commit()
        session.refresh(job)
        return job
    except Exception as exc:
        job = session.get(SyncJob, job_id)
        if job is not None:
            if job.correlation_id is None:
                job.correlation_id = str(uuid4())
            if job.status in {"pending", "running", "retrying"}:
                job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(UTC)
            error_type = runner._classify_exception(exc).error_type if "runner" in locals() else "unknown_error"
            log = IntegrationLog(
                id=str(uuid4()),
                tenant_id=job.tenant_id,
                flow_id=job.flow_id,
                job_id=job.id,
                status=job.status,
                message=str(exc),
                event_type="flow_execution",
                correlation_id=job.correlation_id,
                source_platform=None,
                target_platform=None,
                source_entity=None,
                target_entity=None,
                duration_ms=None,
                error_type=error_type,
                payload_masked=json.dumps(mask_payload(job.source_payload), ensure_ascii=False),
                source_payload_masked=json.dumps(mask_payload(job.source_payload), ensure_ascii=False),
                transformed_payload_masked=None,
                response_payload_masked=None,
            )
            error = IntegrationError(
                id=str(uuid4()),
                tenant_id=job.tenant_id,
                flow_id=job.flow_id,
                job_id=job.id,
                error_type=error_type,
                error_message=str(exc),
                normalized_message=str(exc),
                raw_error_masked=json.dumps(mask_payload_for_logging({"error": str(exc)}), ensure_ascii=False),
                retryable=error_type in {"timeout_error", "rate_limit_error", "external_api_error"},
                correlation_id=job.correlation_id,
            )
            session.add(log)
            session.add(error)
            session.commit()
            session.refresh(job)
            return job
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(name="preferenza_connector.execute_flow_job", bind=True)
def execute_flow_job(self, job_id: str) -> dict[str, Any]:
    job = process_flow_job(job_id)
    retry_in_seconds = None
    task_id = None
    if job.status == "retrying":
        retry_in_seconds = calculate_backoff(job.attempt_count)
        if not celery_app.conf.task_always_eager:
            scheduled = execute_flow_job.apply_async(args=[job.id], countdown=retry_in_seconds)
            task_id = scheduled.id
    return {
        "job_id": job.id,
        "tenant_id": job.tenant_id,
        "flow_id": job.flow_id,
        "status": job.status,
        "attempt_count": job.attempt_count,
        "retry_in_seconds": retry_in_seconds,
        "task_id": task_id,
    }
