"""Simulation state checkpointing and restoration for resumable streams."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from syntheticforge.graph.pool import EntityIdPool
from syntheticforge.tui.stats import StreamStats


@dataclass
class SimulationCheckpoint:
    """Serializable snapshot of a running simulation."""

    saved_at: str
    virtual_seconds: float
    events_emitted: int
    entity_id_pool: dict[str, list[Any]] = field(default_factory=dict)
    entity_counts: dict[str, int] = field(default_factory=dict)
    state_counts: dict[str, int] = field(default_factory=dict)
    anomaly_counts: dict[str, int] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        virtual_seconds: float,
        pool: EntityIdPool,
        stats: StreamStats,
    ) -> SimulationCheckpoint:
        """Capture current simulation state into a checkpoint."""
        keys_copy = {ent: list(pool.get_keys(ent)) for ent in pool._keys}
        return cls(
            saved_at=datetime.now(UTC).isoformat(),
            virtual_seconds=virtual_seconds,
            events_emitted=stats.events_emitted,
            entity_id_pool=keys_copy,
            entity_counts=dict(stats.entity_counts),
            state_counts=dict(stats.state_counts),
            anomaly_counts=dict(stats.anomaly_counts),
        )

    def save(self, target_path: str | Path) -> Path:
        """Write checkpoint to a JSON file."""
        p = Path(target_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
        return p

    @classmethod
    def load(cls, source_path: str | Path) -> SimulationCheckpoint:
        """Load a checkpoint snapshot from a JSON file."""
        p = Path(source_path)
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    def restore_into(self, pool: EntityIdPool, stats: StreamStats) -> None:
        """Restore pool keys and stats counters from this checkpoint."""
        for ent, keys in self.entity_id_pool.items():
            pool.register_batch(ent, keys)

        stats.events_emitted = self.events_emitted
        stats.entity_counts.update(self.entity_counts)
        stats.state_counts.update(self.state_counts)
        stats.anomaly_counts.update(self.anomaly_counts)
