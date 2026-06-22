from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.integration_log import IntegrationLog
from app.schemas.integration_log import IntegrationLogRead

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=list[IntegrationLogRead])
def list_logs(
    tenant_id: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[IntegrationLogRead]:
    stmt = (
        select(IntegrationLog)
        .where(IntegrationLog.tenant_id == tenant_id)
        .order_by(IntegrationLog.created_at.desc())
        .limit(limit)
    )
    return [IntegrationLogRead.model_validate(row) for row in db.scalars(stmt).all()]
