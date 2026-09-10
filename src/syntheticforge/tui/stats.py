"""Live stream statistics collector for terminal metrics and dashboards."""

from __future__ import annotations

import time
from collections import defaultdict


class StreamStats:
    """Collects real-time generation throughput, state transitions, and anomaly metrics."""

    def __init__(self) -> None:
        self.start_time: float = time.time()
        self.events_emitted: int = 0
        self.entity_counts: dict[str, int] = defaultdict(int)
        self.state_counts: dict[str, int] = defaultdict(int)
        self.anomaly_counts: dict[str, int] = defaultdict(int)

        # Rolling window for EPS calculation
        self._window_start: float = time.time()
        self._window_events: int = 0
        self.current_eps: float = 0.0

    def record_event(
        self,
        entity_name: str,
        state: str,
        anomaly_type: str | None = None,
    ) -> None:
        """Record an emitted domain event."""
        self.events_emitted += 1
        self.entity_counts[entity_name] += 1
        self.state_counts[state] += 1
        self._window_events += 1

        if anomaly_type:
            self.anomaly_counts[anomaly_type] += 1

        now = time.time()
        elapsed = now - self._window_start
        if elapsed >= 0.5:
            self.current_eps = self._window_events / elapsed
            self._window_start = now
            self._window_events = 0

    @property
    def total_elapsed_seconds(self) -> float:
        return max(0.001, time.time() - self.start_time)

    @property
    def average_eps(self) -> float:
        return self.events_emitted / self.total_elapsed_seconds
