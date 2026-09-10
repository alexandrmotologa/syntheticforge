# State machine lifecycles

In event-driven architectures, entities do not merely exist as static snapshots. They transition through status states over time (e.g. an order created at 10:00 AM changes to payment pending at 10:02 AM and completed at 10:15 AM).

SyntheticForge models this progression using discrete-event Markov chain simulation with temporal inter-arrival distributions.

## Defining a lifecycle

A lifecycle belongs to an entity definition in the schema YAML:

```yaml
lifecycle:
  initial_state: "CREATED"
  states: ["CREATED", "PAYMENT_PENDING", "PROCESSING", "COMPLETED", "CANCELLED"]
  transitions:
    - from: "CREATED"
      to: "PAYMENT_PENDING"
      probability: 0.95
      delay_seconds: 2.0
    - from: "CREATED"
      to: "CANCELLED"
      probability: 0.05
      delay_seconds: 5.0
    - from: "PAYMENT_PENDING"
      to: "PROCESSING"
      probability: 0.90
      delay_seconds: 4.0
    - from: "PAYMENT_PENDING"
      to: "CANCELLED"
      probability: 0.10
      delay_seconds: 1.0
    - from: "PROCESSING"
      to: "COMPLETED"
      probability: 0.98
      delay_seconds: 8.0
    - from: "PROCESSING"
      to: "CANCELLED"
      probability: 0.02
      delay_seconds: 3.0
```

## Virtual clock and speed factor

Running real-time simulations of long business workflows (such as shipment delivery taking 3 business days) is impractical in test environments.

SyntheticForge uses a virtual clock with a configurable `speed_factor`:

```bash
syntheticforge stream --schema schemas/e-commerce-flow.yaml --speed-factor 3600
```

With `speed_factor: 3600`:
- 1 wall-clock second corresponds to 1 hour of simulated business time.
- A 3-day delivery delay (72 hours) completes in 72 seconds of real execution time.
- Event timestamps emitted to Kafka or database records reflect accurate 72-hour progression.

## Terminal states

States with no outgoing transitions are treated as terminal states (e.g. `COMPLETED`, `CANCELLED`, `REJECTED`). Once an entity enters a terminal state, no further lifecycle events are scheduled for it.
