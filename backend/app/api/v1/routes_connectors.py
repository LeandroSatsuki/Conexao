from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.connectors.registry import DEFAULT_CONNECTOR_REGISTRY

router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("")
def list_connectors() -> list[dict[str, object]]:
    return DEFAULT_CONNECTOR_REGISTRY.list_connectors()


@router.get("/{platform}")
def get_connector(platform: str) -> dict[str, object]:
    if not DEFAULT_CONNECTOR_REGISTRY.is_supported(platform):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    capabilities = DEFAULT_CONNECTOR_REGISTRY.get_capabilities(platform)
    return {
        "platform": platform.lower(),
        "capabilities": capabilities.model_dump(),
    }
