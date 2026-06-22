from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.connection import Connection
from app.models.integration_flow import IntegrationFlow
from app.models.integration_log import IntegrationLog
from app.models.sync_job import SyncJob
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])

VALID_TENANT_STATUSES = {"active", "inactive"}


def _tenant_to_read(tenant: Tenant) -> TenantRead:
    return TenantRead.model_validate(tenant)


def _assert_status(status_value: str | None) -> str:
    resolved = status_value or "active"
    if resolved not in VALID_TENANT_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid tenant status")
    return resolved


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)) -> TenantRead:
    resolved_status = _assert_status(payload.status)
    tenant = Tenant(
        id=str(uuid4()),
        name=payload.name,
        document=payload.document,
        status=resolved_status,
        active=resolved_status == "active",
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return _tenant_to_read(tenant)


@router.get("", response_model=list[TenantRead])
def list_tenants(db: Session = Depends(get_db)) -> list[TenantRead]:
    tenants = db.scalars(select(Tenant).order_by(Tenant.created_at.desc())).all()
    return [_tenant_to_read(tenant) for tenant in tenants]


@router.get("/{tenant_id}", response_model=TenantRead)
def get_tenant(tenant_id: str, db: Session = Depends(get_db)) -> TenantRead:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return _tenant_to_read(tenant)


@router.patch("/{tenant_id}", response_model=TenantRead)
def update_tenant(tenant_id: str, payload: TenantUpdate, db: Session = Depends(get_db)) -> TenantRead:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes:
        changes["status"] = _assert_status(changes["status"])
        changes["active"] = changes["status"] == "active"

    for field_name, value in changes.items():
        setattr(tenant, field_name, value)

    db.commit()
    db.refresh(tenant)
    return _tenant_to_read(tenant)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(tenant_id: str, db: Session = Depends(get_db)) -> None:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    linked_counts = [
        db.scalar(select(func.count(Connection.id)).where(Connection.tenant_id == tenant_id)) or 0,
        db.scalar(select(func.count(IntegrationFlow.id)).where(IntegrationFlow.tenant_id == tenant_id)) or 0,
        db.scalar(select(func.count(SyncJob.id)).where(SyncJob.tenant_id == tenant_id)) or 0,
        db.scalar(select(func.count(IntegrationLog.id)).where(IntegrationLog.tenant_id == tenant_id)) or 0,
    ]
    if any(count > 0 for count in linked_counts):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant has linked resources and cannot be deleted",
        )

    db.delete(tenant)
    db.commit()
