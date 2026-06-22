from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.connectors.sankhya.schemas import SankhyaReadOperationConfig


class SankhyaReadOperationDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    entity_name: str = Field(min_length=1)
    allowed_fields: tuple[str, ...] = Field(default_factory=tuple)
    default_fields: tuple[str, ...] = Field(default_factory=tuple)
    sensitive_fields: tuple[str, ...] = Field(default_factory=tuple)
    default_limit: int = Field(default=10, ge=1, le=50)
    max_limit: int = Field(default=50, ge=1, le=50)
    allow_criteria: bool = True
    read_only: bool = True
    production_allowed: bool = False

    @model_validator(mode="after")
    def _validate_definition(self) -> SankhyaReadOperationDefinition:
        allowed = set(self.allowed_fields)
        if not allowed:
            raise ValueError("allowed_fields must not be empty")
        if not set(self.default_fields).issubset(allowed):
            raise ValueError("default_fields must be a subset of allowed_fields")
        if not set(self.sensitive_fields).issubset(allowed):
            raise ValueError("sensitive_fields must be a subset of allowed_fields")
        if self.default_limit > self.max_limit:
            raise ValueError("default_limit must be less than or equal to max_limit")
        if not self.read_only:
            raise ValueError("Sankhya read operations must be read only")
        return self

    def to_read_model(self) -> dict[str, Any]:
        return {
            "operation_name": self.operation_name,
            "description": self.description,
            "entity_name": self.entity_name,
            "allowed_fields": list(self.allowed_fields),
            "default_fields": list(self.default_fields),
            "sensitive_fields": list(self.sensitive_fields),
            "default_limit": self.default_limit,
            "max_limit": self.max_limit,
            "allow_criteria": self.allow_criteria,
            "read_only": self.read_only,
            "production_allowed": self.production_allowed,
        }


@dataclass(frozen=True)
class SankhyaReadOperationResolution:
    config: SankhyaReadOperationConfig
    definition: SankhyaReadOperationDefinition | None = None

    @property
    def sensitive_fields(self) -> tuple[str, ...]:
        if self.definition is None:
            return ()
        return self.definition.sensitive_fields

    @property
    def read_only(self) -> bool:
        if self.definition is None:
            return True
        return self.definition.read_only

    @property
    def production_allowed(self) -> bool:
        if self.definition is None:
            return False
        return self.definition.production_allowed


_READ_OPERATIONS: tuple[SankhyaReadOperationDefinition, ...] = (
    SankhyaReadOperationDefinition(
        operation_name="sankhya_read_partner",
        description="Read partner records from Sankhya in a controlled way",
        entity_name="Parceiro",
        allowed_fields=("CODPARC", "NOMEPARC", "CGC_CPF", "TIPPESSOA", "ATIVO"),
        default_fields=("CODPARC", "NOMEPARC", "CGC_CPF"),
        sensitive_fields=("CGC_CPF",),
        default_limit=10,
        max_limit=50,
        allow_criteria=True,
        read_only=True,
        production_allowed=False,
    ),
    SankhyaReadOperationDefinition(
        operation_name="sankhya_read_product",
        description="Read product records from Sankhya in a controlled way",
        entity_name="Produto",
        allowed_fields=("CODPROD", "DESCRPROD", "REFERENCIA", "MARCA", "ATIVO"),
        default_fields=("CODPROD", "DESCRPROD"),
        sensitive_fields=(),
        default_limit=10,
        max_limit=50,
        allow_criteria=True,
        read_only=True,
        production_allowed=False,
    ),
    SankhyaReadOperationDefinition(
        operation_name="sankhya_read_seller",
        description="Read seller records from Sankhya in a controlled way",
        entity_name="Vendedor",
        allowed_fields=("CODVEND", "APELIDO", "ATIVO"),
        default_fields=("CODVEND", "APELIDO"),
        sensitive_fields=(),
        default_limit=10,
        max_limit=50,
        allow_criteria=True,
        read_only=True,
        production_allowed=False,
    ),
    SankhyaReadOperationDefinition(
        operation_name="sankhya_read_company",
        description="Read company records from Sankhya in a controlled way",
        entity_name="Empresa",
        allowed_fields=("CODEMP", "RAZAOSOCIAL", "NOMEFANTASIA", "CGC"),
        default_fields=("CODEMP", "RAZAOSOCIAL", "NOMEFANTASIA", "CGC"),
        sensitive_fields=("CGC",),
        default_limit=10,
        max_limit=20,
        allow_criteria=True,
        read_only=True,
        production_allowed=False,
    ),
)

