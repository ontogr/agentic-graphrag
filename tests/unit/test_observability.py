"""Tests for the OpenTelemetry observability helpers."""

from contextlib import contextmanager

import pytest

from agrag.observability import get_tracer, traced


class _RecordingTracer:
    """A stand-in tracer that records span starts without an SDK."""

    def __init__(self) -> None:
        self.spans: list[str] = []

    @contextmanager
    def start_as_current_span(self, name: str):
        self.spans.append(name)
        yield


class TestGetTracer:
    """The tracer helper falls back to a no-op global tracer."""

    def test_returns_caller_tracer(self) -> None:
        """Returns caller tracer."""
        tracer = _RecordingTracer()
        assert get_tracer(tracer) is tracer

    def test_none_returns_a_tracer(self) -> None:
        """None returns a tracer."""
        assert get_tracer(None) is not None


class TestTraced:
    """The traced decorator wraps sync, async, and generator calls."""

    def test_wraps_sync_function(self) -> None:
        """Wraps sync function."""
        tracer = _RecordingTracer()

        @traced(tracer)
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 5
        assert len(tracer.spans) == 1
        assert "add" in tracer.spans[0]

    def test_keeps_span_open_while_generator_iterates(self) -> None:
        """Keeps span open while generator iterates."""
        tracer = _RecordingTracer()

        @traced(tracer)
        def items():
            yield 1
            yield 2

        result = list(items())
        assert result == [1, 2]
        assert len(tracer.spans) == 1
        assert "items" in tracer.spans[0]

    async def test_wraps_async_function(self) -> None:
        """Wraps async function."""
        tracer = _RecordingTracer()

        @traced(tracer)
        async def go() -> int:
            return 7

        assert await go() == 7
        assert len(tracer.spans) == 1
        assert "go" in tracer.spans[0]

    def test_sync_function_exception_is_recorded_on_a_span(self) -> None:
        """Sync function exception is recorded on a span."""
        tracer = _RecordingTracer()

        @traced(tracer)
        def boom() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            boom()
        assert len(tracer.spans) == 1
        assert "boom" in tracer.spans[0]

    def test_noop_tracer_runs_without_sdk(self) -> None:
        """Noop tracer runs without sdk."""

        @traced(None)
        def go() -> int:
            return 1

        assert go() == 1
