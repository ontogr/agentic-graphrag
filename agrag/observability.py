"""OpenTelemetry wiring for the ingestion layer.

This module imports only ``opentelemetry-api``. The SDK and exporters stay in
the optional ``observability`` extra and are never imported here; a caller
wires them before opening a graph. The tracer is constructor-injected, never
ambient: ``get_tracer(None)`` returns an explicit no-op tracer instead of
reaching the global ``TracerProvider``.
"""

from opentelemetry import trace
from opentelemetry.trace import Tracer


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
