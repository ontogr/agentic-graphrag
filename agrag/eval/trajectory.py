"""Agent trajectory evaluation: read runs, check structure, judge quality.

A trajectory is the ordered tool and model steps of one agent run, read from
its OpenTelemetry spans (see ``agrag.agents.tracing``). Structural rules over
it are deterministic; task completion and trajectory quality use an LLM judge.
"""

import json
from collections.abc import Sequence
from typing import Any, Literal

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import Tracer
from pydantic import BaseModel


class Step(BaseModel):
    """One tool or model step of an agent run.

    Attributes:
        kind: ``"tool"`` for a tool call, ``"llm"`` for a model call.
        name: The tool name, or the span name for a model call.
        args: The parsed ``input.value`` span attribute.
        output: The step's output text, unwrapped from its tool message.
        span_id: The span id as hex.
        parent_ids: The ancestor span ids, nearest first, as hex.
        started: Start time in nanoseconds.
        ended: End time in nanoseconds.
        subagent: The ``subagent_type`` of the nearest ancestor ``task``
            span, or None for a planner step.
    """

    kind: Literal["tool", "llm"]
    name: str
    args: dict[str, Any]
    output: str
    span_id: str
    parent_ids: list[str]
    started: int
    ended: int
    subagent: str | None


class Trajectory(BaseModel):
    """The ordered steps of one agent run.

    Attributes:
        steps: The run's tool and model steps in start order.
    """

    steps: list[Step]


def _kind(span: ReadableSpan) -> Literal["tool", "llm"] | None:
    """Return the step kind for a span, or None when it is not a step."""
    attributes = span.attributes or {}
    kind = attributes.get("openinference.span.kind")
    if kind == "TOOL":
        return "tool"
    if kind == "LLM":
        return "llm"
    return None


def _is_task(span: ReadableSpan) -> bool:
    """Tell a delegation span from any other tool span."""
    attributes = span.attributes or {}
    return str(attributes.get("tool.name", span.name)) == "task"


def _read_args(raw: Any) -> dict[str, Any]:
    """Parse ``input.value`` as JSON, keeping raw text when it is not JSON."""
    if raw is None:
        return {}
    text = raw if isinstance(raw, str) else str(raw)
    try:
        parsed = json.loads(text)
    except ValueError:
        return {"input": text}
    return parsed if isinstance(parsed, dict) else {"input": text}


def _read_output(raw: Any) -> str:
    """Unwrap a serialized tool message, keeping raw text otherwise.

    A tool span's ``output.value`` is a serialized ``ToolMessage``, so the
    step output is its ``data.content``. Anything else is kept as is.
    """
    if raw is None:
        return ""
    text = raw if isinstance(raw, str) else str(raw)
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    if isinstance(parsed, dict):
        data = parsed.get("data")
        if isinstance(data, dict) and "content" in data:
            content = data["content"]
            return content if isinstance(content, str) else json.dumps(content)
    return text


def _parent_ids(span: ReadableSpan, by_id: dict[int, ReadableSpan]) -> list[str]:
    """Return every ancestor span id, nearest first.

    The walk follows every span, including dropped ``CHAIN`` spans, so a step
    nested under middleware spans still records its full chain.
    """
    chain: list[str] = []
    seen: set[int] = set()
    if span.context is not None:
        seen.add(span.context.span_id)
    parent = span.parent
    while parent is not None and parent.span_id not in seen:
        seen.add(parent.span_id)
        chain.append(f"{parent.span_id:016x}")
        holder = by_id.get(parent.span_id)
        parent = holder.parent if holder is not None else None
    return chain


def _subagent(span: ReadableSpan, by_id: dict[int, ReadableSpan]) -> str | None:
    """Return the ``subagent_type`` of the nearest ancestor ``task`` span."""
    seen: set[int] = set()
    current = span
    while True:
        parent = current.parent
        if parent is None or parent.span_id in seen:
            return None
        seen.add(parent.span_id)
        holder = by_id.get(parent.span_id)
        if holder is None:
            return None
        if _is_task(holder):
            args = _read_args((holder.attributes or {}).get("input.value"))
            subagent_type = args.get("subagent_type")
            return str(subagent_type) if subagent_type is not None else None
        current = holder


def _read_step(span: ReadableSpan, by_id: dict[int, ReadableSpan]) -> Step:
    """Read one kept span as a trajectory step."""
    attributes = span.attributes or {}
    kind = _kind(span)
    name = str(attributes.get("tool.name", span.name)) if kind == "tool" else span.name
    context = span.context
    return Step(
        kind=kind or "tool",
        name=name,
        args=_read_args(attributes.get("input.value")),
        output=_read_output(attributes.get("output.value")),
        span_id=f"{context.span_id:016x}" if context is not None else "",
        parent_ids=_parent_ids(span, by_id),
        started=span.start_time or 0,
        ended=span.end_time or 0,
        subagent=_subagent(span, by_id),
    )


def read_trajectory(spans: Sequence[ReadableSpan]) -> Trajectory:
    """Read the tool and model steps from finished spans.

    Keeps ``TOOL`` and ``LLM`` spans, drops ``CHAIN`` spans, and orders steps
    by start time rather than export order. A step's ``subagent`` is the
    ``subagent_type`` of its nearest ancestor ``task`` span, or None for a
    planner step.

    Args:
        spans: The finished spans of one traced agent run.

    Returns:
        The run's trajectory in start order.
    """
    by_id: dict[int, ReadableSpan] = {}
    for span in spans:
        if span.context is not None:
            by_id[span.context.span_id] = span
    kept = [span for span in spans if _kind(span) is not None]
    kept.sort(key=lambda span: (span.start_time or 0, span.end_time or 0, span.name))
    return Trajectory(steps=[_read_step(span, by_id) for span in kept])


class SpanCapture:
    """Capture one agent run's spans for ``read_trajectory``.

    Use as a context manager around ``agent.ainvoke`` and read the run with
    ``trajectory()`` after. Each capture has its own provider and exporter,
    so captures never share spans and the global provider is unchanged.

    Example:
        with SpanCapture() as capture:
            agent = build_agent(engine, settings, tracer=capture.tracer)
            result = await agent.ainvoke({"messages": [...]})
        trajectory = capture.trajectory()
    """

    def __init__(self) -> None:
        """Create a private provider and exporter."""
        from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: PLC0415
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: PLC0415
            InMemorySpanExporter,
        )

        self._exporter = InMemorySpanExporter()
        self._provider = TracerProvider()
        self._provider.add_span_processor(SimpleSpanProcessor(self._exporter))

    @property
    def tracer(self) -> Tracer:
        """The tracer to pass as ``tracer=`` to ``build_agent``."""
        return self._provider.get_tracer("agrag.eval")

    def trajectory(self) -> Trajectory:
        """Read the captured spans as a trajectory."""
        return read_trajectory(self._exporter.get_finished_spans())

    def __enter__(self) -> "SpanCapture":
        """Return this capture."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Shut down the private provider."""
        self._provider.shutdown()
