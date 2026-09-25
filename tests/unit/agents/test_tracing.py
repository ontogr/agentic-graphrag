"""Tests for per-run OpenInference tracing of agent runs.

Runs real LangChain tools with the callback from ``run_callbacks`` and an
in-memory OpenTelemetry exporter, so the span tree is the real one. No model
or network is involved. The canary test fails when the private OpenInference
module the callback is imported from moves; revisit the ``<0.2`` bound on
``openinference-instrumentation-langchain`` in ``pyproject.toml`` if it does.
"""

import asyncio
import builtins
import importlib
from typing import Any

import pytest
from langchain_core.tools import tool
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.agents import AgentMissingExtraError
from agrag.agents.tracing import require_tracing, run_callbacks


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _by_id(spans: tuple[ReadableSpan, ...]) -> dict[int, ReadableSpan]:
    return {span.context.span_id: span for span in spans}


def _tool_spans(spans: tuple[ReadableSpan, ...]) -> dict[str, ReadableSpan]:
    return {
        span.name: span
        for span in spans
        if span.attributes.get("openinference.span.kind") == "TOOL"
    }


@tool
async def inner(x: str) -> str:
    """Return the input."""
    return x


@tool
async def other(x: str) -> str:
    """Return the input."""
    return x


@tool
async def outer(x: str) -> str:
    """Call two tools in parallel."""
    return "".join(await asyncio.gather(inner.ainvoke(x), other.ainvoke(x)))


class TestRunCallbacks:
    """Tests the per-run callback built from a tracer."""

    async def test_inner_tool_spans_are_children_of_outer_tool_span(self) -> None:
        """Tools called inside a tool nest under its span."""
        provider, exporter = _provider()

        await outer.ainvoke(
            "a", config={"callbacks": run_callbacks(provider.get_tracer("t"))}
        )

        spans = exporter.get_finished_spans()
        tools = _tool_spans(spans)
        assert set(tools) == {"outer", "inner", "other"}
        for name in ("inner", "other"):
            parent = tools[name].parent
            assert parent is not None
            assert parent.span_id == tools["outer"].context.span_id

    def test_none_tracer_returns_no_callbacks(self) -> None:
        """No tracer means no callbacks."""
        assert run_callbacks(None) == []

    async def test_agent_spans_nest_under_the_active_span(self) -> None:
        """Spans join the caller's trace instead of starting a new one."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")

        with tracer.start_as_current_span("caller") as caller:
            await outer.ainvoke("a", config={"callbacks": run_callbacks(tracer)})

        spans = exporter.get_finished_spans()
        outer_span = _tool_spans(spans)["outer"]
        assert outer_span.parent is not None
        assert outer_span.parent.span_id == caller.get_span_context().span_id
        assert len({span.context.trace_id for span in spans}) == 1

    async def test_runs_with_separate_exporters_do_not_share_spans(self) -> None:
        """Concurrent runs with different tracers keep their spans apart."""
        provider_a, exporter_a = _provider()
        provider_b, exporter_b = _provider()

        await asyncio.gather(
            outer.ainvoke(
                "a", config={"callbacks": run_callbacks(provider_a.get_tracer("a"))}
            ),
            inner.ainvoke(
                "b", config={"callbacks": run_callbacks(provider_b.get_tracer("b"))}
            ),
        )

        assert set(_tool_spans(exporter_a.get_finished_spans())) == {
            "outer",
            "inner",
            "other",
        }
        assert set(_tool_spans(exporter_b.get_finished_spans())) == {"inner"}

    def test_private_tracer_module_still_exports_the_callback(self) -> None:
        """Canary for the private OpenInference import."""
        try:
            module = importlib.import_module(
                "openinference.instrumentation.langchain._tracer"
            )
            assert hasattr(module, "OpenInferenceTracer")
        except (ImportError, AssertionError):
            pytest.fail(
                "OpenInferenceTracer moved in openinference-instrumentation-"
                "langchain; revisit the <0.2 bound in pyproject.toml"
            )


class TestRequireTracing:
    """Tests the check for the observability extra."""

    def test_identifies_the_missing_extra_when_openinference_is_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The error identifies the installable extra when OpenInference is absent."""
        real_import = builtins.__import__

        def blocked(name: str, *args: Any, **kwargs: Any) -> Any:
            if name.startswith("openinference"):
                raise ModuleNotFoundError(name, name=name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)

        with pytest.raises(
            AgentMissingExtraError,
            match=r"agentic-graphrag\[observability\]",
        ) as exc:
            require_tracing()

        assert exc.value.extra == "observability"

    def test_preserves_import_errors_from_installed_dependencies(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only a missing OpenInference package means the extra is absent."""
        real_import = builtins.__import__

        def blocked(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "openinference.instrumentation":
                raise ModuleNotFoundError("opentelemetry", name="opentelemetry")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)

        with pytest.raises(ModuleNotFoundError, match="opentelemetry"):
            require_tracing()

    def test_passes_when_the_extra_is_installed(self) -> None:
        """No error when the extra is installed."""
        require_tracing()
