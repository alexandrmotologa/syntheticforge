"""Asynchronous HTTP Webhook and REST dispatcher with HMAC SHA-256 signing."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

from syntheticforge.generator.lifecycle_simulator import DomainEvent

logger = logging.getLogger(__name__)


class WebhookStreamer:
    """Streams DomainEvents as HTTP POST requests to a webhook endpoint with HMAC signing."""

    def __init__(
        self,
        endpoint_url: str,
        secret_key: str | None = None,
        concurrency: int = 50,
        timeout: float = 5.0,
        max_retries: int = 3,
        mock_mode: bool = False,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.secret_key = secret_key
        self.concurrency = concurrency
        self.timeout = timeout
        self.max_retries = max_retries
        self.mock_mode = mock_mode

        self._semaphore = asyncio.Semaphore(concurrency)
        self._client: httpx.AsyncClient | None = None
        self.sent_count = 0
        self.error_count = 0
        self.mock_requests: list[dict[str, Any]] = []

    async def start(self) -> None:
        """Initialize the HTTP client pool."""
        if not self.mock_mode:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=self.concurrency, max_keepalive_connections=20),
            )

    async def stop(self) -> None:
        """Gracefully close the HTTP client pool."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def sign_payload(self, timestamp: int, payload_bytes: bytes) -> str:
        """Compute HMAC SHA-256 signature for payload verification."""
        if not self.secret_key:
            return ""
        message = f"{timestamp}.".encode() + payload_bytes
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={signature}"

    async def send_event(self, event: DomainEvent) -> bool:
        """Send a single domain event as an HTTP POST webhook with retries."""
        payload_bytes = event.to_json().encode("utf-8")
        now_ts = int(time.time())

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SyntheticForge-Webhook/0.1.0",
            "X-SyntheticForge-Event-ID": event.event_id,
            "X-SyntheticForge-Entity": event.entity_name,
            "X-SyntheticForge-State": event.state,
            "X-Webhook-Timestamp": str(now_ts),
        }

        if event.trace_context:
            headers["traceparent"] = event.trace_context.traceparent
            headers["tracestate"] = f"span={event.trace_context.span_id}"

        if self.secret_key:
            headers["X-Signature-256"] = self.sign_payload(now_ts, payload_bytes)

        if self.mock_mode or not self._client:
            self.mock_requests.append(
                {
                    "url": self.endpoint_url,
                    "headers": headers,
                    "event": event.to_dict(),
                }
            )
            self.sent_count += 1
            return True

        async with self._semaphore:
            backoff = 0.1
            for attempt in range(self.max_retries):
                try:
                    resp = await self._client.post(
                        self.endpoint_url,
                        content=payload_bytes,
                        headers=headers,
                    )
                    if resp.status_code < 400:
                        self.sent_count += 1
                        return True
                    elif resp.status_code >= 500:
                        # Server error, retry with exponential backoff
                        await asyncio.sleep(backoff)
                        backoff *= 2
                    else:
                        # Client error (4xx), do not retry
                        logger.warning(
                            "Webhook returned %d for event %s", resp.status_code, event.event_id
                        )
                        self.error_count += 1
                        return False
                except Exception as exc:
                    if attempt == self.max_retries - 1:
                        logger.error(
                            "Webhook POST failed after %d retries: %s", self.max_retries, exc
                        )
                        self.error_count += 1
                        return False
                    await asyncio.sleep(backoff)
                    backoff *= 2

        return False
