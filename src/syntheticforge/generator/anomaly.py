"""Targeted chaos and anomaly injection engine for resiliency testing."""

from __future__ import annotations

from datetime import timedelta
import random
from typing import Any

from syntheticforge.config import AnomalyConfig
from syntheticforge.generator.lifecycle_simulator import DomainEvent


class AnomalyInjector:
    """Injects controlled anomalies into domain events according to AnomalyConfig."""

    def __init__(self, config: AnomalyConfig, seed: int | None = None) -> None:
        self.config = config
        self._rng = random.Random(seed)
        self._seen_ids: list[str] = []
        self.stats: dict[str, int] = {
            "duplicate_key": 0,
            "schema_mutation": 0,
            "null_injection": 0,
            "payload_corruption": 0,
            "out_of_order": 0,
        }

    def inject(
        self, event: DomainEvent, past_events: list[DomainEvent] | None = None
    ) -> tuple[DomainEvent, str | None]:
        """Optionally inject an anomaly into the event. Returns (event, anomaly_type_or_None)."""
        anomaly_type: str | None = None
        mutated_payload = dict(event.payload)
        mutated_id = event.entity_id
        mutated_ts = event.timestamp

        # 1. Duplicate Key Anomaly (testing idempotency gates)
        if (
            self.config.duplicate_key_rate > 0
            and self._seen_ids
            and self._rng.random() < self.config.duplicate_key_rate
        ):
            mutated_id = self._rng.choice(self._seen_ids)
            anomaly_type = "duplicate_key"
            self.stats["duplicate_key"] += 1

        # 2. Schema Mutation Anomaly (testing schema registry / contract enforcement)
        elif (
            self.config.schema_mutation_rate > 0
            and self._rng.random() < self.config.schema_mutation_rate
        ):
            # Inject an invalid type or unexpected field
            choice = self._rng.choice(["type_mutation", "unexpected_field"])
            if choice == "unexpected_field":
                mutated_payload["__unexpected_chaos_attr__"] = "MUTATED_SCHEMA_VALUE"
            else:
                for k, v in mutated_payload.items():
                    if isinstance(v, (int, float)):
                        mutated_payload[k] = f"MALFORMED_NUMERIC_{v}"
                        break
                    elif isinstance(v, str) and not k.endswith("id"):
                        mutated_payload[k] = 99999999
                        break
            anomaly_type = "schema_mutation"
            self.stats["schema_mutation"] += 1

        # 3. Null Injection Anomaly (testing non-null constraints)
        elif (
            self.config.null_injection_rate > 0
            and self._rng.random() < self.config.null_injection_rate
        ):
            candidates = [k for k in mutated_payload if not k.endswith("id")]
            if candidates:
                chosen_key = self._rng.choice(candidates)
                mutated_payload[chosen_key] = None
                anomaly_type = "null_injection"
                self.stats["null_injection"] += 1

        # 4. Payload Corruption Anomaly (testing DLQ / poison pill handling)
        elif (
            self.config.payload_corruption_rate > 0
            and self._rng.random() < self.config.payload_corruption_rate
        ):
            mutated_payload["__corrupted_raw_bytes__"] = "b'\\x00\\xff\\xfeMALFORMED_UTF8_PAYLOAD'"
            mutated_payload["__is_poison_pill__"] = True
            anomaly_type = "payload_corruption"
            self.stats["payload_corruption"] += 1

        # 5. Out of Order Event (testing watermark / stream reordering)
        elif (
            self.config.out_of_order_rate > 0
            and self._rng.random() < self.config.out_of_order_rate
        ):
            skew_seconds = self._rng.uniform(30.0, 300.0)
            mutated_ts = mutated_ts - timedelta(seconds=skew_seconds)
            anomaly_type = "out_of_order"
            self.stats["out_of_order"] += 1

        self._seen_ids.append(event.entity_id)
        if len(self._seen_ids) > 10000:
            # Cap cache size to avoid unbounded memory in long runs
            self._seen_ids = self._seen_ids[-5000:]

        result_event = DomainEvent(
            event_id=event.event_id,
            entity_name=event.entity_name,
            entity_id=mutated_id,
            state=event.state,
            previous_state=event.previous_state,
            timestamp=mutated_ts,
            payload=mutated_payload,
        )

        return result_event, anomaly_type
