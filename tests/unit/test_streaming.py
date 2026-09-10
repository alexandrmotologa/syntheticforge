"""Unit tests for streaming sinks, traffic curves, and file exporters."""

from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from syntheticforge.config import EntityConfig, FieldConfig, FieldType
from syntheticforge.generator.lifecycle_simulator import DomainEvent
from syntheticforge.streaming.file_sink import JsonlSink, ParquetSink
from syntheticforge.streaming.kafka_streamer import KafkaStreamer
from syntheticforge.streaming.postgres_loader import PostgresLoader
from syntheticforge.streaming.traffic_curve import DiurnalTrafficCurve


def test_diurnal_traffic_curve() -> None:
    curve = DiurnalTrafficCurve(base_rate=1000.0, peak_hour=14.0, seed=42)

    # Peak hour (14:00) vs Trough (02:00)
    peak_time = datetime(2026, 9, 10, 14, 0, 0, tzinfo=UTC)
    trough_time = datetime(2026, 9, 10, 2, 0, 0, tzinfo=UTC)

    peak_rate = curve.get_rate(peak_time)
    trough_rate = curve.get_rate(trough_time)

    assert peak_rate > trough_rate
    assert peak_rate > 2000.0  # Approx 2.5x base rate


def test_jsonl_and_parquet_file_sinks(tmp_path: Path) -> None:
    records = [
        {"id": "u1", "name": "Alice", "score": 98.5},
        {"id": "u2", "name": "Bob", "score": 85.0},
    ]

    # 1. JsonlSink
    jsonl_sink = JsonlSink(tmp_path / "jsonl")
    f_jsonl = jsonl_sink.write_entity("users", records)
    assert f_jsonl.exists()
    content = f_jsonl.read_text().strip().split("\n")
    assert len(content) == 2

    # 2. ParquetSink
    parquet_sink = ParquetSink(tmp_path / "parquet")
    f_parquet = parquet_sink.write_entity("users", records)
    assert f_parquet.exists()

    # Read back parquet and verify content
    table = pq.read_table(f_parquet)
    assert table.num_rows == 2
    assert "name" in table.column_names


@pytest.mark.asyncio
async def test_kafka_streamer_mock_mode() -> None:
    streamer = KafkaStreamer(mock_mode=True)
    await streamer.start()

    ev = DomainEvent(
        event_id="e1",
        entity_name="orders",
        entity_id="ord_999",
        state="CREATED",
        previous_state=None,
        timestamp=datetime.now(UTC),
        payload={"order_id": "ord_999", "total": 45.0},
    )

    success = await streamer.send_event(ev)
    assert success is True
    assert streamer.sent_count == 1
    assert len(streamer.mock_sent_events) == 1
    assert streamer.mock_sent_events[0]["key"] == "ord_999"

    await streamer.stop()


@pytest.mark.asyncio
async def test_postgres_loader_ddl_and_mock_bulk() -> None:
    loader = PostgresLoader("postgresql://forge:pass@localhost:5432/db", mock_mode=True)
    await loader.connect()

    cfg = EntityConfig(
        count=10,
        primary_key="id",
        fields={
            "id": FieldConfig(type=FieldType.UUID),
            "amount": FieldConfig(type=FieldType.DECIMAL),
            "status": FieldConfig(type=FieldType.ENUM, values=["OK", "FAIL"]),
        },
    )

    ddl = loader.generate_ddl("orders", cfg)
    assert "CREATE TABLE IF NOT EXISTS orders" in ddl
    assert "id TEXT PRIMARY KEY" in ddl

    records = [{"id": f"ord_{i}", "amount": 10.0 * i, "status": "OK"} for i in range(5)]
    count = await loader.bulk_load("orders", records)
    assert count == 5
    assert loader.inserted_count == 5
    assert len(loader.mock_tables["orders"]) == 5

    await loader.close()
