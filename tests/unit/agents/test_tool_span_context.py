"""Tests for the tool-span bridge in agrag.agents.tracing.

Extends the run-callbacks tests: the bridge must make the running tool's own
OpenInference ``TOOL`` span current inside the tool body and restore the
caller's span after. Runs real LangChain tools with the real callback and an
in-memory exporter, so the parent relationships are the real ones.
"""

import asyncio
import contextlib
from typing import Any

import pytest
from langchain_core.tools import tool
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.agents.tracing import run_callbacks, tool_span_context


# The test sets this before invoking, so the tool can open a real span.
_current_tracer: list[Any] = []


@pytest.fixture(autouse=True)
def _reset_tracer():
    """Give every test a fresh slot for the tool's tracer."""
    _current_tracer.clear()
    yield
    _current_tracer.clear()


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a provider and exporter pair backed by one in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


@tool
async def bridged(x: str, callbacks: Any = None) -> str:
    """Open a span inside the tool and return its name."""
    with (
        tool_span_context(callbacks),
        _current_tracer[0].start_as_current_span("opened-under-the-tool"),
    ):
        return "opened-under-the-tool"


@tool
async def raising(x: str, callbacks: Any = None) -> str:
    """Raise after opening the bridge."""
    with tool_span_context(callbacks):
        raise RuntimeError("tool failed")


def _tool_spans(spans: tuple[ReadableSpan, ...]) -> dict[str, ReadableSpan]:
    """Return the TOOL spans by name."""
    return {
        span.name: span
        for span in spans
        if span.attributes.get("openinference.span.kind") == "TOOL"
    }


class TestToolSpanContext:
    """The bridge nests spans opened in a tool under its TOOL span."""

    async def test_tool_span_is_current_inside_a_bridged_tool(self) -> None:
        """A span opened in the tool has the tool's span as its parent."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        callbacks = run_callbacks(tracer)
        _current_tracer[:] = [tracer]

        await bridged.ainvoke("a", config={"callbacks": callbacks})

        spans = exporter.get_finished_spans()
        tools = _tool_spans(spans)
        assert "bridged" in tools
        opened = [s for s in spans if s.name == "opened-under-the-tool"]
        assert len(opened) == 1
        assert opened[0].parent is not None
        assert opened[0].parent.span_id == tools["bridged"].context.span_id

    async def test_the_callers_span_is_restored_after_the_tool(self) -> None:
        """A span opened after the tool call is the caller's child again."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        callbacks = run_callbacks(tracer)
        _current_tracer[:] = [tracer]

        with tracer.start_as_current_span("caller"):
            await bridged.ainvoke("a", config={"callbacks": callbacks})
            with tracer.start_as_current_span("after"):
                pass

        spans = exporter.get_finished_spans()
        after_span = next(s for s in spans if s.name == "after")
        caller_span = next(s for s in spans if s.name == "caller")
        assert after_span.parent is not None
        assert after_span.parent.span_id == caller_span.context.span_id

    async def test_two_parallel_calls_nest_under_their_own_tool_spans(self) -> None:
        """Each parallel call nests under its own TOOL span, in one trace."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        callbacks = run_callbacks(tracer)
        _current_tracer[:] = [tracer]

        await asyncio.gather(
            bridged.ainvoke("a", config={"callbacks": callbacks}),
            bridged.ainvoke("b", config={"callbacks": callbacks}),
        )

        spans = exporter.get_finished_spans()
        tool_spans = [s for s in spans if s.name == "bridged"]
        opened = [s for s in spans if s.name == "opened-under-the-tool"]
        assert len(tool_spans) == 2
        assert len(opened) == 2
        # The two calls share no trace when no caller span wraps them, so
        # pair each inner span with the tool span it declares as parent.
        tool_ids = {s.context.span_id for s in tool_spans}
        children_per_tool: dict[int, int] = {}
        for opened_span in opened:
            assert opened_span.parent is not None
            assert opened_span.parent.span_id in tool_ids
            children_per_tool[opened_span.parent.span_id] = (
                children_per_tool.get(opened_span.parent.span_id, 0) + 1
            )
        assert set(children_per_tool.values()) == {1}

    async def test_a_raising_tool_records_its_exception_once(self) -> None:
        """The bridge adds no second exception event to the TOOL span."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        callbacks = run_callbacks(tracer)
        _current_tracer[:] = [tracer]

        with contextlib.suppress(RuntimeError):
            await raising.ainvoke("a", config={"callbacks": callbacks})

        tools = _tool_spans(exporter.get_finished_spans())
        assert "raising" in tools
        exceptions = [e for e in tools["raising"].events if e.name == "exception"]
        assert len(exceptions) == 1
