"""OpenTelemetry wiring for the ingestion layer.

This module imports only ``opentelemetry-api``. The SDK and exporters stay in
the optional ``observability`` extra and are never imported here; a caller
wires them before opening a graph. The tracer is constructor-injected, never
ambient: ``get_tracer(None)`` returns an explicit no-op tracer instead of
reaching the global ``TracerProvider``.
"""

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Tracer


# Spellings follow the OpenTelemetry database span conventions. The package
# that ships these names is not a dependency because every release pins
# opentelemetry-api to an exact version.
DB_SYSTEM_NAME = "db.system.name"
DB_NAMESPACE = "db.namespace"
DB_QUERY_TEXT = "db.query.text"
DB_COLLECTION_NAME = "db.collection.name"
DB_OPERATION_BATCH_SIZE = "db.operation.batch.size"
DB_QUERY_PARAMETER_PREFIX = "db.query.parameter."


def get_tracer(tracer: Tracer | None) -> Tracer:
    """Return a usable tracer.

    Args:
        tracer: A caller-supplied tracer, or ``None`` for an explicit no-op tracer.

    Returns:
        agrag uses the supplied tracer or a no-op for ``None`` and skips global tracing.
    """
    if tracer is None:
        return trace.NoOpTracer()
    return tracer


def stage_failure_context() -> tuple[str | None, str | None]:
    """Return the current span's trace and span id as hex, or (None, None).

    Reads whatever span is ambiently current. Returns ``(None, None)`` when
    that span is not being recorded -- true when no span is open, when the
    current span came from ``get_tracer(None)``'s no-op tracer (even one
    wrapping a real ambient context for correct propagation -- see the
    module-level note above), and when a real tracer's sampler dropped the
    span. Uses ``is_recording()``, not the span context's ``is_valid``: a
    no-op tracer's span can carry a *valid* context (a real host trace id it
    is merely propagating, not recording into) without this function ever
    exposing that id.
    """
    span = trace.get_current_span()
    if not span.is_recording():
        return None, None
    span_context = span.get_span_context()
    return (
        format(span_context.trace_id, "032x"),
        format(span_context.span_id, "016x"),
    )


def record_stage_failure(exc: Exception) -> tuple[str | None, str | None]:
    """Record ``exc`` as an error on the current span, then return its ids.

    Call this from inside the ``except`` block that constructs the
    ``StageFailure`` this exception maps to, and only from code running
    under a span `agrag` itself opened (any span this plan or a later one
    opens, real or no-op) -- never from a point where the only ambient span
    is one a host application opened itself, which this would incorrectly
    mark as errored. Every call site this plan adds sits inside at least
    one `agrag`-opened root span, so this invariant always holds; a future
    caller adding a new StageFailure site outside any `agrag` span would
    need its own span first, not a bare call to this function.

    The current span must still be open (not yet exited its `with` block)
    at the point this runs -- a span that already closed before the
    ``except`` ran is not the current span here, and the ids returned
    would correlate to whatever the caller's own ambient span is instead.

    Returns:
        The current span's ``(trace_id, span_id)`` as hex strings, for
        ``StageFailure.trace_id``/``.span_id``, or ``(None, None)`` when
        `stage_failure_context` would also return that.
    """
    span = trace.get_current_span()
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR))
    return stage_failure_context()


def record_swallowed_exception(exc: Exception) -> None:
    """Record ``exc`` on the current span without marking it errored.

    For a path that intentionally continues after ``exc`` without failing
    the caller (a best-effort fallback, background recovery): the trace
    shows the exception happened, but the span's own status is left alone,
    since the caller's behavior did not change because of it. Same
    ambient-span invariant as `record_stage_failure` above.
    """
    trace.get_current_span().record_exception(exc)
