from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.connectors.sankhya.services import resolve_read_operation_request, validate_catalog_read_operation
from app.database.session import get_db
from app.integrations.runner import IntegrationRunner
from app.models.connection import Connection
from app.models.field_mapping import FieldMapping
from app.models.integration_flow import IntegrationFlow
from app.models.sync_job import SyncJob
from app.models.tenant import Tenant
from app.schemas.field_mapping import FieldMappingCreate, FieldMappingRead
from app.schemas.integration_flow import IntegrationFlowCreate, IntegrationFlowRead, IntegrationFlowUpdate
from app.schemas.sync_job import FlowRunRequest, FlowRunResponse
from app.workers.tasks import execute_flow_job

router = APIRouter(prefix="/flows", tags=["flows"])


def _flow_to_read(flow: IntegrationFlow) -> IntegrationFlowRead:
    return IntegrationFlowRead.model_validate(flow)


def _mapping_to_read(mapping: FieldMapping) -> FieldMappingRead:
    return FieldMappingRead.model_validate(mapping)


def _load_flow_or_404(db: Session, flow_id: str) -> IntegrationFlow:
    flow = db.get(IntegrationFlow, flow_id)
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    return flow


def _load_connection_or_404(db: Session, connection_id: str) -> Connection:
    connection = db.get(Connection, connection_id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return connection


def _load_tenant_or_404(db: Session, tenant_id: str) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


def _validate_flow_connections(
    db: Session,
    tenant_id: str,
    source_connection_id: str,
    target_connection_id: str,
) -> None:
    source_connection = _load_connection_or_404(db, source_connection_id)
    target_connection = _load_connection_or_404(db, target_connection_id)
    if source_connection.tenant_id != tenant_id or target_connection.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Flow connections must belong to the same tenant",
        )


def _validate_read_operation_config(
    config_json: dict[str, object] | None,
    *,
    source_entity: str | None,
    connection_environment: str | None = None,
) -> None:
    try:
        resolution = resolve_read_operation_request(config_json, source_entity=source_entity)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if resolution is None:
        return
    issues = validate_catalog_read_operation(resolution, connection_environment=connection_environment)
    if issues:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="; ".join(issues))


@router.post("", response_model=IntegrationFlowRead, status_code=status.HTTP_201_CREATED)
def create_flow(payload: IntegrationFlowCreate, db: Session = Depends(get_db)) -> IntegrationFlowRead:
    _load_tenant_or_404(db, payload.tenant_id)
    _validate_flow_connections(
        db,
        payload.tenant_id,
        payload.source_connection_id,
        payload.target_connection_id,
    )
    source_connection = _load_connection_or_404(db, payload.source_connection_id)
    _validate_read_operation_config(
        payload.config_json,
        source_entity=payload.source_entity,
        connection_environment=source_connection.environment,
    )
    flow = IntegrationFlow(
        id=str(uuid4()),
        tenant_id=payload.tenant_id,
        name=payload.name,
        source_connection_id=payload.source_connection_id,
        target_connection_id=payload.target_connection_id,
        source_entity=payload.source_entity,
        target_entity=payload.target_entity,
        config_json=payload.config_json,
        trigger_type=payload.trigger_type,
        schedule_cron=payload.schedule_cron,
        active=payload.active,
    )
    db.add(flow)
    db.commit()
    db.refresh(flow)
    return _flow_to_read(flow)


@router.get("", response_model=list[IntegrationFlowRead])
def list_flows(
    tenant_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> list[IntegrationFlowRead]:
    _load_tenant_or_404(db, tenant_id)
    flows = db.scalars(
        select(IntegrationFlow)
        .where(IntegrationFlow.tenant_id == tenant_id)
        .order_by(IntegrationFlow.created_at.desc())
    ).all()
    return [_flow_to_read(flow) for flow in flows]


@router.get("/{flow_id}", response_model=IntegrationFlowRead)
def get_flow(flow_id: str, db: Session = Depends(get_db)) -> IntegrationFlowRead:
    return _flow_to_read(_load_flow_or_404(db, flow_id))


@router.patch("/{flow_id}", response_model=IntegrationFlowRead)
def update_flow(flow_id: str, payload: IntegrationFlowUpdate, db: Session = Depends(get_db)) -> IntegrationFlowRead:
    flow = _load_flow_or_404(db, flow_id)
    changes = payload.model_dump(exclude_unset=True)

    source_connection_id = changes.get("source_connection_id", flow.source_connection_id)
    target_connection_id = changes.get("target_connection_id", flow.target_connection_id)
    if "source_connection_id" in changes or "target_connection_id" in changes:
        _validate_flow_connections(db, flow.tenant_id, source_connection_id, target_connection_id)
    source_connection = _load_connection_or_404(db, source_connection_id)
    _validate_read_operation_config(
        changes.get("config_json"),
        source_entity=changes.get("source_entity", flow.source_entity),
        connection_environment=source_connection.environment,
    )

    for field_name, value in changes.items():
        setattr(flow, field_name, value)

    db.commit()
    db.refresh(flow)
    return _flow_to_read(flow)


@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flow(flow_id: str, db: Session = Depends(get_db)) -> None:
    flow = _load_flow_or_404(db, flow_id)
    mapping_count = db.scalar(select(func.count(FieldMapping.id)).where(FieldMapping.flow_id == flow_id)) or 0
    job_count = db.scalar(select(func.count(SyncJob.id)).where(SyncJob.flow_id == flow_id)) or 0
    if mapping_count > 0 or job_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Flow has linked mappings or jobs and cannot be deleted",
        )
    db.delete(flow)
    db.commit()


