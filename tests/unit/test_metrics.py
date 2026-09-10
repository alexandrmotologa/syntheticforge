"""Unit tests for Prometheus metrics registry and exporter."""

import httpx
import pytest

from syntheticforge.metrics import MetricsRegistry, PrometheusExporter
from syntheticforge.tui.stats import StreamStats


def test_metrics_registry_formatting() -> None:
    stats = StreamStats()
    stats.record_event("orders", "CREATED")
    stats.record_event("orders", "COMPLETED", anomaly_type="duplicate_key")

    reg = MetricsRegistry()
    reg.update_from_stats(stats, target="kafka")

    text = reg.to_prometheus_text()
    assert "# TYPE syntheticforge_events_total counter" in text
    assert 'syntheticforge_events_total{entity="orders",state="ALL",target="kafka"} 2' in text
    assert 'syntheticforge_anomalies_total{type="duplicate_key"} 1' in text
    assert "syntheticforge_rate_eps" in text


@pytest.mark.asyncio
async def test_prometheus_exporter_http_endpoint() -> None:
    exporter = PrometheusExporter(port=19100, host="127.0.0.1")
    await exporter.start()

    stats = StreamStats()
    stats.record_event("users", "SNAPSHOT")
    exporter.registry.update_from_stats(stats, target="webhook")

    async with httpx.AsyncClient() as client:
        resp = await client.get("http://127.0.0.1:19100/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        assert 'entity="users"' in resp.text

    await exporter.stop()
