from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.sync_job import SyncJob
from app.schemas.sync_job import SyncJobCancelResponse, SyncJobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[SyncJobRead])
def list_jobs(
    tenant_id: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SyncJobRead]:
    stmt = select(SyncJob).where(SyncJob.tenant_id == tenant_id).order_by(SyncJob.created_at.desc()).limit(limit)
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
    if job.status not in {"pending", "running", "retrying"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending, running or retrying jobs can be cancelled",
        )
    job.status = "cancelled"
    db.commit()
    db.refresh(job)
    return SyncJobCancelResponse(id=job.id, status=job.status, message="Job cancelled")
