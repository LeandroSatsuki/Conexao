from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.registry import DEFAULT_CONNECTOR_REGISTRY
from app.connectors.sankhya.services import mask_connection_credentials
from app.core.encryption import encrypt_secret
from app.database.session import get_db
from app.integrations.runner import IntegrationRunner
from app.models.connection import Connection
from app.models.tenant import Tenant
from app.schemas.connection import ConnectionCreate, ConnectionRead, ConnectionTestResponse

router = APIRouter(prefix="/connections", tags=["connections"])


def _ensure_tenant(db: Session, tenant_id: str, tenant_name: str | None = None) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        tenant = Tenant(
            id=tenant_id,
            name=tenant_name or "Preferenza",
            document=None,
            status="active",
            active=True,
        )
        db.add(tenant)
        db.flush()
    return tenant


def _to_read_model(connection: Connection) -> ConnectionRead:
    return ConnectionRead(
        id=connection.id,
        tenant_id=connection.tenant_id,
        name=connection.name,
        platform=connection.platform,
        environment=connection.environment,
        base_url=connection.base_url,
        status=connection.status,
        last_test_status=connection.last_test_status,
        last_test_at=connection.last_test_at,
        credentials_masked=mask_connection_credentials(connection),
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


@router.post("", response_model=ConnectionRead, status_code=status.HTTP_201_CREATED)
def create_connection(payload: ConnectionCreate, db: Session = Depends(get_db)) -> ConnectionRead:
    if not DEFAULT_CONNECTOR_REGISTRY.is_supported(payload.platform):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported connector platform")
    _ensure_tenant(db, payload.tenant_id, payload.tenant_name)
    connection = Connection(
        id=str(uuid4()),
        tenant_id=payload.tenant_id,
        name=payload.name,
        platform=payload.platform,
        environment=payload.environment,
        base_url=payload.base_url,
        credentials_encrypted=encrypt_secret(payload.credentials),
        status="inactive",
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return _to_read_model(connection)


@router.get("", response_model=list[ConnectionRead])
def list_connections(
    tenant_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> list[ConnectionRead]:
    stmt = select(Connection).where(Connection.tenant_id == tenant_id).order_by(Connection.created_at.desc())
    return [_to_read_model(connection) for connection in db.scalars(stmt).all()]


@router.post("/{connection_id}/test", response_model=ConnectionTestResponse)
def test_connection(
    connection_id: str,
    request: Request,
    tenant_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> ConnectionTestResponse:
    connection = db.get(Connection, connection_id)
    if connection is None or connection.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    if not DEFAULT_CONNECTOR_REGISTRY.is_supported(connection.platform):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported connector platform")

    runner = IntegrationRunner(db)
    result = runner.test_connection(connection, correlation_id=request.state.correlation_id)
    db.commit()
    db.refresh(connection)
    return ConnectionTestResponse.model_validate(result)
