"""End-to-end test that a real agent run exports a span tree.

Runs the deepagents planner with a real LLM against a stub search engine and
an in-memory OpenTelemetry exporter. It checks the shape of the trace only:
the planner delegates to the researcher through a ``task`` tool span, and the
researcher's own tool calls appear beneath it. It skips without an LLM
endpoint in ``.env``. The span dump goes to the e2e artifact directory.
"""

import importlib.util
import os
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_schema import GENERIC
from agrag.common.data_models.search_result import SearchResult
from tests.integration.e2e._artifact import write_artifact


def _llm_configured() -> bool:
    """Return True when an agent LLM endpoint is configured."""
    load_dotenv()
    base_url = os.environ.get("AGENT_LLM_BASE_URL") or os.environ.get("LLM_BASE_URL")
    api_key = os.environ.get("AGENT_LLM_API_KEY") or os.environ.get("LLM_API_KEY")
    return bool(base_url and api_key)


@pytest.mark.skipif(
    importlib.util.find_spec("deepagents") is None, reason="deepagents not installed"
)
@pytest.mark.skipif(not _llm_configured(), reason="LLM endpoint not configured")
class TestAgentTracingE2E:
    """A traced agent run exports planner, researcher and tool spans."""

    async def test_researcher_tool_spans_nest_under_the_task_span(self) -> None:
        """The researcher's tool calls are descendants of the ``task`` span."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        engine = MagicMock()
        engine.graph_schema = GENERIC
        engine.find_entity = AsyncMock(return_value=None)
        engine.list_relationship_types = AsyncMock(return_value=[])
        engine.traverse = AsyncMock(return_value=[])
        engine.search = AsyncMock(
            return_value=[
                SearchResult(
                    item=Entity(id=uuid4(), label="Person", name="Alice"),
                    score=0.9,
                    method="entity",
                )
            ]
        )
        agent = build_agent(
            engine=engine,
            llm_settings=AgentLLMSettings.from_openai_compatible_env(),
            tracer=provider.get_tracer("agrag-e2e"),
        )

        await agent.ainvoke(
            {"messages": [{"role": "user", "content": "Who is Alice?"}]}
        )

        spans = exporter.get_finished_spans()
        by_id = {span.context.span_id: span for span in spans}
        tools = [
            span
            for span in spans
            if span.attributes.get("openinference.span.kind") == "TOOL"
        ]
        tasks = [span for span in tools if span.name == "task"]
        assert tasks, "the planner did not delegate through the task tool"

        def ancestors(span: ReadableSpan) -> set[int]:
            found: set[int] = set()
            while span.parent is not None and span.parent.span_id in by_id:
                span = by_id[span.parent.span_id]
                found.add(span.context.span_id)
            return found

        task_ids = {span.context.span_id for span in tasks}
        nested = [
            span for span in tools if span.name != "task" and task_ids & ancestors(span)
        ]
        assert nested, "no researcher tool span sits under a task span"
        record = write_artifact(
            "agent_tracing",
            {
                "has_task_span": bool(tasks),
                "has_nested_tool_span": bool(nested),
                "kinds": sorted(
                    {
                        str(span.attributes.get("openinference.span.kind"))
                        for span in spans
                    }
                ),
            },
        )
        assert record["has_nested_tool_span"] is True
