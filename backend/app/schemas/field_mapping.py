from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TransformationRule = Literal[
    "trim",
    "upper",
    "lower",
    "limpar_cnpj",
    "limpar_cpf",
    "remover_mascara",
    "converter_decimal",
    "converter_data_iso",
    "valor_padrao",
]


class FieldMappingBase(BaseModel):
    source_field: str
    target_field: str
    transformation_rule: TransformationRule | None = None
    default_value: str | None = None
    required: bool = False
    active: bool = True


class FieldMappingCreate(FieldMappingBase):
    pass


class FieldMappingUpdate(BaseModel):
    source_field: str | None = Field(default=None, min_length=1)
    target_field: str | None = Field(default=None, min_length=1)
    transformation_rule: TransformationRule | None = None
    default_value: str | None = None
    required: bool | None = None
    active: bool | None = None


class FieldMappingRead(FieldMappingBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    flow_id: str
    created_at: datetime
    updated_at: datetime
