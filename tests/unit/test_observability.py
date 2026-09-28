"""Tests for agrag.observability.get_tracer.

Covers the never-ambient rule: a caller passing ``None`` gets an explicit
no-op tracer that never reaches the global ``TracerProvider``.
"""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.observability import get_tracer


class TestGetTracer:
    """get_tracer(None) never emits through a global provider."""

    def test_none_never_reaches_global_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A span opened on get_tracer(None) exports nothing."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        monkeypatch.setattr(trace, "get_tracer_provider", lambda: provider)

        tracer = get_tracer(None)
        with tracer.start_as_current_span("probe"):
            pass

        assert list(exporter.get_finished_spans()) == []
