from __future__ import annotations

from typing import Any


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key.lower(): value for key, value in record.items()}
