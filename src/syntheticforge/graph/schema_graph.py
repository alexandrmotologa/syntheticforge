"""Topological dependency graph engine for SyntheticForge entities."""

from __future__ import annotations

from typing import Any
import networkx as nx

from syntheticforge.config import EntityConfig, ForgeConfig


class CircularDependencyError(Exception):
    """Raised when the entity dependency graph contains a cycle."""

    def __init__(self, cycles: list[list[str]]) -> None:
        formatted = " -> ".join(cycles[0] + [cycles[0][0]]) if cycles else "unknown"
        super().__init__(
            f"Circular dependency detected in schema graph: {formatted}. "
            "Entities cannot have mutually dependent foreign keys."
        )
        self.cycles = cycles


class SchemaGraph:
    """Directed Acyclic Graph (DAG) representing entity dependencies."""

    def __init__(self, config: ForgeConfig) -> None:
        self.config = config
        self.dag: nx.DiGraph = nx.DiGraph()
        self._build_graph()

    def _build_graph(self) -> None:
        for name, entity_cfg in self.config.entities.items():
            self.dag.add_node(name, config=entity_cfg)

        for child_name, entity_cfg in self.config.entities.items():
            for parent_name in entity_cfg.depends_on:
                if parent_name not in self.dag:
                    raise ValueError(
                        f"Entity '{child_name}' depends on unregistered entity '{parent_name}'."
                    )
                # Directed edge: parent -> child (parent must be evaluated before child)
                self.dag.add_edge(parent_name, child_name)

        if not nx.is_directed_acyclic_graph(self.dag):
            cycles = list(nx.simple_cycles(self.dag))
            raise CircularDependencyError(cycles)

    def topological_order(self) -> list[str]:
        """Return the linear entity generation sequence."""
        return list(nx.topological_sort(self.dag))

    def generation_stages(self) -> list[list[str]]:
        """Return entities grouped into parallelizable topological generations (stages)."""
        return [sorted(list(stage)) for stage in nx.topological_generations(self.dag)]

    def get_parents(self, entity: str) -> list[str]:
        """Return immediate parent entities that this entity depends on."""
        return list(self.dag.predecessors(entity))

    def get_children(self, entity: str) -> list[str]:
        """Return immediate child entities that depend on this entity."""
        return list(self.dag.successors(entity))

    def get_entity_config(self, entity: str) -> EntityConfig:
        """Return the EntityConfig for a given entity name."""
        return self.dag.nodes[entity]["config"]

    def to_ascii_tree(self) -> str:
        """Generate a human-readable ASCII representation of the entity DAG."""
        lines = ["Entity Dependency Hierarchy:"]
        stages = self.generation_stages()
        for idx, stage in enumerate(stages):
            lines.append(f"  Stage {idx}:")
            for ent in stage:
                parents = self.get_parents(ent)
                parent_str = f" (depends on: {', '.join(parents)})" if parents else " (root entity)"
                count = self.get_entity_config(ent).count
                lines.append(f"    - {ent} [count: {count}]{parent_str}")
        return "\n".join(lines)
