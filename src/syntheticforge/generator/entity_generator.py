"""Relational entity generation coordinating schema dependencies and foreign keys."""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from syntheticforge.config import EntityConfig, FieldConfig, FieldType, ForgeConfig
from syntheticforge.generator.field_generators import FieldGenerator
from syntheticforge.graph.pool import EntityIdPool
from syntheticforge.graph.schema_graph import SchemaGraph


class EntityGenerator:
    """Generates coherent relational entity datasets with strict referential integrity."""

    def __init__(
        self,
        config: ForgeConfig,
        graph: SchemaGraph | None = None,
        pool: EntityIdPool | None = None,
        seed: int | None = None,
    ) -> None:
        self.config = config
        self.graph = graph or SchemaGraph(config)
        self.pool = pool or EntityIdPool(seed=seed)
        self.field_gen = FieldGenerator(seed=seed)

    def generate_all(
        self, base_timestamp: datetime | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        """Generate all entities following the topological stage order."""
        dataset: dict[str, list[dict[str, Any]]] = {}

        # Iterate through generation stages (topological generations)
        stages = self.graph.generation_stages()
        for stage in stages:
            for entity_name in stage:
                entity_cfg = self.config.entities[entity_name]
                records = self.generate_entity_batch(
                    entity_name,
                    entity_cfg,
                    count=entity_cfg.count,
                    base_timestamp=base_timestamp,
                )
                dataset[entity_name] = records

        return dataset

    def generate_entity_batch(
        self,
        entity_name: str,
        entity_cfg: EntityConfig,
        count: int,
        base_timestamp: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Generate a batch of records for a specific entity, resolving foreign keys from pool."""
        records: list[dict[str, Any]] = []
        pk_name = entity_cfg.primary_key

        for _ in range(count):
            record: dict[str, Any] = {}

            # 1. Generate or reserve primary key
            if pk_name in entity_cfg.fields:
                pk_val = self.field_gen.generate(
                    pk_name, entity_cfg.fields[pk_name], record, base_timestamp
                )
            else:
                pk_val = str(uuid.uuid4())
            record[pk_name] = pk_val

            # 2. Resolve foreign keys from parent entities in pool
            for fk_col, fk_cfg in entity_cfg.foreign_keys.items():
                parent_id = self.pool.sample_key(
                    fk_cfg.entity,
                    distribution=fk_cfg.distribution,
                    pareto_alpha=fk_cfg.pareto_alpha,
                    zipf_alpha=fk_cfg.zipf_alpha,
                )
                record[fk_col] = parent_id

            # 3. Generate remaining fields
            for field_name, field_cfg in entity_cfg.fields.items():
                if field_name == pk_name or field_name in entity_cfg.foreign_keys:
                    continue
                record[field_name] = self.field_gen.generate(
                    field_name, field_cfg, record, base_timestamp
                )

            # 4. Register generated record in pool
            self.pool.register(entity_name, pk_val, record)
            records.append(record)

        return records
