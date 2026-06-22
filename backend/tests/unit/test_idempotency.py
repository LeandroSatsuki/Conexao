from __future__ import annotations

from app.integrations.idempotency import build_idempotency_key


def test_idempotency_key_is_stable_for_same_payload():
    key1 = build_idempotency_key(
        tenant_id="tenant-a",
        flow_id="flow-a",
        source_entity="pedidos",
        target_entity="orders",
        external_id="123",
        payload={"a": 1, "b": 2},
    )
    key2 = build_idempotency_key(
        tenant_id="tenant-a",
        flow_id="flow-a",
        source_entity="pedidos",
        target_entity="orders",
        external_id="123",
        payload={"b": 2, "a": 1},
    )

    assert key1 == key2


def test_idempotency_key_changes_when_payload_changes():
    key1 = build_idempotency_key(
        tenant_id="tenant-a",
        flow_id="flow-a",
        source_entity="pedidos",
        target_entity="orders",
        external_id="123",
        payload={"a": 1},
    )
    key2 = build_idempotency_key(
        tenant_id="tenant-a",
        flow_id="flow-a",
        source_entity="pedidos",
        target_entity="orders",
        external_id="123",
        payload={"a": 2},
    )

    assert key1 != key2
