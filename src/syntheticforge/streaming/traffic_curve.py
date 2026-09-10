"""Diurnal traffic curve modeling diurnal peaks, troughs, and burst spikes."""

from __future__ import annotations

from datetime import datetime
import math
import random


class DiurnalTrafficCurve:
    """Calculates instantaneous target event rates (events/second) based on time of day."""

    def __init__(
        self,
        base_rate: float = 1000.0,
        peak_factor: float = 2.5,
        trough_factor: float = 0.2,
        peak_hour: float = 14.0,  # 2:00 PM local peak
        burst_probability: float = 0.01,
        burst_multiplier: float = 3.0,
        seed: int | None = None,
    ) -> None:
        self.base_rate = base_rate
        self.peak_factor = peak_factor
        self.trough_factor = trough_factor
        self.peak_hour = peak_hour
        self.burst_probability = burst_probability
        self.burst_multiplier = burst_multiplier
        self._rng = random.Random(seed)

    def get_rate(self, current_time: datetime | None = None) -> float:
        """Return the target event rate (EPS) for the given datetime."""
        dt = current_time or datetime.now()
        hour_fraction = dt.hour + dt.minute / 60.0 + dt.second / 3600.0

        # Sinusoidal diurnal wave with peak at peak_hour
        # Period = 24 hours
        phase = (hour_fraction - self.peak_hour) * (2 * math.pi / 24.0)
        # cos(0) = 1 (at peak_hour), cos(pi) = -1 (12 hours away)
        normalized_wave = (math.cos(phase) + 1.0) / 2.0  # Range [0, 1]

        amplitude_multiplier = (
            self.trough_factor + (self.peak_factor - self.trough_factor) * normalized_wave
        )
        rate = self.base_rate * amplitude_multiplier

        # Add stochastic micro-jitter (+/- 5%)
        jitter = self._rng.uniform(0.95, 1.05)
        rate *= jitter

        # Check for spontaneous burst traffic spikes
        if self._rng.random() < self.burst_probability:
            rate *= self.burst_multiplier

        return max(1.0, rate)
