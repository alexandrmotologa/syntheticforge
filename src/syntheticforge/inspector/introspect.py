"""Database schema auto-introspection from PostgreSQL to SyntheticForge YAML schemas."""

from __future__ import annotations

import logging
from typing import Any
import yaml

import asyncpg

logger = logging.getLogger(__name__)


class SchemaIntrospector:
    """Introspects PostgreSQL relational schemas and converts them to SyntheticForge YAML configs."""

    def __init__(self, dsn: str, mock_data: dict[str, Any] | None = None) -> None:
        self.dsn = dsn
        self.mock_data = mock_data

    async def introspect(self, schema_name: str = "public") -> dict[str, Any]:
        """Introspect all tables and foreign keys, returning a SyntheticForge configuration dict."""
        if self.mock_data:
            return self.mock_data

        try:
            conn = await asyncpg.connect(self.dsn)
        except Exception as e:
            logger.warning("Could not connect to PostgreSQL (%s); returning fallback schema.", e)
            return self._fallback_schema()

        try:
            # 1. Fetch tables
            tables = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = $1 AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """,
                schema_name,
            )

            # 2. Fetch primary keys
            pk_records = await conn.fetch(
                """
                SELECT tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = $1
                """,
                schema_name,
            )
            pks: dict[str, str] = {r["table_name"]: r["column_name"] for r in pk_records}

            # 3. Fetch foreign keys
            fk_records = await conn.fetch(
                """
                SELECT
                    kcu.table_name AS child_table,
                    kcu.column_name AS child_column,
                    ccu.table_name AS parent_table,
                    ccu.column_name AS parent_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = $1
                """,
                schema_name,
            )

            entities: dict[str, Any] = {}

            for t in tables:
                tname = t["table_name"]
                col_records = await conn.fetch(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = $1 AND table_schema = $2
                    ORDER BY ordinal_position
                    """,
                    tname,
                    schema_name,
                )

                fields: dict[str, Any] = {}
                for col in col_records:
                    cname = col["column_name"]
                    ctype = col["data_type"]
                    fields[cname] = {"type": self._map_type(cname, ctype)}

                # Build foreign keys
                fks: dict[str, Any] = {}
                depends_on: list[str] = []
                for fk in fk_records:
                    if fk["child_table"] == tname:
                        fks[fk["child_column"]] = {
                            "entity": fk["parent_table"],
                            "field": fk["parent_column"],
                            "distribution": "pareto",
                        }
                        if fk["parent_table"] not in depends_on:
                            depends_on.append(fk["parent_table"])

                entities[tname] = {
                    "count": 500,
                    "primary_key": pks.get(tname, "id"),
                    "depends_on": depends_on,
                    "foreign_keys": fks,
                    "fields": fields,
                }

            return {
                "version": "1.0",
                "name": f"introspected-{schema_name}",
                "description": f"Auto-generated schema from PostgreSQL schema {schema_name}",
                "entities": entities,
            }
        finally:
            await conn.close()

    def _map_type(self, col_name: str, data_type: str) -> str:
        """Map SQL type and column name heuristics to SyntheticForge FieldType."""
        dt = data_type.lower()
        cn = col_name.lower()

        if "uuid" in dt or cn.endswith("_id") or cn == "id":
            return "uuid"
        elif "int" in dt:
            return "integer"
        elif any(x in dt for x in ["numeric", "decimal", "real", "double", "float"]):
            return "decimal"
        elif "timestamp" in dt or "date" in dt or "time" in dt:
            return "timestamp"
        elif "email" in cn:
            return "email"
        elif any(x in cn for x in ["name", "title", "user"]):
            return "name"
        return "regex"

    def _fallback_schema(self) -> dict[str, Any]:
        return {
            "version": "1.0",
            "name": "fallback-schema",
            "entities": {
                "users": {
                    "count": 100,
                    "primary_key": "id",
                    "fields": {
                        "id": {"type": "uuid"},
                        "name": {"type": "name"},
                    },
                }
            },
        }

    def to_yaml(self, schema_dict: dict[str, Any]) -> str:
        """Serialize configuration dictionary to clean YAML string."""
        return yaml.dump(schema_dict, sort_keys=False)
