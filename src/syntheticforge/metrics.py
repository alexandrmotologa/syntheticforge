"""Prometheus metrics registry and asynchronous HTTP exporter for soak testing."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict

from syntheticforge.tui.stats import StreamStats

logger = logging.getLogger(__name__)


class MetricsRegistry:
    """Collects and formats Prometheus metrics in standard text exposition format."""

    def __init__(self) -> None:
        self.events_total: dict[tuple[str, str, str], int] = defaultdict(int)
        self.anomalies_total: dict[str, int] = defaultdict(int)
        self.current_rate_eps: float = 0.0
        self.start_time: float = time.time()

    def update_from_stats(self, stats: StreamStats, target: str = "kafka") -> None:
        """Synchronize internal counters from StreamStats snapshot."""
        for ent, cnt in stats.entity_counts.items():
            self.events_total[(ent, "ALL", target)] = cnt
        for anom, cnt in stats.anomaly_counts.items():
            self.anomalies_total[anom] = cnt
        self.current_rate_eps = stats.current_eps

    def to_prometheus_text(self) -> str:
        """Format metrics according to Prometheus text exposition format 0.0.4."""
        lines = [
            "# HELP syntheticforge_events_total Total number of domain events emitted.",
            "# TYPE syntheticforge_events_total counter",
        ]
        for (ent, state, target), val in sorted(self.events_total.items()):
            lines.append(
                f'syntheticforge_events_total{{entity="{ent}",state="{state}",target="{target}"}} {val}'
            )

        lines.extend(
            [
                "# HELP syntheticforge_rate_eps Current instantaneous generation rate in events per second.",
                "# TYPE syntheticforge_rate_eps gauge",
                f"syntheticforge_rate_eps {self.current_rate_eps:.2f}",
                "# HELP syntheticforge_anomalies_total Total chaos anomalies injected.",
                "# TYPE syntheticforge_anomalies_total counter",
            ]
        )
        for anom_type, count in sorted(self.anomalies_total.items()):
            lines.append(f'syntheticforge_anomalies_total{{type="{anom_type}"}} {count}')

        elapsed = max(0.0, time.time() - self.start_time)
        lines.extend(
            [
                "# HELP syntheticforge_elapsed_seconds Total elapsed execution time in seconds.",
                "# TYPE syntheticforge_elapsed_seconds gauge",
                f"syntheticforge_elapsed_seconds {elapsed:.1f}",
                "",
            ]
        )
        return "\n".join(lines)


class PrometheusExporter:
    """Asynchronous HTTP server serving Prometheus metrics on /metrics."""

    def __init__(self, port: int = 9100, host: str = "0.0.0.0") -> None:
        self.port = port
        self.host = host
        self.registry = MetricsRegistry()
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        """Start the background HTTP server for Prometheus scraping."""
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        logger.info("PrometheusExporter listening on http://%s:%d/metrics", self.host, self.port)

    async def stop(self) -> None:
        """Stop the background HTTP server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await reader.readline()
            req = request_line.decode("utf-8", errors="ignore")
            # Read until empty line (end of headers)
            while True:
                line = await reader.readline()
                if not line or line == b"\r\n" or line == b"\n":
                    break

            if "GET /metrics" in req or "GET / " in req:
                body = self.registry.to_prometheus_text().encode("utf-8")
                response = (
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: text/plain; version=0.0.4; charset=utf-8\r\n"
                    b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
                    b"Connection: close\r\n\r\n" + body
                )
            else:
                response = b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\nNot Found\n"

            writer.write(response)
            await writer.drain()
        except Exception as e:
            logger.debug("Error handling Prometheus client request: %s", e)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