READ_OPERATION_CATALOG: dict[str, SankhyaReadOperationDefinition] = {
    operation.operation_name: operation for operation in _READ_OPERATIONS
}


def list_read_operations() -> list[SankhyaReadOperationDefinition]:
    return list(_READ_OPERATIONS)


def get_read_operation(operation_name: str) -> SankhyaReadOperationDefinition | None:
    return READ_OPERATION_CATALOG.get(operation_name)


def _normalize_fields(fields: Any) -> list[str]:
    if isinstance(fields, str):
        return [field.strip() for field in fields.split(",") if field.strip()]
    if isinstance(fields, list):
        return [str(field).strip() for field in fields if str(field).strip()]
    if isinstance(fields, tuple):
        return [str(field).strip() for field in fields if str(field).strip()]
    return []


def resolve_read_operation_request(
    config_json: dict[str, Any] | None,
    *,
    source_entity: str | None = None,
) -> SankhyaReadOperationResolution | None:
    if not config_json:
        return None

    payload = dict(config_json)
    operation_name = str(payload.get("operation") or "").strip()
    if not operation_name:
        return None

    if operation_name == "sankhya_load_records":
        if source_entity and not payload.get("entity_name"):
            payload["entity_name"] = source_entity
        config = SankhyaReadOperationConfig.model_validate(payload)
        return SankhyaReadOperationResolution(config=config, definition=None)

    definition = get_read_operation(operation_name)
    if definition is None:
        raise ValueError(f"Unsupported Sankhya read operation: {operation_name}")

    if source_entity and payload.get("entity_name") and str(payload["entity_name"]).strip() != source_entity:
        raise ValueError("entity_name must match the Sankhya catalog operation")

    payload["entity_name"] = payload.get("entity_name") or definition.entity_name
    fields = _normalize_fields(payload.get("fields"))
    if not fields:
        fields = list(definition.default_fields)
    payload["fields"] = fields
    if payload.get("limit") is None:
        payload["limit"] = definition.default_limit
    else:
        payload["limit"] = int(payload["limit"])
    payload.setdefault("mode", "mock")
    payload.setdefault("criteria", None)

    config = SankhyaReadOperationConfig.model_validate(payload)
    invalid_fields = [field for field in config.fields if field not in definition.allowed_fields]
    if invalid_fields:
        raise ValueError(f"Fields not allowed for {definition.operation_name}: {', '.join(invalid_fields)}")
    if config.limit > definition.max_limit:
        raise ValueError(
            f"Limit {config.limit} exceeds max_limit {definition.max_limit} for {definition.operation_name}"
        )
    if config.entity_name != definition.entity_name:
        raise ValueError(f"entity_name must be {definition.entity_name} for {definition.operation_name}")
    return SankhyaReadOperationResolution(config=config, definition=definition)


def validate_read_operation_resolution(
    resolution: SankhyaReadOperationResolution,
    *,
    connection_environment: str | None = None,
) -> list[str]:
    issues: list[str] = []
    definition = resolution.definition
    config = resolution.config

    if definition is not None:
        if not definition.read_only:
            issues.append("Operation is not read-only")
        if not definition.production_allowed and config.mode == "real":
            environment = (connection_environment or "").strip().lower()
            if environment != "sandbox":
                issues.append("Real mode is restricted to sandbox connections for catalog operations")
    elif config.mode == "real":
        environment = (connection_environment or "").strip().lower()
        if environment != "sandbox":
            issues.append("Real mode is restricted to sandbox connections")

    return issues
