"""Markov chain state machine engine for entity lifecycles."""

from __future__ import annotations

import random
from collections import defaultdict

from syntheticforge.config import DelayDistribution, LifecycleConfig, TransitionConfig


class StateMachine:
    """Evaluates probabilistic state transitions and temporal delays for an entity lifecycle."""

    def __init__(self, config: LifecycleConfig, seed: int | None = None) -> None:
        self.config = config
        self._rng = random.Random(seed)
        self._transitions_by_state: dict[str, list[TransitionConfig]] = defaultdict(list)
        self._terminal_states: set[str] = set(config.states)
        self._compile_transitions()

    def _compile_transitions(self) -> None:
        for t in self.config.transitions:
            self._transitions_by_state[t.from_state].append(t)
            if t.from_state in self._terminal_states:
                self._terminal_states.remove(t.from_state)

    @property
    def initial_state(self) -> str:
        return self.config.initial_state

    @property
    def terminal_states(self) -> set[str]:
        return set(self._terminal_states)

    def is_terminal(self, state: str) -> bool:
        """Check whether the given state has no outgoing transitions."""
        return state in self._terminal_states or len(self._transitions_by_state.get(state, [])) == 0

    def next_transition(self, current_state: str) -> tuple[str, float] | None:
        """Evaluate the next state and inter-arrival delay in seconds, or None if terminal."""
        transitions = self._transitions_by_state.get(current_state, [])
        if not transitions:
            return None

        # Sample next transition by probability
        weights = [t.probability for t in transitions]
        total = sum(weights)
        if total <= 0.0:
            return None

        # Handle remaining probability as stay/terminal if total < 1.0
        r = self._rng.random() * max(1.0, total)
        cumulative = 0.0
        chosen_transition: TransitionConfig | None = None
        for t in transitions:
            cumulative += t.probability
            if r <= cumulative:
                chosen_transition = t
                break

        if chosen_transition is None:
            return None

        delay = self._calculate_delay(chosen_transition)
        return chosen_transition.to_state, delay

    def _calculate_delay(self, transition: TransitionConfig) -> float:
        """Calculate temporal delay based on transition delay distribution."""
        dist = transition.delay_distribution
        base_delay = transition.delay_seconds

        if dist == DelayDistribution.CONSTANT:
            return max(0.0, base_delay)

        elif dist == DelayDistribution.UNIFORM:
            min_d = transition.delay_min if transition.delay_min is not None else 0.5 * base_delay
            max_d = transition.delay_max if transition.delay_max is not None else 1.5 * base_delay
            return max(0.0, self._rng.uniform(min_d, max_d))

        elif dist == DelayDistribution.EXPONENTIAL:
            # Poisson arrival: lambda = 1 / mean_delay
            rate = 1.0 / max(0.001, base_delay)
            return max(0.0, self._rng.expovariate(rate))

        elif dist == DelayDistribution.NORMAL:
            std = transition.delay_std if transition.delay_std is not None else 0.25 * base_delay
            return max(0.0, self._rng.gauss(base_delay, std))

        return max(0.0, base_delay)
