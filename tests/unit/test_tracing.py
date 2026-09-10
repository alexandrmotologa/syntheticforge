"""Unit tests for OpenTelemetry and W3C Trace Context engine."""

import re

from syntheticforge.config import load_config
from syntheticforge.generator.lifecycle_simulator import LifecycleSimulator
from syntheticforge.tracing import (
    TraceContext,
)


def test_w3c_traceparent_format() -> None:
    trace = TraceContext.new_root()
    assert len(trace.trace_id) == 32
    assert len(trace.span_id) == 16
    assert trace.parent_span_id is None

    tp = trace.traceparent
    # Standard W3C regex: 00-{32hex}-{16hex}-01
    assert re.match(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-01$", tp)


def test_child_span_inherits_trace_id() -> None:
    parent = TraceContext.new_root()
    child = parent.create_child()

    assert child.trace_id == parent.trace_id
    assert child.span_id != parent.span_id
    assert child.parent_span_id == parent.span_id
    assert child.traceparent.split("-")[1] == parent.traceparent.split("-")[1]


def test_causal_trace_continuity_in_lifecycle_events() -> None:
    schema_yaml = """
    version: "1.0"
    name: "trace-test"
    entities:
      customers:
        count: 5
        primary_key: "id"
        fields:
          id: { type: "uuid" }

      orders:
        count: 10
        primary_key: "id"
        depends_on: ["customers"]
        foreign_keys:
          customer_id:
            entity: "customers"
            field: "id"
        fields:
          id: { type: "uuid" }
        lifecycle:
          initial_state: "CREATED"
          states: ["CREATED", "COMPLETED"]
          transitions:
            - from: "CREATED"
              to: "COMPLETED"
              probability: 1.0
              delay_seconds: 1.0
    """
    config = load_config(schema_yaml)
    sim = LifecycleSimulator(config, seed=42)
    events = sim.generate_all_events()

    # All events should have trace_context populated
    for ev in events:
        assert ev.trace_context is not None
        assert "traceparent" in ev.to_dict()

    # Find customer events and order events
    cust_events = [e for e in events if e.entity_name == "customers"]
    order_events = [e for e in events if e.entity_name == "orders"]

    # Verify orders inherit trace_id from their parent customer!
    for o_ev in order_events:
        parent_cust_id = o_ev.payload["customer_id"]
        matching_cust = next(c for c in cust_events if c.entity_id == parent_cust_id)
        assert o_ev.trace_context.trace_id == matching_cust.trace_context.trace_id
