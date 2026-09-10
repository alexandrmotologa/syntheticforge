"""Unit tests for simulation checkpointing and state restoration."""

from pathlib import Path

from syntheticforge.checkpoint import SimulationCheckpoint
from syntheticforge.graph.pool import EntityIdPool
from syntheticforge.tui.stats import StreamStats


def test_checkpoint_save_and_restore(tmp_path: Path) -> None:
    pool = EntityIdPool()
    pool.register_batch("users", ["u1", "u2", "u3"])
    pool.register_batch("orders", ["o1", "o2"])

    stats = StreamStats()
    stats.record_event("users", "SNAPSHOT")
    stats.record_event("orders", "CREATED")
    stats.record_event("orders", "COMPLETED", anomaly_type="duplicate_key")

    ckpt = SimulationCheckpoint.create(virtual_seconds=125.5, pool=pool, stats=stats)

    file_path = tmp_path / "stream_state.ckpt"
    ckpt.save(file_path)
    assert file_path.exists()

    # Load into fresh pool and stats
    loaded_ckpt = SimulationCheckpoint.load(file_path)
    assert loaded_ckpt.virtual_seconds == 125.5
    assert loaded_ckpt.events_emitted == 3
    assert loaded_ckpt.entity_id_pool["users"] == ["u1", "u2", "u3"]

    fresh_pool = EntityIdPool()
    fresh_stats = StreamStats()
    loaded_ckpt.restore_into(fresh_pool, fresh_stats)

    assert fresh_pool.get_keys("users") == ["u1", "u2", "u3"]
    assert fresh_stats.events_emitted == 3
    assert fresh_stats.anomaly_counts["duplicate_key"] == 1
