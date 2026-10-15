"""End-to-end test that a task-scoped agent run exports tool spans."""

import importlib.util
import os

import pytest
from dotenv import load_dotenv
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings
from agrag.embedding import build_embedder
from agrag.graphdb import build_graph_store
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
@pytest.mark.skipif(
    importlib.util.find_spec("neo4j") is None, reason="neo4j extra not installed"
)
@pytest.mark.skipif(not _llm_configured(), reason="LLM endpoint not configured")
class TestAgentTracingE2E:
    """A traced agent run exports planner, researcher and tool spans."""

    async def test_researcher_tool_spans_nest_under_the_task_span(self) -> None:
        """The researcher's tool calls are descendants of the ``task`` span."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        graph_store = build_graph_store("neo4j")
        await graph_store.connect()
        embedder = build_embedder("ibm-granite/granite-embedding-small-english-r2")
        agent = build_agent(
            graph_store=graph_store,
            embedder=embedder,
            scope=frozenset(),
            project_id="agent-tracing-e2e",
            agent_id="tracing-agent",
            llm_settings=AgentLLMSettings.from_openai_compatible_env(),
            tracer=provider.get_tracer("agrag-e2e"),
        )

        await agent.ainvoke(
            {"task_name": "alice", "question": "Who is Alice?"}
        )
        await graph_store.close()

        spans = exporter.get_finished_spans()
        by_id = {span.context.span_id: span for span in spans}
        tools = [
            span
            for span in spans
            if span.attributes.get("openinference.span.kind") == "TOOL"
        ]
        assert tools, "the agent emitted no tool span"

        def ancestors(span: ReadableSpan) -> set[int]:
            found: set[int] = set()
            while span.parent is not None and span.parent.span_id in by_id:
                span = by_id[span.parent.span_id]
                found.add(span.context.span_id)
            return found

        nested = [span for span in tools if ancestors(span)]
        assert nested, "no tool span has a parent span"
        record = write_artifact(
            "agent_tracing",
            {
                "has_tool_span": bool(tools),
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
