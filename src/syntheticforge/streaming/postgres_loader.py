"""High-velocity PostgreSQL bulk loader using asyncpg binary COPY protocol."""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

from syntheticforge.config import EntityConfig, FieldType

logger = logging.getLogger(__name__)


class PostgresLoader:
    """Loads relational entities into PostgreSQL tables using asyncpg COPY protocol."""

    def __init__(self, dsn: str, mock_mode: bool = False) -> None:
        self.dsn = dsn
        self.mock_mode = mock_mode
        self._pool: asyncpg.Pool | None = None
        self.inserted_count = 0
        self.mock_tables: dict[str, list[dict[str, Any]]] = {}

    async def connect(self) -> None:
        """Establish connection pool to PostgreSQL."""
        if self.mock_mode:
            logger.info("PostgresLoader initialized in MOCK mode.")
            return

        try:
            self._pool = await asyncpg.create_pool(dsn=self.dsn, min_size=2, max_size=10)
            logger.info("PostgresLoader connected to PostgreSQL pool.")
        except Exception as e:
            logger.warning("PostgreSQL connection failed (%s); switching to mock mode.", e)
            self.mock_mode = True

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    def generate_ddl(self, entity_name: str, config: EntityConfig) -> str:
        """Generate CREATE TABLE IF NOT EXISTS statement matching entity schema."""
        cols = []
        pk = config.primary_key

        for fname, fcfg in config.fields.items():
            pg_type = self._map_pg_type(fcfg.type)
            pk_suffix = " PRIMARY KEY" if fname == pk else ""
            cols.append(f"    {fname} {pg_type}{pk_suffix}")

        # Add foreign key columns if not in fields
        for fk_name in config.foreign_keys:
            if fk_name not in config.fields:
                cols.append(f"    {fk_name} TEXT")

        ddl = f"CREATE TABLE IF NOT EXISTS {entity_name} (\n" + ",\n".join(cols) + "\n);"
        return ddl

    def _map_pg_type(self, field_type: FieldType) -> str:
        if field_type == FieldType.UUID:
            return "TEXT"
        elif field_type in (FieldType.INTEGER, FieldType.SEQUENCE):
            return "BIGINT"
        elif field_type == FieldType.DECIMAL:
            return "NUMERIC(14, 4)"
        elif field_type == FieldType.TIMESTAMP:
            return "TEXT"
        return "TEXT"

    async def create_table(self, entity_name: str, config: EntityConfig) -> None:
        """Execute DDL to create table if not exists."""
        ddl = self.generate_ddl(entity_name, config)
        if self.mock_mode or not self._pool:
            self.mock_tables.setdefault(entity_name, [])
            return

        async with self._pool.acquire() as conn:
            await conn.execute(ddl)

    async def bulk_load(
        self, entity_name: str, records: list[dict[str, Any]]
    ) -> int:
        """Bulk insert records using PostgreSQL COPY protocol."""
        if not records:
            return 0

        if self.mock_mode or not self._pool:
            self.mock_tables.setdefault(entity_name, []).extend(records)
            self.inserted_count += len(records)
            return len(records)

        columns = list(records[0].keys())
        tuples = [tuple(r.get(col) for col in columns) for r in records]

        async with self._pool.acquire() as conn:
            # asyncpg binary copy_records_to_table
            await conn.copy_records_to_table(
                entity_name,
                records=tuples,
                columns=columns,
            )

        self.inserted_count += len(records)
        return len(records)
