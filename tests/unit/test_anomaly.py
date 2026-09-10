"""Unit tests for targeted chaos and anomaly injection."""

from datetime import datetime, timezone
from syntheticforge.config import AnomalyConfig
from syntheticforge.generator.anomaly import AnomalyInjector
from syntheticforge.generator.lifecycle_simulator import DomainEvent


def _make_event(eid: str) -> DomainEvent:
    return DomainEvent(
        event_id=f"ev_{eid}",
        entity_name="orders",
        entity_id=eid,
        state="CREATED",
        previous_state=None,
        timestamp=datetime.now(timezone.utc),
        payload={"order_id": eid, "amount": 100.5, "status": "CREATED"},
    )


def test_duplicate_key_injection() -> None:
    cfg = AnomalyConfig(duplicate_key_rate=1.0)
    injector = AnomalyInjector(cfg, seed=42)

    # First event is recorded in seen_ids
    ev1, a1 = injector.inject(_make_event("order_1"))
    assert a1 is None  # no seen IDs prior to first

    # Second event must be injected with duplicate key
    ev2, a2 = injector.inject(_make_event("order_2"))
    assert a2 == "duplicate_key"
    assert ev2.entity_id == "order_1"
    assert injector.stats["duplicate_key"] == 1


def test_schema_mutation_injection() -> None:
    cfg = AnomalyConfig(schema_mutation_rate=1.0)
    injector = AnomalyInjector(cfg, seed=42)

    ev, a = injector.inject(_make_event("order_10"))
    assert a == "schema_mutation"
    assert (
        "__unexpected_chaos_attr__" in ev.payload
        or isinstance(ev.payload.get("amount"), str)
        or isinstance(ev.payload.get("status"), int)
    )
    assert injector.stats["schema_mutation"] == 1


def test_null_injection() -> None:
    cfg = AnomalyConfig(null_injection_rate=1.0)
    injector = AnomalyInjector(cfg, seed=42)

    ev, a = injector.inject(_make_event("order_20"))
    assert a == "null_injection"
    assert ev.payload["amount"] is None or ev.payload["status"] is None


def test_payload_corruption_injection() -> None:
    cfg = AnomalyConfig(payload_corruption_rate=1.0)
    injector = AnomalyInjector(cfg, seed=42)

    ev, a = injector.inject(_make_event("order_30"))
    assert a == "payload_corruption"
    assert "__is_poison_pill__" in ev.payload


def test_out_of_order_event_skew() -> None:
    cfg = AnomalyConfig(out_of_order_rate=1.0)
    injector = AnomalyInjector(cfg, seed=42)

    orig = _make_event("order_40")
    ev, a = injector.inject(orig)
    assert a == "out_of_order"
    assert ev.timestamp < orig.timestamp
