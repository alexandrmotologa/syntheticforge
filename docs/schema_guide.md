# Schema guide

This guide documents the YAML syntax used to define entities, relationships, field generators, lifecycles, and anomalies in SyntheticForge.

## Top-level structure

Every schema contains metadata, an `entities` dictionary, and an optional `anomalies` section:

```yaml
version: "1.0"
name: "my-custom-pipeline"
description: "Pipeline description"

entities:
  # Entity definitions here

anomalies:
  # Chaos injection rates here
```

## Entity configuration

Each entry in `entities` specifies how records of that type are generated:

```yaml
entities:
  orders:
    count: 5000              # Total records to generate
    primary_key: "id"        # Name of the primary key field
    depends_on: ["customers"] # Parent entities that must generate first
    foreign_keys:
      customer_id:
        entity: "customers"
        field: "id"
        distribution: "pareto" # uniform, pareto, zipfian, gaussian, recent_weighted
    fields:
      id: { type: "uuid" }
      status: { type: "enum", values: ["OPEN", "CLOSED"], weights: [0.8, 0.2] }
```

## Supported field generator types

| Type | Parameters | Description |
| :--- | :--- | :--- |
| `uuid` | (none) | Generates random UUIDv4 string. |
| `ulid` | (none) | Generates monotonically sortable ULID string. |
| `integer` | `min`, `max` | Uniform random integer between `min` and `max`. |
| `sequence` | `start`, `step` | Monotonically increasing sequential integer. |
| `decimal` | `min`, `max`, `precision` | Floating-point or fixed decimal value. |
| `name` | (none) | Realistic human name generated with Faker. |
| `email` | `domain` (optional) | Realistic email address. |
| `credit_card`| (none) | Luhn-valid 16-digit credit card number. |
| `timestamp` | `past_days`, `future_days` | ISO 8601 formatted timestamp string. |
| `enum` | `values`, `weights` | Categorical selection with optional weighted probabilities. |
| `regex` | `pattern` | Generates strings matching regular expression patterns. |
| `template` | `format` | Interpolated string referencing other field values. |

## Foreign key sampling distributions

- `uniform`: Each parent ID has equal likelihood of selection.
- `pareto`: Power law distribution simulating real-world concentration (e.g. power buyers).
- `zipfian`: Heavy-tailed rank-frequency distribution.
- `gaussian`: Normal distribution centered on the parent population.
- `recent_weighted`: Prioritizes IDs generated latest in simulated time.
