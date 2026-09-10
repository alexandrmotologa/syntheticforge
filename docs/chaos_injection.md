# Chaos injection and anomaly testing

Testing distributed systems requires verifying how services respond to malformed payloads, network retries, and schema violations. SyntheticForge includes a targeted chaos injection engine with configurable anomaly rates.

## Anomaly types

### 1. Duplicate keys (`duplicate_key_rate`)

Re-emits a previously generated primary key with identical or modified payload attributes.

- **Target scenario**: Testing idempotency gates and deduplication caches (e.g. IdemGate).
- **Example configuration**: `duplicate_key_rate: 0.02` (2% of messages carry duplicate IDs).

### 2. Schema mutation (`schema_mutation_rate`)

Alters field types or introduces unexpected fields in the generated payload.

- **Target scenario**: Validating schema registry enforcement and backward compatibility checks (e.g. ContractHub).
- **Example mutation**: Replacing an integer field with a string or injecting an unrecognized attribute.

### 3. Null injection (`null_injection_rate`)

Replaces values in required fields with `null`.

- **Target scenario**: Ensuring downstream ingestion pipelines enforce non-null constraints and handle edge cases gracefully without crashing.

### 4. Payload corruption (`payload_corruption_rate`)

Replaces valid JSON payloads with corrupted byte sequences or unparseable JSON strings.

- **Target scenario**: Verifying dead-letter queue (DLQ) routing, poison pill handling, and error logging (e.g. EventLens).

### 5. Out-of-order events (`out_of_order_rate`)

Emits child lifecycle events before parent creation events or backdates event timestamps.

- **Target scenario**: Validating stream processing watermarks, event-time windowing, and late-arriving event handlers.
