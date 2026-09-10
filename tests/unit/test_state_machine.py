"""Unit tests for Markov chain StateMachine and LifecycleSimulator."""

from syntheticforge.config import LifecycleConfig, TransitionConfig, load_config
from syntheticforge.generator.lifecycle_simulator import LifecycleSimulator
from syntheticforge.generator.state_machine import StateMachine


def test_state_machine_transitions_and_terminal_states() -> None:
    cfg = LifecycleConfig(
        initial_state="CREATED",
        states=["CREATED", "PAYMENT_PENDING", "COMPLETED", "CANCELLED"],
        transitions=[
            TransitionConfig(
                **{
                    "from": "CREATED",
                    "to": "PAYMENT_PENDING",
                    "probability": 1.0,
                    "delay_seconds": 2.0,
                }
            ),
            TransitionConfig(
                **{
                    "from": "PAYMENT_PENDING",
                    "to": "COMPLETED",
                    "probability": 0.8,
                    "delay_seconds": 5.0,
                }
            ),
            TransitionConfig(
                **{
                    "from": "PAYMENT_PENDING",
                    "to": "CANCELLED",
                    "probability": 0.2,
                    "delay_seconds": 1.0,
                }
            ),
        ],
    )
    sm = StateMachine(cfg, seed=42)

    assert sm.initial_state == "CREATED"
    assert sm.terminal_states == {"COMPLETED", "CANCELLED"}
    assert not sm.is_terminal("CREATED")
    assert not sm.is_terminal("PAYMENT_PENDING")
    assert sm.is_terminal("COMPLETED")
    assert sm.is_terminal("CANCELLED")

    # CREATED -> PAYMENT_PENDING with delay 2.0
    step1 = sm.next_transition("CREATED")
    assert step1 is not None
    next_s, delay = step1
    assert next_s == "PAYMENT_PENDING"
    assert delay == 2.0

    # From terminal state, next_transition is None
    assert sm.next_transition("COMPLETED") is None


def test_lifecycle_simulator_chronological_ordering() -> None:
    raw_yaml = """
    version: "1.0"
    name: "sim-test"
    entities:
      orders:
        count: 10
        primary_key: "id"
        fields:
          id: { type: "uuid" }
          amount: { type: "decimal", min: 10, max: 100 }
        lifecycle:
          initial_state: "CREATED"
          states: ["CREATED", "PROCESSING", "COMPLETED"]
          transitions:
            - from: "CREATED"
              to: "PROCESSING"
              probability: 1.0
              delay_seconds: 5.0
            - from: "PROCESSING"
              to: "COMPLETED"
              probability: 1.0
              delay_seconds: 10.0
    """
    config = load_config(raw_yaml)
    sim = LifecycleSimulator(config, speed_factor=100.0, seed=42)

    events = sim.generate_all_events()

    # 10 orders * 3 states (CREATED, PROCESSING, COMPLETED) = 30 events
    assert len(events) == 30

    # Ensure events are strictly chronologically ordered
    for i in range(len(events) - 1):
        assert events[i].timestamp <= events[i + 1].timestamp

    # Verify state progression per order
    order_states: dict[str, list[str]] = {}
    for ev in events:
        order_states.setdefault(ev.entity_id, []).append(ev.state)

    for states in order_states.values():
        assert states == ["CREATED", "PROCESSING", "COMPLETED"]
