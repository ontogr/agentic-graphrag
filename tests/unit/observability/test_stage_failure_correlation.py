"""Tests for the StageFailure span-correlation helpers in agrag.observability.

Uses a real SDK TracerProvider with an in-memory exporter, never a fake
recording tracer. Covers the is_recording rule: a no-op tracer wrapping a
real host context still propagates that context without leaking its ids
into StageFailure fields.
"""

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from agrag.observability import (
    get_tracer,
    record_stage_failure,
    record_swallowed_exception,
    stage_failure_context,
)


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a provider wired to an in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


class TestStageFailureContext:
    """stage_failure_context reads the current span only when recorded."""

    def test_never_returns_host_ids_under_tracer_none(self) -> None:
        """A host span active under tracer=None keeps its own ids private."""
        host_provider, host_exporter = _provider()
        host_tracer = host_provider.get_tracer("host")
        with (
            host_tracer.start_as_current_span("host.request"),
            get_tracer(None).start_as_current_span("agrag.ingestion.add"),
        ):
            assert record_stage_failure(ValueError("boom")) == (None, None)
        (host_span,) = host_exporter.get_finished_spans()
        assert host_span.name == "host.request"
        assert host_span.status.status_code is StatusCode.UNSET
        assert list(host_span.events) == []

    def test_host_context_still_propagates_through_noop_span(self) -> None:
        """Host-instrumented work inside an agrag call nests under the host."""
        host_provider, host_exporter = _provider()
        host_tracer = host_provider.get_tracer("host")
        with (
            host_tracer.start_as_current_span("host.request"),
            get_tracer(None).start_as_current_span("agrag.ingestion.add"),
            host_tracer.start_as_current_span("nested.host.work"),
        ):
            pass
        spans = {span.name: span for span in host_exporter.get_finished_spans()}
        assert spans["nested.host.work"].context.trace_id == (
            spans["host.request"].context.trace_id
        )
        assert spans["nested.host.work"].parent is not None


class TestRecordStageFailure:
    """record_stage_failure marks the span errored and returns its ids."""

    def test_marks_span_error_and_returns_matching_ids(self) -> None:
        """The span exports ERROR with one event for the exception."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("test")
        exc = ValueError("bad write")
        with tracer.start_as_current_span("agrag.storage.upsert_chunks"):
            trace_id, span_id = record_stage_failure(exc)
            assert (trace_id, span_id) == stage_failure_context()
        (span,) = exporter.get_finished_spans()
        assert span.status.status_code is StatusCode.ERROR
        assert len(list(span.events)) == 1
        event = list(span.events)[0]
        assert event.name == "exception"
        assert (event.attributes or {})["exception.message"] == "bad write"
        assert trace_id == format(span.context.trace_id, "032x")
        assert span_id == format(span.context.span_id, "016x")


class TestRecordSwallowedException:
    """record_swallowed_exception records without marking the span errored."""

    def test_leaves_status_unset(self) -> None:
        """A best-effort fallback shows the exception, not a failure."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("agrag.resolution.candidate_generation"):
            record_swallowed_exception(RuntimeError("transient hiccup"))
        (span,) = exporter.get_finished_spans()
        assert span.status.status_code is StatusCode.UNSET
        assert len(list(span.events)) == 1
