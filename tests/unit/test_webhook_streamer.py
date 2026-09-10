"""Unit tests for WebhookStreamer with HMAC SHA-256 signing and retries."""

import hashlib
import hmac
from datetime import UTC, datetime

import pytest

from syntheticforge.generator.lifecycle_simulator import DomainEvent
from syntheticforge.streaming.webhook_streamer import WebhookStreamer
from syntheticforge.tracing import TraceContext


def test_hmac_signature_generation() -> None:
    secret = "super-secret-key-123"
    streamer = WebhookStreamer(endpoint_url="http://localhost:8080/webhook", secret_key=secret)

    payload = b'{"event": "test"}'
    ts = 1726000000

    sig = streamer.sign_payload(ts, payload)
    assert sig.startswith("sha256=")

    # Independently verify signature
    expected_hmac = hmac.new(
        secret.encode("utf-8"),
        f"{ts}.".encode() + payload,
        hashlib.sha256,
    ).hexdigest()
    assert sig == f"sha256={expected_hmac}"


@pytest.mark.asyncio
async def test_webhook_streamer_mock_dispatch() -> None:
    streamer = WebhookStreamer(
        endpoint_url="https://api.example.com/events",
        secret_key="my-key",
        mock_mode=True,
    )
    await streamer.start()

    trace = TraceContext.new_root()
    ev = DomainEvent(
        event_id="ev_100",
        entity_name="payments",
        entity_id="pay_555",
        state="SUCCESS",
        previous_state="PENDING",
        timestamp=datetime.now(UTC),
        payload={"amount": 42.5},
        trace_context=trace,
    )

    success = await streamer.send_event(ev)
    assert success is True
    assert streamer.sent_count == 1
    assert len(streamer.mock_requests) == 1

    req = streamer.mock_requests[0]
    assert req["url"] == "https://api.example.com/events"
    assert req["headers"]["X-SyntheticForge-Entity"] == "payments"
    assert req["headers"]["traceparent"] == trace.traceparent
    assert "X-Signature-256" in req["headers"]

    await streamer.stop()
