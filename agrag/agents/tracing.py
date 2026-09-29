"""Per-run OpenInference tracing for agent runs.

``build_agent`` takes an optional OpenTelemetry ``Tracer``. Each ``ainvoke``
passes a fresh OpenInference callback built from it, so no global tracer
provider or instrumentation is installed. deepagents forwards the parent's
callbacks to the researcher and verifier subagents, so their tool and model
calls appear in the same trace.
"""

import inspect
from typing import Any

from opentelemetry.trace import Tracer

from agrag.agents.errors import AgentMissingExtraError


def _import_tracer_classes() -> tuple[Any, Any, Any]:
    """Import the OpenInference classes, with an actionable error on failure."""
    try:
        from openinference.instrumentation import (  # noqa: PLC0415
            OITracer,
            TraceConfig,
        )
    except ModuleNotFoundError as exc:
        if exc.name not in {"openinference", "openinference.instrumentation"}:
            raise
        raise AgentMissingExtraError("observability") from exc
    try:
        from openinference.instrumentation.langchain._tracer import (  # noqa: PLC0415
            OpenInferenceTracer,
        )
    except ImportError as exc:
        raise ImportError(
            "The installed openinference-instrumentation-langchain no longer has "
            "the expected layout. Install a version in the range "
            ">=0.1.76,<0.2: pip install 'agentic-graphrag[observability]'"
        ) from exc
    return OITracer, TraceConfig, OpenInferenceTracer


def require_tracing() -> None:
    """Raise a typed error when tracing dependencies are unavailable.

    Raises:
        AgentMissingExtraError: The ``observability`` extra is not installed.
        ImportError: The installed OpenInference package has an incompatible
            layout.
    """
    _import_tracer_classes()


def _record_all(trace_config: Any) -> Any:
    """Return a TraceConfig with every ``hide_*`` flag off.

    The flags are read from the signature so a new ``hide_*`` flag in a
    later release is covered. Spans always carry full text, whatever the
    environment says.

    Args:
        trace_config: The OpenInference ``TraceConfig`` class.

    Returns:
        A ``TraceConfig`` with every ``hide_*`` flag set to ``False``.
    """
    hide_flags = {
        name: False
        for name in inspect.signature(trace_config).parameters
        if name.startswith("hide_")
    }
    return trace_config(**hide_flags)


def run_callbacks(tracer: Tracer | None) -> list[Any]:
    """Return the callbacks for one agent run.

    The callback holds per-run state, so build a new one for every run.
    Spans carry the question, tool inputs, and evidence text.

    Args:
        tracer: The tracer that receives the spans, or ``None`` to disable
            tracing.

    Returns:
        A one-item callback list, or an empty list when ``tracer`` is ``None``.
    """
    if tracer is None:
        return []
    oi_tracer, trace_config, callback_cls = _import_tracer_classes()
    # Agent spans nest under the caller's active span, not a new root trace.
    return [
        callback_cls(
            oi_tracer(tracer, _record_all(trace_config)),
            separate_trace_from_runtime_context=False,
        )
    ]
