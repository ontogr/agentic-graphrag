"""Tests for the OpenTelemetry observability helpers."""

from contextlib import contextmanager

import pytest
from opentelemetry import trace

from agrag.observability import get_tracer, traced


class _RecordingSpan(trace.Span):
    """A minimal real ``Span`` so ``get_current_span`` recognizes it as attached."""

    def get_span_context(self) -> trace.SpanContext:
        return trace.INVALID_SPAN_CONTEXT

    def is_recording(self) -> bool:
        return True

    def end(self, end_time: int | None = None) -> None:
        pass

    def set_attributes(self, attributes) -> None:
        pass

    def set_attribute(self, key: str, value) -> None:
        pass

    def add_event(
        self, name: str, attributes=None, timestamp: int | None = None
    ) -> None:
        pass

    def update_name(self, name: str) -> None:
        pass

    def set_status(self, status, description: str | None = None) -> None:
        pass

    def record_exception(
        self, exception, attributes=None, timestamp=None, escaped=False
    ) -> None:
        pass


class _RecordingTracer:
    """A stand-in tracer that records span starts without an SDK."""

    def __init__(self) -> None:
        self.spans: list[str] = []

    @contextmanager
    def start_as_current_span(self, name: str):
        self.spans.append(name)
        yield

    def start_span(self, name: str) -> _RecordingSpan:
        self.spans.append(name)
        return _RecordingSpan()


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

    def test_span_still_opens_when_the_wrapped_function_raises(self) -> None:
        """A span opens for the call even when the wrapped function raises."""
        tracer = _RecordingTracer()

        @traced(tracer)
        def boom() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            boom()
        assert len(tracer.spans) == 1
        assert "boom" in tracer.spans[0]

    def test_keeps_span_open_for_a_generator_returned_by_a_plain_function(
        self,
    ) -> None:
        """A span stays open while a manually returned generator iterates."""
        tracer = _RecordingTracer()

        def _inner():
            yield 1
            yield 2

        @traced(tracer)
        def wrapper():
            return _inner()

        result = list(wrapper())
        assert result == [1, 2]
        assert len(tracer.spans) == 1
        assert "wrapper" in tracer.spans[0]

    def test_defers_context_attachment_until_the_generator_iterates(self) -> None:
        """An unconsumed generator does not leave its span attached as current."""
        tracer = _RecordingTracer()

        def _inner():
            yield 1

        @traced(tracer)
        def wrapper():
            return _inner()

        gen = wrapper()
        assert trace.get_current_span() is trace.INVALID_SPAN
        list(gen)
        assert trace.get_current_span() is trace.INVALID_SPAN

    def test_noop_tracer_runs_without_sdk(self) -> None:
        """Noop tracer runs without sdk."""

        @traced(None)
        def go() -> int:
            return 1

        assert go() == 1
