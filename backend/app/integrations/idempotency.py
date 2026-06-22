from __future__ import annotations

import hashlib
import json
from typing import Any


def _normalize_payload(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def build_idempotency_key(
    *,
    tenant_id: str,
    flow_id: str | None,
    source_entity: str | None = None,
    target_entity: str | None = None,
    external_id: str | None = None,
    payload: Any,
) -> str:
    data = {
        "tenant_id": tenant_id,
        "flow_id": flow_id,
        "payload": payload,
    }
    digest = hashlib.sha256(_normalize_payload(data).encode("utf-8")).hexdigest()
    return digest
