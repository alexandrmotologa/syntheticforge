<p align="center">
  <img src="docs/images/logo.png?raw=true" alt="SyntheticForge Logo" width="130" style="border-radius: 28px;" />
</p>

<h1 align="center">SyntheticForge</h1>

<p align="center">
  <b>Graph-driven relational and event stream generator with probabilistic lifecycle simulation, chaos injection, and W3C distributed tracing.</b>
</p>

<p align="center">
  <a href="https://github.com/alexandrmotologa/syntheticforge/actions/workflows/ci.yml"><img src="https://github.com/alexandrmotologa/syntheticforge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/alexandrmotologa/syntheticforge/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.12%20%7C%203.13%20%7C%203.14-blue?logo=python&logoColor=white" alt="Python Version"></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

---

SyntheticForge generates coherent relational data and temporal event streams for benchmarking distributed architectures, message brokers, and relational databases. Rather than emitting isolated mock records, SyntheticForge builds a Directed Acyclic Graph (DAG) of entities, evaluates topological dependencies to enforce 100% referential integrity, and advances entities through state machine lifecycles over simulated business time.

```
                  +-----------------------------------+
                  |   Declarative YAML Schema (DAG)   |
                  +-----------------+-----------------+
                                    |
                                    v
                  +-----------------------------------+
                  |     NetworkX Topological Sort     |
                  +-----------------+-----------------+
                                    |
            +-----------------------+-----------------------+
            |                                               |
            v                                               v
+-----------------------+                       +-----------------------+
|  Entity ID Pool &     |                       |  Markov State Machine |
|  Foreign Key Sampler  |                       |  Lifecycle Engine     |
|  (Uniform, Pareto)    |                       |  (Virtual Clock)      |
+-----------+-----------+                       +-----------+-----------+
            |                                               |
            +-----------------------+-----------------------+
                                    |
                                    v
                  +-----------------------------------+
                  |     Targeted Chaos Injection      |
                  |     (Duplicates, Mutations, DLQ)  |
                  +-----------------+-----------------+
                                    |
      +-----------------+-----------+-----------+-----------------+
      |                 |                       |                 |
      v                 v                       v                 v
+-----------+     +-----------+           +-----------+     +-----------+
|   Kafka   |     | PostgreSQL|           | JSONL /   |     |  DuckDB   |
| Streaming |     | Binary    |           | Parquet   |     | In-Memory |
| (aiokafka)|     | COPY      |           | Exporter  |     | Verifier  |
+-----------+     +-----------+           +-----------+     +-----------+
```

## Visual tour

### Interactive web studio

Launch the browser studio with `syntheticforge studio --schema <path>` to inspect topological stages, review entity state machines, and synthesize live sample records:

<p align="center">
  <img src="docs/images/studio_overview.png?raw=true" alt="SyntheticForge Web Studio Overview" width="880" style="border-radius: 10px; border: 1px solid #334155;" />
</p>

### CLI schema inspection

View dependency tiers, primary key types, foreign key distributions, and lifecycle state counts directly in your terminal:

<p align="center">
  <img src="docs/images/cli_inspect.png?raw=true" alt="SyntheticForge CLI Schema Inspection" width="880" style="border-radius: 10px;" />
</p>

### DuckDB referential integrity audit

Run zero-copy in-memory SQL audits to confirm that child records link to valid parent IDs without orphan references:

<p align="center">
  <img src="docs/images/cli_verify.png?raw=true" alt="SyntheticForge DuckDB Referential Integrity Audit" width="880" style="border-radius: 10px;" />
</p>

## Key features

- **Topological entity ordering**: Uses `networkx` to resolve dependency trees. Parent entities always generate before child entities, preventing orphan foreign keys.
- **Distribution-aware foreign key sampling**: Supports uniform random, Pareto (80/20 power law for realistic customer behavior), Zipfian, and Gaussian key sampling.
- **Probabilistic lifecycle simulation**: Emits state transition events over time driven by Markov chains with configurable inter-arrival delays.
- **Temporal time-travel engine**: Accelerates simulated time via a virtual clock (`speed_factor`), running multi-hour business workflows in seconds without distorting timestamps.
- **Targeted chaos injection**: Injects controlled rates of duplicate keys (idempotency testing), schema mutations, null values, and corrupted byte payloads (dead-letter queue validation).
- **OpenTelemetry W3C distributed tracing**: Emits valid `traceparent` and `tracestate` headers across Kafka events and HTTP Webhooks, preserving causal parent-child spans across transitions.
- **Self-referencing and deferred foreign keys**: Handles organizational hierarchies (`parent_id`) and two-pass deferred mutual dependencies (`account` and `card`).
- **High-throughput dispatchers**: Streams asynchronously to Apache Kafka topics, writes directly to PostgreSQL using binary `COPY` via `asyncpg`, delivers signed HTTP Webhooks with HMAC SHA-256, or exports to JSON Lines and Apache Parquet.
- **Soak test observability**: Exposes live Prometheus metrics (throughput, error counters, event histograms) on an async HTTP `/metrics` endpoint.
- **State checkpointing**: Saves and restores entity ID pools and virtual clock state, allowing interrupted soak tests to resume without key collisions.
- **Schema auto-introspection**: Reverse engineers existing PostgreSQL schemas into declarative SyntheticForge YAML specifications.
- **DuckDB integrity verifier**: In-memory relational auditor checking 100% referential consistency and valid lifecycle transitions on generated datasets.

## Installation

SyntheticForge requires Python 3.12 or newer. Install it using `uv` or `pip`:

```bash
# Using uv
uv tool install syntheticforge

# Or clone and install locally
git clone https://github.com/alexandrmotologa/syntheticforge.git
cd syntheticforge
uv sync
```

