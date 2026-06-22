from __future__ import annotations

from typing import Any

from app.core.encryption import mask_secret

SENSITIVE_FIELD_NAMES = {
    "cpf",
    "cnpj",
    "cgc_cpf",
    "cpf_cnpj",
    "document",
    "doc",
}


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key.lower(): value for key, value in record.items()}


def extract_records(raw_response: Any) -> list[dict[str, Any]]:
    if isinstance(raw_response, list):
        return [record for record in raw_response if isinstance(record, dict)]
    if not isinstance(raw_response, dict):
        return []

    candidates: list[Any] = []
    if isinstance(raw_response.get("responseBody"), dict):
        response_body = raw_response["responseBody"]
        candidates.extend(
            [
                response_body.get("entities"),
                response_body.get("records"),
                response_body.get("data"),
            ]
        )
    candidates.extend([raw_response.get("entities"), raw_response.get("records"), raw_response.get("data")])

    for candidate in candidates:
        if isinstance(candidate, list):
            return [record for record in candidate if isinstance(record, dict)]
        if isinstance(candidate, dict):
            nested = candidate.get("records") or candidate.get("data")
            if isinstance(nested, list):
                return [record for record in nested if isinstance(record, dict)]
    return []


def select_record_fields(record: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    if not fields or fields == ["*"]:
        return dict(record)
    selected: dict[str, Any] = {}
    lower_map = {key.lower(): key for key in record}
    for field in fields:
        source_key = field if field in record else lower_map.get(field.lower())
        if source_key is not None:
            selected[field] = record[source_key]
    return selected


def mask_read_record(record: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in record.items():
        if key.lower() in SENSITIVE_FIELD_NAMES:
            masked[key] = mask_secret(value)
        else:
            masked[key] = value
    return masked


def normalize_read_records_response(
    raw_response: Any,
    *,
    fields: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    records = extract_records(raw_response)
    normalized: list[dict[str, Any]] = []
    for record in records[:limit]:
        normalized.append(mask_read_record(select_record_fields(record, fields)))
    return normalized


def count_records(raw_response: Any) -> int:
    if isinstance(raw_response, list):
        return len(raw_response)
    if not isinstance(raw_response, dict):
        return 0

    candidates: list[Any] = []
    response_body = raw_response.get("responseBody")
    if isinstance(response_body, dict):
        candidates.extend([response_body.get("entities"), response_body.get("records"), response_body.get("data")])
    candidates.extend([raw_response.get("entities"), raw_response.get("records"), raw_response.get("data")])

    for candidate in candidates:
        if isinstance(candidate, list):
            return len(candidate)
        if isinstance(candidate, dict):
            total = candidate.get("total")
            if isinstance(total, int):
                return total
            if isinstance(total, str) and total.isdigit():
                return int(total)
            nested = candidate.get("records") or candidate.get("data")
            if isinstance(nested, list):
                return len(nested)
    return 0