@router.post("/{flow_id}/run", response_model=FlowRunResponse)
def run_flow(
    flow_id: str,
    payload: FlowRunRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> FlowRunResponse:
    flow = _load_flow_or_404(db, flow_id)
    runner = IntegrationRunner(db)
    try:
        job = runner.prepare_flow_job(
            flow=flow,
            source_payload=payload.source_payload,
            correlation_id=request.state.correlation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(job)
    if job.status == "pending" and not payload.sync:
        async_result = execute_flow_job.apply_async(args=[job.id])
        task_id = async_result.id
    else:
        task_id = None
        if payload.sync and job.status == "pending":
            job = runner.execute_job(job.id, correlation_id=request.state.correlation_id)
            db.commit()
            db.refresh(job)
    return FlowRunResponse(
        job_id=job.id,
        flow_id=job.flow_id or flow.id,
        tenant_id=job.tenant_id,
        status=job.status,
        task_id=task_id,
        correlation_id=job.correlation_id,
        idempotency_key=job.idempotency_key,
        message="Job queued"
        if job.status == "pending"
        else "Duplicate payload ignored"
        if job.status == "ignored"
        else "Job executed synchronously",
    )


@router.post("/{flow_id}/validate")
def validate_flow(flow_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    flow = _load_flow_or_404(db, flow_id)
    source_connection = _load_connection_or_404(db, flow.source_connection_id)
    target_connection = _load_connection_or_404(db, flow.target_connection_id)
    details: list[str] = []
    valid = True

    if source_connection.tenant_id != flow.tenant_id or target_connection.tenant_id != flow.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Flow tenant mismatch")

    if flow.source_connection.platform.lower() == "sankhya":
        try:
            resolution = resolve_read_operation_request(flow.config_json, source_entity=flow.source_entity)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if resolution is None:
            details.append("Missing Sankhya read-only configuration")
            valid = False
        else:
            issues = validate_catalog_read_operation(
                resolution,
                connection_environment=source_connection.environment,
            )
            if issues:
                details.extend(issues)
                valid = False
            else:
                details.append("Sankhya read-only configuration valid")
            details.append(f"operation={resolution.config.operation}")
            details.append(f"entity_name={resolution.config.entity_name}")
            details.append(f"fields={len(resolution.config.fields)}")
            details.append(f"limit={resolution.config.limit}")
    else:
        details.append("Non-Sankhya flow validation complete")

    return {"flow_id": flow.id, "tenant_id": flow.tenant_id, "valid": valid, "details": details}


@router.get("/{flow_id}/mappings", response_model=list[FieldMappingRead])
def list_flow_mappings(flow_id: str, db: Session = Depends(get_db)) -> list[FieldMappingRead]:
    _load_flow_or_404(db, flow_id)
    mappings = db.scalars(
        select(FieldMapping).where(FieldMapping.flow_id == flow_id).order_by(FieldMapping.created_at.desc())
    ).all()
    return [_mapping_to_read(mapping) for mapping in mappings]


@router.post("/{flow_id}/mappings", response_model=FieldMappingRead, status_code=status.HTTP_201_CREATED)
def create_flow_mapping(
    flow_id: str,
    payload: FieldMappingCreate,
    db: Session = Depends(get_db),
) -> FieldMappingRead:
    flow = _load_flow_or_404(db, flow_id)
    mapping = FieldMapping(
        id=str(uuid4()),
        tenant_id=flow.tenant_id,
        flow_id=flow.id,
        source_field=payload.source_field,
        target_field=payload.target_field,
        transformation_rule=payload.transformation_rule,
        default_value=payload.default_value,
        required=payload.required,
        active=payload.active,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return _mapping_to_read(mapping)
