"""Discrete-event lifecycle simulation with virtual clock and temporal delays."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import heapq
import json
import time
from typing import Any, AsyncIterator, Iterator
import uuid

from syntheticforge.config import ForgeConfig
from syntheticforge.generator.entity_generator import EntityGenerator
from syntheticforge.generator.state_machine import StateMachine


@dataclass(order=True)
class ScheduledEvent:
    """Internal item for priority queue ordered by virtual event timestamp."""

    virtual_timestamp: float
    sequence_id: int
    event: DomainEvent = field(compare=False)


@dataclass
class DomainEvent:
    """Represents a domain lifecycle event emitted by an entity."""

    event_id: str
    entity_name: str
    entity_id: str
    state: str
    previous_state: str | None
    timestamp: datetime
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "entity_name": self.entity_name,
            "entity_id": self.entity_id,
            "state": self.state,
            "previous_state": self.previous_state,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class LifecycleSimulator:
    """Simulates entity lifecycle transitions across temporal timelines using a virtual clock."""

    def __init__(
        self,
        config: ForgeConfig,
        generator: EntityGenerator | None = None,
        speed_factor: float = 1.0,
        start_time: datetime | None = None,
        seed: int | None = None,
    ) -> None:
        self.config = config
        self.generator = generator or EntityGenerator(config, seed=seed)
        self.speed_factor = max(0.001, speed_factor)
        self.start_time = start_time or datetime.now(timezone.utc)
        self._seed = seed

        # Initialize state machines for configured entities
        self._state_machines: dict[str, StateMachine] = {}
        for ent_name, ent_cfg in self.config.entities.items():
            if ent_cfg.lifecycle:
                self._state_machines[ent_name] = StateMachine(ent_cfg.lifecycle, seed=seed)

    def generate_all_events(self) -> list[DomainEvent]:
        """Eagerly simulate and return all domain events sorted by timestamp."""
        return list(self.iter_events())

    def iter_events(self) -> Iterator[DomainEvent]:
        """Generate and yield discrete events in chronological simulated order."""
        event_queue: list[ScheduledEvent] = []
        seq = 0

        # Generate base relational entities
        dataset = self.generator.generate_all(base_timestamp=self.start_time)

        # Schedule initial state for entities with lifecycle
        for ent_name, records in dataset.items():
            sm = self._state_machines.get(ent_name)
            pk_col = self.config.entities[ent_name].primary_key

            for record in records:
                pk_val = str(record[pk_col])
                if sm:
                    initial_state = sm.initial_state
                    init_event = DomainEvent(
                        event_id=str(uuid.uuid4()),
                        entity_name=ent_name,
                        entity_id=pk_val,
                        state=initial_state,
                        previous_state=None,
                        timestamp=self.start_time,
                        payload=dict(record),
                    )
                    heapq.heappush(
                        event_queue,
                        ScheduledEvent(virtual_timestamp=0.0, sequence_id=seq, event=init_event),
                    )
                    seq += 1
                else:
                    # Entity without lifecycle emits a single creation event
                    creation_event = DomainEvent(
                        event_id=str(uuid.uuid4()),
                        entity_name=ent_name,
                        entity_id=pk_val,
                        state="SNAPSHOT",
                        previous_state=None,
                        timestamp=self.start_time,
                        payload=dict(record),
                    )
                    heapq.heappush(
                        event_queue,
                        ScheduledEvent(
                            virtual_timestamp=0.0, sequence_id=seq, event=creation_event
                        ),
                    )
                    seq += 1

        # Process discrete event queue
        while event_queue:
            scheduled = heapq.heappop(event_queue)
            curr_event = scheduled.event
            yield curr_event

            ent_name = curr_event.entity_name
            sm = self._state_machines.get(ent_name)
            if not sm:
                continue

            curr_state = curr_event.state
            if not sm.is_terminal(curr_state):
                next_step = sm.next_transition(curr_state)
                if next_step is not None:
                    next_state, delay_secs = next_step
                    next_virtual_ts = scheduled.virtual_timestamp + delay_secs
                    event_dt = self.start_time + timedelta(seconds=next_virtual_ts)

                    updated_payload = dict(curr_event.payload)
                    updated_payload["status"] = next_state

                    next_event = DomainEvent(
                        event_id=str(uuid.uuid4()),
                        entity_name=ent_name,
                        entity_id=curr_event.entity_id,
                        state=next_state,
                        previous_state=curr_state,
                        timestamp=event_dt,
                        payload=updated_payload,
                    )
                    heapq.heappush(
                        event_queue,
                        ScheduledEvent(
                            virtual_timestamp=next_virtual_ts,
                            sequence_id=seq,
                            event=next_event,
                        ),
                    )
                    seq += 1

    async def stream_events(self) -> AsyncIterator[DomainEvent]:
        """Asynchronously stream events paced by the virtual clock and speed factor."""
        last_virtual_ts = 0.0
        for event in self.iter_events():
            event_secs = (event.timestamp - self.start_time).total_seconds()
            virtual_delta = max(0.0, event_secs - last_virtual_ts)
            if virtual_delta > 0:
                wall_sleep = virtual_delta / self.speed_factor
                # Cap sleep intervals to keep streaming responsive
                if wall_sleep > 0.001:
                    await asyncio.sleep(min(wall_sleep, 5.0))
            last_virtual_ts = event_secs
            yield event
