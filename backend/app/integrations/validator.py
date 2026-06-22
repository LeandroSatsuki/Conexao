from __future__ import annotations

from typing import Any

SUPPORTED_TRANSFORMATION_RULES = {
    "trim",
    "upper",
    "lower",
    "limpar_cnpj",
    "limpar_cpf",
    "remover_mascara",
    "converter_decimal",
    "converter_data_iso",
    "valor_padrao",
}

SUPPORTED_TRIGGER_TYPES = {"manual", "scheduled"}


def validate_required_fields(payload: dict[str, Any], required_fields: list[str]) -> None:
    missing = [field for field in required_fields if field not in payload or payload[field] in (None, "")]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def validate_transformation_rule(rule: str | None) -> None:
    if rule is None:
        return
    if rule not in SUPPORTED_TRANSFORMATION_RULES:
        raise ValueError(f"Unsupported transformation rule: {rule}")


def validate_trigger_type(trigger_type: str) -> None:
    if trigger_type not in SUPPORTED_TRIGGER_TYPES:
        raise ValueError(f"Unsupported trigger type: {trigger_type}")