## Quick start

### 1. Inspect a schema DAG

View the entity dependency graph and execution order:

```bash
syntheticforge inspect schemas/e-commerce-flow.yaml
```

### 2. Generate static relational datasets

Generate 10,000 customers with corresponding orders, payments, and shipments directly to JSON Lines or Parquet:

```bash
syntheticforge generate --schema schemas/e-commerce-flow.yaml --sink jsonl --output-dir ./output
```

### 3. Stream real-time events to Kafka with live dashboard

Simulate live e-commerce transactions streamed directly to Kafka with a terminal dashboard:

```bash
syntheticforge stream \
  --schema schemas/e-commerce-flow.yaml \
  --target kafka \
  --kafka-bootstrap localhost:9092 \
  --rate 2500 \
  --speed-factor 60 \
  --dashboard
```

### 4. Verify referential integrity

Audit emitted records using the in-memory DuckDB verifier:

```bash
syntheticforge verify --data-dir ./output --schema schemas/e-commerce-flow.yaml
```

## Declarative schema specification

Schemas are defined in plain YAML. Here is an e-commerce flow defining customer orders with lifecycle transitions:

```yaml
version: "1.0"
name: "e-commerce-flow"

entities:
  customers:
    count: 1000
    primary_key: "id"
    fields:
      id: { type: "uuid" }
      name: { type: "name" }
      email: { type: "email" }
      created_at: { type: "timestamp", past_days: 30 }

  orders:
    count: 5000
    primary_key: "id"
    depends_on: ["customers"]
    foreign_keys:
      customer_id:
        entity: "customers"
        field: "id"
        distribution: "pareto"
    fields:
      id: { type: "uuid" }
      amount: { type: "decimal", min: 10.0, max: 999.99, precision: 2 }
      currency: { type: "enum", values: ["USD", "EUR", "GBP"], weights: [0.7, 0.2, 0.1] }
    lifecycle:
      initial_state: "CREATED"
      states: ["CREATED", "PAYMENT_PENDING", "COMPLETED", "CANCELLED"]
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
          to: "COMPLETED"
          probability: 0.98
          delay_seconds: 10.0
        - from: "PAYMENT_PENDING"
          to: "CANCELLED"
          probability: 0.02
          delay_seconds: 1.0

anomalies:
  duplicate_key_rate: 0.01
  schema_mutation_rate: 0.005
  payload_corruption_rate: 0.002
```

## Architecture overview

1. **Schema parser (`syntheticforge.config`)**: Validates the YAML definition against strict Pydantic v2 schemas.
2. **Topological solver (`syntheticforge.graph.schema_graph`)**: Constructs an entity graph with `networkx`, verifies absence of cyclic dependencies, and groups entities into sequential dependency tiers. Supports self-referential hierarchies and two-pass deferred foreign keys.
3. **Primary key pool (`syntheticforge.graph.pool`)**: Stores generated parent keys in memory. When child entities request foreign keys, the pool samples parent IDs using selected mathematical distributions (Pareto, Gaussian, Zipfian, Uniform).
4. **Lifecycle engine (`syntheticforge.generator.lifecycle_simulator`)**: Manages discrete-event simulations where entities evolve through Markov chains. Events carry event timestamps adjusted by the virtual clock and causal OpenTelemetry W3C trace contexts.
5. **Streaming dispatchers (`syntheticforge.streaming`)**: Batches and dispatches events to Kafka topics, PostgreSQL tables, or signed HTTP Webhook endpoints with HMAC SHA-256. Employs async workers with backpressure management.
6. **Integrity auditor (`syntheticforge.inspector.verifier`)**: Validates foreign key constraints with in-memory DuckDB queries, verifying that every child record points to an existing parent record.
7. **Simulation checkpointing (`syntheticforge.checkpoint`)**: Saves and restores primary key pools, virtual clocks, and counters to resume long-running tests without key collisions.
8. **Observability exporter (`syntheticforge.metrics`)**: Exposes Prometheus counters, gauges, and latency histograms on an asynchronous HTTP `/metrics` endpoint.
9. **Interactive Web Studio (`syntheticforge.studio`)**: Real-time browser UI for DAG inspection, state transition graphs, schema evolution rules, and live event previews.

## Interactive web studio

Launch the built-in browser studio to inspect schemas, explore entity relationships, and review transition state machines:

```bash
syntheticforge studio --schema schemas/e-commerce-flow.yaml --port 8000
```

Open `http://localhost:8000` to view the interactive DAG visualization, lifecycle diagrams, and live sample payload generation.

## Webhooks and distributed tracing

SyntheticForge injects standard W3C `traceparent` and `tracestate` headers into Kafka records and Webhook deliveries, enabling end-to-end distributed tracing across downstream microservices:

```bash
syntheticforge stream \
  --schema schemas/e-commerce-flow.yaml \
  --target webhook \
  --webhook-url https://api.example.com/events \
  --webhook-secret "your-hmac-secret" \
  --prometheus-port 9100 \
  --checkpoint-file ./checkpoint.json
```

To resume from an existing state snapshot:

```bash
syntheticforge stream \
  --schema schemas/e-commerce-flow.yaml \
  --target webhook \
  --resume-from ./checkpoint.json \
  --limit 5000
```

## Docker compose demo

A complete local sandbox with SyntheticForge, Apache Kafka (KRaft mode), PostgreSQL 16, and Kafka UI is provided:

```bash
docker compose up -d
```

Run a streaming simulation inside the container network:

```bash
docker compose run --rm syntheticforge stream \
  --schema schemas/e-commerce-flow.yaml \
  --target kafka \
  --kafka-bootstrap kafka:9092 \
  --rate 1000
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
