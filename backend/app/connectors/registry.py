from __future__ import annotations

from typing import Any

from app.connectors.base import ConnectorCapabilities, ConnectorRegistration
from app.connectors.sankhya.client import SankhyaClient
from app.connectors.sankhya.schemas import SankhyaCredentials


class ConnectorRegistry:
    def __init__(self) -> None:
        self._registrations: dict[str, ConnectorRegistration] = {}

    def register(
        self,
        platform: str,
        name: str,
        factory: Any,
        capabilities: ConnectorCapabilities,
    ) -> None:
        self._registrations[platform.lower()] = ConnectorRegistration(
            platform=platform.lower(),
            name=name,
            factory=factory,
            capabilities=capabilities,
        )

    def is_supported(self, platform: str) -> bool:
        return platform.lower() in self._registrations

    def create(self, platform: str, credentials: SankhyaCredentials) -> Any:
        registration = self._registrations.get(platform.lower())
        if registration is None:
            raise KeyError(f"Unsupported connector platform: {platform}")
        return registration.factory(credentials)

    def get_capabilities(self, platform: str) -> ConnectorCapabilities:
        registration = self._registrations.get(platform.lower())
        if registration is None:
            raise KeyError(f"Unsupported connector platform: {platform}")
        return registration.capabilities

    def list_connectors(self) -> list[dict[str, Any]]:
        return [
            {
                "platform": registration.platform,
                "name": registration.name,
                "capabilities": registration.capabilities.model_dump(),
            }
            for registration in self._registrations.values()
        ]


def build_default_registry() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register(
        platform="sankhya",
        name="Sankhya",
        factory=lambda credentials: SankhyaClient(credentials=credentials),
        capabilities=SankhyaClient.default_capabilities(),
    )
    return registry


DEFAULT_CONNECTOR_REGISTRY = build_default_registry()
