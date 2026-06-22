from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.integrations.runner import IntegrationRunner
from app.models.sync_job import SyncJob
from app.schemas.sync_job import FlowRunResponse, SyncJobCancelResponse, SyncJobRead
from app.workers.tasks import execute_flow_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[SyncJobRead])
def list_jobs(
    tenant_id: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SyncJobRead]:
    stmt = select(SyncJob).where(SyncJob.tenant_id == tenant_id).order_by(SyncJob.created_at.desc()).limit(limit)
    return [SyncJobRead.model_validate(row) for row in db.scalars(stmt).all()]


@router.get("/dead-letter", response_model=list[SyncJobRead])
def list_dead_letter_jobs(
    tenant_id: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SyncJobRead]:
    stmt = (
        select(SyncJob)
        .where(SyncJob.tenant_id == tenant_id, SyncJob.status == "dead_letter")
        .order_by(SyncJob.created_at.desc())
        .limit(limit)
    )
    return [SyncJobRead.model_validate(row) for row in db.scalars(stmt).all()]


@router.get("/{job_id}", response_model=SyncJobRead)
def get_job(job_id: str, db: Session = Depends(get_db)) -> SyncJobRead:
    job = db.get(SyncJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return SyncJobRead.model_validate(job)


@router.post("/{job_id}/cancel", response_model=SyncJobCancelResponse)
def cancel_job(job_id: str, db: Session = Depends(get_db)) -> SyncJobCancelResponse:
    job = db.get(SyncJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status == "success":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Success jobs cannot be cancelled")
    if job.status in {"failed", "dead_letter", "ignored", "cancelled"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job cannot be cancelled in its current status",
        )
    if job.status == "running":
        job.cancel_requested = True
        db.commit()
        db.refresh(job)
        return SyncJobCancelResponse(
            id=job.id,
            status=job.status,
            message="Cancellation requested",
            cancel_requested=True,
        )

    job.status = "cancelled"
    job.cancel_requested = True
    db.commit()
    db.refresh(job)
    return SyncJobCancelResponse(id=job.id, status=job.status, message="Job cancelled", cancel_requested=True)


@router.post("/{job_id}/reprocess", response_model=FlowRunResponse)
def reprocess_job(job_id: str, request: Request, db: Session = Depends(get_db)) -> FlowRunResponse:
    job = db.get(SyncJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status not in {"failed", "dead_letter"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed or dead_letter jobs can be reprocessed",
        )

    runner = IntegrationRunner(db)
    job = runner.reprocess_job(job=job, correlation_id=request.state.correlation_id)
    db.commit()
    db.refresh(job)

    async_result = execute_flow_job.apply_async(args=[job.id])
    return FlowRunResponse(
        job_id=job.id,
        flow_id=job.flow_id or "",
        tenant_id=job.tenant_id,
        status=job.status,
        task_id=async_result.id,
        correlation_id=job.correlation_id,
        idempotency_key=job.idempotency_key,
        message="Job reprocessed",
    )
