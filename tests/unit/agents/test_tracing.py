"""Tests for per-run OpenInference tracing of agent runs.

Runs real LangChain tools with the callback from ``run_callbacks`` and an
in-memory OpenTelemetry exporter, so the span tree is the real one. No model
or network is involved.
"""

import asyncio
import builtins
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


class TestPrivacySwitchIsGone:
    """No environment variable hides text on an agent LLM span."""

    _HIDE_FLAGS = (
        "OPENINFERENCE_HIDE_INPUTS",
        "OPENINFERENCE_HIDE_OUTPUTS",
        "OPENINFERENCE_HIDE_INPUT_MESSAGES",
        "OPENINFERENCE_HIDE_OUTPUT_MESSAGES",
        "OPENINFERENCE_HIDE_MODEL_INVOCATION_PARAMS",
        "OPENINFERENCE_HIDE_EMBEDDING_VECTORS",
    )

    def _chat_model(self) -> Any:
        """Return a chat model answering from a mock transport."""
        import httpx  # noqa: PLC0415
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        def reply(request: httpx.Request) -> httpx.Response:
            """Answer any chat completion with plain text and a usage block."""
            return httpx.Response(
                200,
                json={
                    "id": "x",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "fake",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "the answer"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 11,
                        "completion_tokens": 7,
                        "total_tokens": 18,
                    },
                },
            )

        transport = httpx.MockTransport(reply)
        return ChatOpenAI(
            model="fake",
            api_key="x",
            base_url="http://fake/v1",
            http_client=httpx.Client(transport=transport),
            http_async_client=httpx.AsyncClient(transport=transport),
        )

    async def _llm_span(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
        """Run a real chat-model call through the callback and return its span."""
        for name in self._HIDE_FLAGS:
            monkeypatch.setenv(name, "true")
        provider, exporter = _provider()
        callback = run_callbacks(provider.get_tracer("t"))

        await self._chat_model().ainvoke(
            "secret question", config={"callbacks": callback}
        )

        llm_spans = [
            span
            for span in exporter.get_finished_spans()
            if span.attributes.get("openinference.span.kind") == "LLM"
        ]
        assert len(llm_spans) == 1, f"expected one LLM span, got {len(llm_spans)}"
        attributes = llm_spans[0].attributes
        assert attributes is not None
        return dict(attributes)

    async def test_hide_variables_do_not_redact_input_messages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The first input message keeps its text too."""
        attributes = await self._llm_span(monkeypatch)

        content = str(attributes["llm.input_messages.0.message.content"])
        assert content != "__REDACTED__"
        assert "secret question" in content

    async def test_hide_variables_do_not_redact_output_messages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The reply text is recorded as well."""
        attributes = await self._llm_span(monkeypatch)

        content = str(attributes["llm.output_messages.0.message.content"])
        assert content != "__REDACTED__"
        assert "the answer" in content
