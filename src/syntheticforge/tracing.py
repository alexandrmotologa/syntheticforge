"""OpenTelemetry and W3C Trace Context generation and causal propagation."""

from __future__ import annotations

import random
from dataclasses import dataclass


def generate_trace_id() -> str:
    """Generate a 128-bit hexadecimal trace ID."""
    return f"{random.getrandbits(128):032x}"


def generate_span_id() -> str:
    """Generate a 64-bit hexadecimal span ID."""
    return f"{random.getrandbits(64):016x}"


@dataclass
class TraceContext:
    """W3C Distributed Trace Context representation."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    sampled: bool = True

    @classmethod
    def new_root(cls, sampled: bool = True) -> TraceContext:
        """Create a new root trace context with fresh trace_id and span_id."""
        return cls(
            trace_id=generate_trace_id(),
            span_id=generate_span_id(),
            parent_span_id=None,
            sampled=sampled,
        )

    def create_child(self) -> TraceContext:
        """Create a child trace context preserving the trace_id with a new span_id."""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=generate_span_id(),
            parent_span_id=self.span_id,
            sampled=self.sampled,
        )

    @property
    def traceparent(self) -> str:
        """Format the traceparent header according to the W3C Trace Context specification."""
        flags = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{flags}"

    def to_headers(self) -> dict[str, str]:
        """Convert trace context to HTTP / message headers."""
        return {
            "traceparent": self.traceparent,
            "tracestate": f"forge_span={self.span_id}",
        }


class CausalTraceManager:
    """Maintains causal trace continuity across interconnected entity events."""

    def __init__(self) -> None:
        # Maps (entity_name, entity_id) -> TraceContext
        self._entity_traces: dict[tuple[str, str], TraceContext] = {}

    def get_or_create_trace(
        self,
        entity_name: str,
        entity_id: str,
        parent_entity: str | None = None,
        parent_id: str | None = None,
    ) -> TraceContext:
        """Retrieve existing trace context or branch a child span from parent entity trace."""
        key = (entity_name, str(entity_id))
        if key in self._entity_traces:
            # Advance to a new child span for subsequent lifecycle transitions
            current = self._entity_traces[key]
            child = current.create_child()
            self._entity_traces[key] = child
            return child

        # Check if parent entity has an active trace to branch from
        if parent_entity and parent_id:
            parent_key = (parent_entity, str(parent_id))
            if parent_key in self._entity_traces:
                parent_trace = self._entity_traces[parent_key]
                child_trace = parent_trace.create_child()
                self._entity_traces[key] = child_trace
                return child_trace

        # Root trace
        root_trace = TraceContext.new_root()
        self._entity_traces[key] = root_trace
        return root_trace
