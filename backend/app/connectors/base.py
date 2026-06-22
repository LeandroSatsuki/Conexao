from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class ConnectorCapabilities(BaseModel):
    supports_authentication: bool = True
    supports_test_connection: bool = True
    supports_query: bool = False
    supports_save_record: bool = False
    supports_load_records: bool = False
    supports_upsert_record: bool = False
    supports_delete_record: bool = False
    supports_raw_execution: bool = False
    supported_entities: list[str] = Field(default_factory=list)


class BaseConnector(ABC):
    @abstractmethod
    def authenticate(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    def test_connection(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_records(self, entity: str, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def get_record(self, entity: str, record_id: str, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def create_record(self, entity: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def update_record(self, entity: str, record_id: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def upsert_record(self, entity: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def delete_record(self, entity: str, record_id: str, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def execute_raw(self, statement: str, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def get_capabilities(self) -> ConnectorCapabilities:
        raise NotImplementedError

    @abstractmethod
    def normalize_error(self, error: Exception) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class ConnectorRegistration:
    platform: str
    name: str
    factory: Any
    capabilities: ConnectorCapabilities
