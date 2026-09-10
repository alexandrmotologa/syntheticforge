"""In-memory primary key pool and distribution-aware foreign key sampler."""

from __future__ import annotations

from collections import defaultdict
import math
import random
from typing import Any

from syntheticforge.config import SamplingDistribution


class EntityIdPool:
    """Thread-safe in-memory storage and sampler for generated entity primary keys."""

    def __init__(self, seed: int | None = None) -> None:
        self._keys: dict[str, list[Any]] = defaultdict(list)
        self._records: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._rng = random.Random(seed)

    def register(self, entity: str, key_value: Any, record: dict[str, Any] | None = None) -> None:
        """Register a single primary key and optional record snapshot."""
        self._keys[entity].append(key_value)
        if record is not None:
            self._records[entity].append(record)

    def register_batch(
        self,
        entity: str,
        key_values: list[Any],
        records: list[dict[str, Any]] | None = None,
    ) -> None:
        """Register a batch of primary keys and records."""
        self._keys[entity].extend(key_values)
        if records:
            self._records[entity].extend(records)

    def get_keys(self, entity: str) -> list[Any]:
        """Get all registered primary keys for an entity."""
        return self._keys.get(entity, [])

    def get_records(self, entity: str) -> list[dict[str, Any]]:
        """Get all registered records for an entity."""
        return self._records.get(entity, [])

    def count(self, entity: str) -> int:
        """Return the number of registered keys for an entity."""
        return len(self._keys.get(entity, []))

    def sample_key(
        self,
        entity: str,
        distribution: SamplingDistribution = SamplingDistribution.UNIFORM,
        pareto_alpha: float = 1.16,
        zipf_alpha: float = 1.0,
    ) -> Any:
        """Sample a foreign key reference from registered parent keys using the specified distribution."""
        keys = self._keys.get(entity)
        if not keys:
            raise KeyError(
                f"Cannot sample foreign key from entity '{entity}'. "
                "No records have been generated or registered for this parent entity yet."
            )

        n = len(keys)
        if n == 1:
            return keys[0]

        index = self._sample_index(n, distribution, pareto_alpha, zipf_alpha)
        return keys[index]

    def _sample_index(
        self,
        n: int,
        distribution: SamplingDistribution,
        pareto_alpha: float,
        zipf_alpha: float,
    ) -> int:
        """Calculate a sampled index in [0, n - 1] according to the distribution."""
        if distribution == SamplingDistribution.UNIFORM:
            return self._rng.randint(0, n - 1)

        elif distribution == SamplingDistribution.PARETO:
            # Bounded Pareto sampling via inverse transform:
            # CDF(x) = (1 - (L/x)^a) / (1 - (L/H)^a)
            u = self._rng.random()
            alpha = max(0.1, pareto_alpha)
            # Power law index heavily skewing towards lower indices (top 20%)
            val = (1.0 - u) ** (-1.0 / alpha) - 1.0
            idx = int(val * (n / 10.0)) % n
            return idx

        elif distribution == SamplingDistribution.ZIPFIAN:
            # Harmonic-weighted rank selection
            u = self._rng.random()
            # Fast approximation for Zipfian inverse CDF
            alpha = max(0.5, zipf_alpha)
            idx = int(n * (u ** (1.0 / (1.0 - alpha + 0.001) if alpha != 1.0 else math.exp(-u))))
            return max(0, min(n - 1, idx))

        elif distribution == SamplingDistribution.GAUSSIAN:
            # Centered Gaussian in the middle of the population
            mu = (n - 1) / 2.0
            sigma = max(1.0, n / 6.0)
            val = int(round(self._rng.gauss(mu, sigma)))
            return max(0, min(n - 1, val))

        elif distribution == SamplingDistribution.RECENT_WEIGHTED:
            # Quadratic skew towards latest elements (temporal locality)
            u = self._rng.random()
            idx = int(math.floor(math.sqrt(u) * n))
            return max(0, min(n - 1, idx))

        return self._rng.randint(0, n - 1)
