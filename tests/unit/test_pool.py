"""Unit tests for EntityIdPool and foreign key sampling distributions."""

from collections import Counter
import pytest
from syntheticforge.config import SamplingDistribution
from syntheticforge.graph.pool import EntityIdPool


def test_pool_registration_and_uniform_sampling() -> None:
    pool = EntityIdPool(seed=42)
    keys = [f"user_{i}" for i in range(10)]
    pool.register_batch("users", keys)

    assert pool.count("users") == 10
    assert pool.get_keys("users") == keys

    sampled = [pool.sample_key("users", SamplingDistribution.UNIFORM) for _ in range(100)]
    # All sampled keys must be in the original pool
    assert all(k in keys for k in sampled)
    # Check that sampling explores multiple keys
    assert len(set(sampled)) > 5


def test_pool_empty_entity_raises_key_error() -> None:
    pool = EntityIdPool()
    with pytest.raises(KeyError):
        pool.sample_key("nonexistent")


def test_pareto_distribution_skews_to_head() -> None:
    pool = EntityIdPool(seed=42)
    keys = [f"user_{i}" for i in range(100)]
    pool.register_batch("users", keys)

    samples = [
        pool.sample_key("users", SamplingDistribution.PARETO, pareto_alpha=1.16)
        for _ in range(1000)
    ]
    counts = Counter(samples)

    # Top 20 keys should account for significantly more frequency than bottom 20
    top_20_keys = set(keys[:20])
    top_20_total = sum(counts[k] for k in top_20_keys)
    assert top_20_total > 400  # Should be heavily concentrated in top keys


def test_gaussian_distribution_clustering() -> None:
    pool = EntityIdPool(seed=42)
    keys = [f"item_{i}" for i in range(50)]
    pool.register_batch("items", keys)

    samples = [pool.sample_key("items", SamplingDistribution.GAUSSIAN) for _ in range(500)]
    counts = Counter(samples)

    # Median element (item_25) should have higher frequency than extreme edge (item_0, item_49)
    middle_count = counts.get("item_24", 0) + counts.get("item_25", 0)
    edges_count = counts.get("item_0", 0) + counts.get("item_49", 0)
    assert middle_count > edges_count
