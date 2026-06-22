from __future__ import annotations

from datetime import datetime
from typing import Any

from app.integrations.validator import validate_transformation_rule


def _digits_only(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def apply_transformation_rule(value: Any, rule: str | None) -> Any:
    if rule is None:
        return value
    validate_transformation_rule(rule)
    text = value if isinstance(value, str) else value
    if rule == "trim" and isinstance(text, str):
        return text.strip()
    if rule == "upper" and isinstance(text, str):
        return text.upper()
    if rule == "lower" and isinstance(text, str):
        return text.lower()
    if rule == "remover_mascara" and isinstance(text, str):
        return _digits_only(text)
    if rule in {"limpar_cnpj", "limpar_cpf"} and isinstance(text, str):
        return _digits_only(text)
    if rule == "converter_decimal":
        if text in (None, ""):
            return None
        return float(str(text).replace(",", "."))
    if rule == "converter_data_iso" and isinstance(text, str):
        return datetime.fromisoformat(text).isoformat()
    if rule == "valor_padrao":
        return text
    return value


def map_fields(source_payload: dict[str, Any], mappings: list[dict[str, Any]]) -> dict[str, Any]:
    target: dict[str, Any] = {}
    for mapping in mappings:
        source_field = mapping["source_field"]
        target_field = mapping["target_field"]
        value = source_payload.get(source_field)
        default_value = mapping.get("default_value")
        rule = mapping.get("transformation_rule")
        if value in (None, "") and default_value is not None:
            value = default_value
        if rule == "valor_padrao" and value in (None, ""):
            value = default_value
        target[target_field] = apply_transformation_rule(value, rule)
    return target


def mask_payload_for_logging(payload: Any) -> Any:
    if isinstance(payload, dict):
        masked: dict[str, Any] = {}
        for key, value in payload.items():
            if key.lower() in {"token", "password", "client_secret", "appkey", "bearer", "access_token"}:
                masked[key] = "***"
            else:
                masked[key] = mask_payload_for_logging(value)
        return masked
    if isinstance(payload, list):
        return [mask_payload_for_logging(item) for item in payload]
    return payload
