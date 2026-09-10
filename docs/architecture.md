# Architecture

SyntheticForge is designed for high-velocity generation and streaming of interconnected relational and event-driven data. This document outlines the core components and execution pipeline.

## System components

SyntheticForge is divided into six decoupled subsystems:

1. **Schema parser and validation**: Loads declarative YAML schemas into Pydantic models with validation of field types, foreign key definitions, and state transition probabilities.
2. **Topological dependency engine**: Uses `networkx` to represent entities as nodes and foreign key dependencies as directed edges. Cycle detection identifies circular dependencies before any generation starts.
3. **Primary key pool**: Holds emitted entity primary keys in memory. When a child entity requests a foreign key reference, the pool samples parent IDs using selected distributions (uniform, Pareto, Zipfian, Gaussian, recent-weighted).
4. **Field generator engine**: Provides deterministic and stochastic generators for standard primitives (UUIDs, ULIDs, names, emails, addresses, ISO timestamps, decimal amounts, regex patterns, Luhn-valid credit cards).
5. **Markov lifecycle simulator**: Runs state machines for entities that undergo status transitions over time. Virtual time scaling allows multi-hour business lifecycles to execute quickly while keeping timestamps coherent.
6. **Streaming and bulk sinks**: Dispatches data to Kafka topics, PostgreSQL tables using binary `COPY`, JSON Lines files, or Parquet datasets.

```
+--------------------------------------------------------------------------+
|                            SYNTHETICFORGE                                |
|                                                                          |
|  +--------------------+        +---------------------+                   |
|  | YAML Schema Config | -----> | NetworkX DAG Engine |                   |
|  +--------------------+        +----------+----------+                   |
|                                           |                              |
|                                           v                              |
|                             +---------------------------+                |
|                             | Topological Stage Planner |                |
|                             +-------------+-------------+                |
|                                           |                              |
|                   +-----------------------+---------------------+        |
|                   v                                             v        |
|     +---------------------------+                 +--------------------+ |
|     |     Entity ID Pool        |                 |   Discrete-Event   | |
|     |  (Referential Integrity)  |                 | Lifecycle Engine   | |
|     +-------------+-------------+                 +---------+----------+ |
|                   |                                         |            |
|                   +-----------------------+-----------------+            |
|                                           |                              |
|                                           v                              |
|                             +---------------------------+                |
|                             |  Targeted Chaos Injector  |                |
|                             +-------------+-------------+                |
|                                           |                              |
|           +-------------------+-----------+-----------+                  |
|           v                   v                       v                  |
|     +-----------+       +-----------+           +-----------+            |
|     |   Kafka   |       | PostgreSQL|           | JSONL /   |            |
|     | Producer  |       |  Loader   |           | Parquet   |            |
|     +-----------+       +-----------+           +-----------+            |
+--------------------------------------------------------------------------+
```

## Topological execution stages

Entities are organized into generation stages using topological generations:

- **Stage 0 (Root entities)**: Entities without incoming foreign keys (such as `customers`, `facilities`, or `users`). These are generated first.
- **Stage 1 (Direct dependencies)**: Entities depending only on Stage 0 entities (such as `orders` or `accounts`). Foreign keys sample from the parent pool populated in Stage 0.
- **Stage 2+ (Downstream entities)**: Entities depending on earlier stages (such as `payments`, `shipments`, or `transactions`).

This staging guarantees zero orphan foreign keys.

## Foreign key distribution models

When child entities reference parent IDs, the selection strategy shapes the relational landscape:

- `uniform`: Every parent entity has an equal probability of being referenced.
- `pareto`: Follows the 80/20 power law. A small subset of parents (e.g. active users) receives the vast majority of references (e.g. orders).
- `zipfian`: Frequency of parent references is inversely proportional to rank.
- `gaussian`: References cluster around the middle of the parent population.
- `recent_weighted`: Parents created more recently in simulated time have a higher probability of being sampled, modeling temporal locality.

## In-memory integrity verification

The integrity verifier loads generated outputs into an in-memory DuckDB database and executes SQL relational assertions:

- Confirms that every foreign key exists in the referenced primary key column.
- Validates that state transition timestamps are monotonically increasing.
- Asserts that terminal states have no subsequent transitions.
