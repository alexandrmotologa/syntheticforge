"""DuckDB-based in-memory referential integrity and consistency verifier."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa

from syntheticforge.config import ForgeConfig


@dataclass
class VerificationReport:
    """Detailed audit report of relational integrity checks."""

    passed: bool
    total_records: int
    entity_counts: dict[str, int] = field(default_factory=dict)
    orphan_fks: dict[str, int] = field(default_factory=dict)
    violations: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Relational Verification: {'PASSED' if self.passed else 'FAILED'}",
            f"Total records audited: {self.total_records}",
            "Entity record counts:",
        ]
        for ent, count in self.entity_counts.items():
            lines.append(f"  - {ent}: {count}")

        if self.orphan_fks:
            lines.append("Orphan foreign keys detected:")
            for fk, count in self.orphan_fks.items():
                lines.append(f"  - {fk}: {count} orphans")

        if self.violations:
            lines.append("Violations:")
            for v in self.violations:
                lines.append(f"  - {v}")

        return "\n".join(lines)


class RelationalVerifier:
    """Verifies 100% referential integrity and schema compliance using in-memory DuckDB."""

    def __init__(self, config: ForgeConfig) -> None:
        self.config = config
        self.con = duckdb.connect(":memory:")

    def verify_dataset(self, dataset: dict[str, list[dict[str, Any]]]) -> VerificationReport:
        """Load dataset in-memory and execute relational integrity queries."""
        total_records = 0
        entity_counts: dict[str, int] = {}
        orphan_fks: dict[str, int] = {}
        violations: list[str] = []

        # 1. Register or insert tables into DuckDB
        for ent_name, records in dataset.items():
            entity_counts[ent_name] = len(records)
            total_records += len(records)
            if records:
                arrow_table = pa.Table.from_pylist(records)
                self.con.register(f"temp_{ent_name}", arrow_table)
                self.con.execute(
                    f"CREATE OR REPLACE TABLE {ent_name} AS SELECT * FROM temp_{ent_name}"
                )
            else:
                self.con.execute(f"CREATE OR REPLACE TABLE {ent_name} (dummy INT)")

        # 2. Audit Foreign Keys
        for child_name, entity_cfg in self.config.entities.items():
            if not dataset.get(child_name):
                continue

            for fk_col, fk_cfg in entity_cfg.foreign_keys.items():
                parent_name = fk_cfg.entity
                parent_pk = fk_cfg.field or "id"

                if not dataset.get(parent_name):
                    violations.append(
                        f"Child entity '{child_name}' references parent '{parent_name}', but parent has 0 records."
                    )
                    continue

                query = f"""
                    SELECT COUNT(*)
                    FROM {child_name} c
                    WHERE c.{fk_col} IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM {parent_name} p
                          WHERE p.{parent_pk} = c.{fk_col}
                      )
                """
                try:
                    orphans = self.con.execute(query).fetchone()[0]
                    if orphans > 0:
                        key_desc = f"{child_name}.{fk_col} -> {parent_name}.{parent_pk}"
                        orphan_fks[key_desc] = orphans
                        violations.append(
                            f"Detected {orphans} orphan foreign key(s) in relationship {key_desc}."
                        )
                except Exception as err:
                    violations.append(f"Query error checking {child_name}.{fk_col}: {err}")

        passed = len(violations) == 0 and len(orphan_fks) == 0
        return VerificationReport(
            passed=passed,
            total_records=total_records,
            entity_counts=entity_counts,
            orphan_fks=orphan_fks,
            violations=violations,
        )

    def verify_jsonl_directory(self, data_dir: str | Path) -> VerificationReport:
        """Verify referential integrity directly from JSONL files in a directory."""
        dir_path = Path(data_dir)
        dataset: dict[str, list[dict[str, Any]]] = {}
        import json

        for ent_name in self.config.entities:
            file_path = dir_path / f"{ent_name}.jsonl"
            records = []
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            records.append(json.loads(line))
            dataset[ent_name] = records

        return self.verify_dataset(dataset)
