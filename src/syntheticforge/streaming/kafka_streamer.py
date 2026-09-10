"""High-velocity event streaming dispatcher using aiokafka."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from syntheticforge.generator.lifecycle_simulator import DomainEvent

logger = logging.getLogger(__name__)


class KafkaStreamer:
    """Streams DomainEvents to Apache Kafka topics with partition key affinity and batching."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic_prefix: str = "syntheticforge.",
        client_id: str = "syntheticforge-producer",
        linger_ms: int = 10,
        mock_mode: bool = False,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic_prefix = topic_prefix
        self.client_id = client_id
        self.linger_ms = linger_ms
        self.mock_mode = mock_mode

        self._producer: AIOKafkaProducer | None = None
        self.sent_count = 0
        self.error_count = 0
        self.mock_sent_events: list[dict[str, Any]] = []

    async def start(self) -> None:
        """Initialize and connect the Kafka producer."""
        if self.mock_mode:
            logger.info("KafkaStreamer started in MOCK mode.")
            return

        try:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                linger_ms=self.linger_ms,
                max_batch_size=65536,
                compression_type="gzip",
            )
            await self._producer.start()
            logger.info("AIOKafkaProducer successfully connected to %s", self.bootstrap_servers)
        except Exception as e:
            logger.warning("Kafka broker connection failed (%s); switching to mock mode.", e)
            self.mock_mode = True

    async def stop(self) -> None:
        """Gracefully flush and close the Kafka producer."""
        if self._producer:
            try:
                await self._producer.flush()
                await self._producer.stop()
            except Exception as e:
                logger.error("Error shutting down Kafka producer: %s", e)
            finally:
                self._producer = None

    async def send_event(self, event: DomainEvent, topic_override: str | None = None) -> bool:
        """Publish a single domain event with entity_id as the partition key."""
        topic = topic_override or f"{self.topic_prefix}{event.entity_name}"
        key_bytes = event.entity_id.encode("utf-8")
        payload_bytes = event.to_json().encode("utf-8")

        if self.mock_mode or not self._producer:
            self.mock_sent_events.append(
                {
                    "topic": topic,
                    "key": event.entity_id,
                    "event": event.to_dict(),
                }
            )
            self.sent_count += 1
            return True

        headers = []
        if event.trace_context:
            headers = [
                ("traceparent", event.trace_context.traceparent.encode("utf-8")),
                ("tracestate", f"span={event.trace_context.span_id}".encode()),
            ]

        try:
            await self._producer.send(topic, key=key_bytes, value=payload_bytes, headers=headers)
            self.sent_count += 1
            return True
        except KafkaError as err:
            logger.error("Failed to stream event %s: %s", event.event_id, err)
            self.error_count += 1
            return False

    async def send_batch(self, events: list[DomainEvent], topic_override: str | None = None) -> int:
        """Send a batch of events asynchronously."""
        tasks = [self.send_event(ev, topic_override=topic_override) for ev in events]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for r in results if r is True)
