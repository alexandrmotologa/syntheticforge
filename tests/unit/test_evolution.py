"""Unit tests for in-flight schema drift and evolution."""

from syntheticforge.config import FieldConfig, FieldType, SchemaEvolutionConfig, load_config
from syntheticforge.generator.lifecycle_simulator import LifecycleSimulator


def test_schema_evolution_drift_trigger() -> None:
    schema_yaml = """
    version: "1.0"
    name: "evolution-test"
    entities:
      orders:
        count: 10
        primary_key: "id"
        fields:
          id: { type: "uuid" }
          total: { type: "decimal", min: 10, max: 100 }
        lifecycle:
          initial_state: "CREATED"
          states: ["CREATED", "PROCESSING", "COMPLETED"]
          transitions:
            - from: "CREATED"
              to: "PROCESSING"
              probability: 1.0
              delay_seconds: 1.0
            - from: "PROCESSING"
              to: "COMPLETED"
              probability: 1.0
              delay_seconds: 2.0
    """
    config = load_config(schema_yaml)
    # Configure in-flight schema migration: after 10 events, evolve to v2.0
    # adding loyalty_points and renaming total -> amount
    config.evolutions["orders"] = [
        SchemaEvolutionConfig(
            trigger_event_count=10,
            target_version="2.0",
            add_fields={
                "loyalty_tier": FieldConfig(type=FieldType.ENUM, values=["GOLD", "SILVER"])
            },
            rename_fields={"total": "amount"},
        )
    ]

    sim = LifecycleSimulator(config, seed=42)
    events = sim.generate_all_events()

    assert len(events) == 30  # 10 orders * 3 states

    # First 9 events should be version 1.0 with 'total'
    v1_events = events[:9]
    for ev in v1_events:
        assert ev.schema_version == "1.0"
        assert "total" in ev.payload

    # Events from 10 onwards should be evolved to version 2.0 with 'amount' and 'loyalty_tier'
    v2_events = events[10:]
    for ev in v2_events:
        assert ev.schema_version == "2.0"
        assert "amount" in ev.payload
        assert "total" not in ev.payload
        assert "loyalty_tier" in ev.payload
