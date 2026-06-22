from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.connectors.registry import DEFAULT_CONNECTOR_REGISTRY
from app.connectors.sankhya.catalog import SankhyaReadOperationDefinition
from app.connectors.sankhya.services import get_catalog_read_operation, list_catalog_read_operations

router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("")
def list_connectors() -> list[dict[str, object]]:
    return DEFAULT_CONNECTOR_REGISTRY.list_connectors()


@router.get("/sankhya/read-operations", response_model=list[SankhyaReadOperationDefinition])
def list_sankhya_read_operations() -> list[SankhyaReadOperationDefinition]:
    return list_catalog_read_operations()


@router.get("/sankhya/read-operations/{operation_name}", response_model=SankhyaReadOperationDefinition)
def get_sankhya_read_operation(operation_name: str) -> SankhyaReadOperationDefinition:
    operation = get_catalog_read_operation(operation_name)
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Read operation not found")
    return operation


@router.get("/{platform}")
def get_connector(platform: str) -> dict[str, object]:
    if not DEFAULT_CONNECTOR_REGISTRY.is_supported(platform):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    capabilities = DEFAULT_CONNECTOR_REGISTRY.get_capabilities(platform)
    return {
        "platform": platform.lower(),
        "capabilities": capabilities.model_dump(),
    }
