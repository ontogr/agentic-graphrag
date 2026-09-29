"""End-to-end agent tracing against a real Neo4j and a real LLM.

One tracer is given to the graph store, the engine and ``build_agent``. Two
independent lookups are delegated to parallel ``task`` calls, and each
retrieval span must nest under the ``TOOL`` span of the call that made it,
which in turn sits under a ``task`` span. The span tree is written to the test
output directory as JSON. The test skips when no agent LLM endpoint is
configured.
"""

import json
import os
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.eval.trajectory import read_trajectory
from agrag.graphdb import build_graph_store
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings
from tests.integration.eval.conftest import TinyCorpus, _FakeHashedWordEmbedder


_OUTPUT_DIR = Path(os.environ.get("AGRAG_TRACING_OUTPUT_DIR", "test-output"))

_PROMPT = (
    "I need two independent facts. Delegate each to its own researcher "
    "subagent with the task tool, and issue both task calls in the same "
    "turn so they run in parallel. Fact 1: who founded Zephyra Robotics? "
    "Fact 2: how much weight can the Lumen-9 robot lift? Then answer both."
)


def _span_tree(spans: tuple[ReadableSpan, ...]) -> dict:
    """Serialize exported spans as one parent-pointer tree."""
    by_id = {span.context.span_id: span for span in spans}
    nodes = []
    for span in spans:
        parent = span.parent
        nodes.append(
            {
                "name": span.name,
                "trace_id": f"{span.context.trace_id:032x}",
                "span_id": f"{span.context.span_id:016x}",
                "parent_span_id": (
                    f"{parent.span_id:016x}" if parent is not None else None
                ),
                "parent_name": (
                    by_id[parent.span_id].name
                    if parent is not None and parent.span_id in by_id
                    else None
                ),
                "attributes": dict(span.attributes or {}),
            }
        )
    return {"spans": nodes}


def _ancestors(
    span: ReadableSpan, by_id: dict[int, ReadableSpan]
) -> list[ReadableSpan]:
    """Return the exported ancestors of a span, nearest first."""
    chain: list[ReadableSpan] = []
    parent = span.parent
    while parent is not None and parent.span_id in by_id:
        holder = by_id[parent.span_id]
        chain.append(holder)
        parent = holder.parent
    return chain


def _is_tool(span: ReadableSpan) -> bool:
    """Return True for an OpenInference TOOL span."""
    return (span.attributes or {}).get("openinference.span.kind") == "TOOL"


def _tool_name(span: ReadableSpan) -> str | None:
    """Return the tool name of a TOOL span, or None for any other span."""
    return str((span.attributes or {}).get("tool.name")) if _is_tool(span) else None


class TestAgentTracing:
    """Retrieval spans nest under the tool call that made them."""

    async def test_retrieval_spans_nest_under_their_task_tool_span(
        self, tiny_corpus: TinyCorpus
    ) -> None:
        """Each retrieval span sits under its own TOOL span under a task span."""
        settings = AgentLLMSettings.from_openai_compatible_env()
        if not settings.clients[0].api_key:
            pytest.skip("Agent LLM API key not configured")

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")

        store = build_graph_store("neo4j", tracer=tracer)
        await store.connect()
        try:
            engine = SearchEngine(
                graph_store=store,
                embedder=_FakeHashedWordEmbedder(),
                settings=RetrievalSettings(entity_top_k=10, chunk_top_k=10),
                graph_schema=GraphSchema(
                    name="agent_tracing",
                    version="1",
                    entities=[
                        EntityType(label=label, description="A corpus entity.")
                        for label in tiny_corpus.labels
                    ],
                    relations=[],
                ),
                tracer=tracer,
            )
            agent = build_agent(engine=engine, llm_settings=settings, tracer=tracer)
            await agent.ainvoke({"messages": [{"role": "user", "content": _PROMPT}]})
        finally:
            await store.close()
            provider.force_flush()

        spans = exporter.get_finished_spans()
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (_OUTPUT_DIR / "agent_tracing_span_tree.json").write_text(
            json.dumps(_span_tree(spans), indent=2)
        )
        by_id = {span.context.span_id: span for span in spans}

        tasks = [span for span in spans if _tool_name(span) == "task"]
        assert tasks, "the agent made no task call"
        task_ids = {task.context.span_id for task in tasks}

        # Each retrieval span's nearest TOOL ancestor is the search tool call
        # that made it, and that call sits under exactly one task span.
        owners: dict[int, set[int]] = {}
        for span in spans:
            if not span.name.startswith("agrag.retrieval."):
                continue
            ancestors = _ancestors(span, by_id)
            tool = next((a for a in ancestors if _is_tool(a)), None)
            assert tool is not None, f"{span.name} has no TOOL ancestor"
            assert _tool_name(tool) != "task", f"{span.name} skips its tool call"
            task = next(
                a for a in _ancestors(tool, by_id) if a.context.span_id in task_ids
            )
            owners.setdefault(task.context.span_id, set()).add(tool.context.span_id)
        assert owners, "the agent ran no retrieval"

        # Tool calls of different tasks are different spans.
        tool_sets = list(owners.values())
        for i, first in enumerate(tool_sets):
            for second in tool_sets[i + 1 :]:
                assert first.isdisjoint(second)

        searches = [
            step
            for step in read_trajectory(spans).steps
            if step.kind == "tool" and step.name != "task"
        ]
        assert searches
        assert {step.subagent for step in searches} == {"researcher"}
