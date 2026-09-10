"""Buffered file sinks for JSON Lines and Apache Parquet formats."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


class JsonlSink:
    """Writes entity records to line-delimited JSON files."""

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_entity(self, entity_name: str, records: list[dict[str, Any]]) -> Path:
        """Write records for an entity to <output_dir>/<entity_name>.jsonl."""
        file_path = self.output_dir / f"{entity_name}.jsonl"
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(record, default=str) + "\n" for record in records)
        return file_path

    def write_all(self, dataset: dict[str, list[dict[str, Any]]]) -> dict[str, Path]:
        """Write all entities in the dataset."""
        result: dict[str, Path] = {}
        for ent_name, records in dataset.items():
            result[ent_name] = self.write_entity(ent_name, records)
        return result


class ParquetSink:
    """Writes entity records to Apache Parquet files using PyArrow."""

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_entity(self, entity_name: str, records: list[dict[str, Any]]) -> Path:
        """Convert records to a PyArrow Table and write to <output_dir>/<entity_name>.parquet."""
        if not records:
            raise ValueError(f"Cannot write empty dataset for entity '{entity_name}'.")

        file_path = self.output_dir / f"{entity_name}.parquet"
        # Convert records to Arrow Table
        table = pa.Table.from_pylist(records)
        pq.write_table(table, file_path, compression="snappy")
        return file_path

    def write_all(self, dataset: dict[str, list[dict[str, Any]]]) -> dict[str, Path]:
        """Write all entities in the dataset to Parquet files."""
        result: dict[str, Path] = {}
        for ent_name, records in dataset.items():
            result[ent_name] = self.write_entity(ent_name, records)
        return result
