"""Tests for the tool span bridge across the ten engine-calling tools.

Each tool is invoked with ``config={"callbacks": run_callbacks(tracer)}`` over
a stub engine whose methods open a span: that span must have the tool's own
``TOOL`` span as its parent, and ``callbacks`` must stay out of the tool
schema the model sees. Parallel calls nest under their own tool spans and a
span opened after the tool call is the caller's child again, so the bridge
leaks nothing.
"""

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.agents.tools import search as search_tools
from agrag.agents.tools import traversal as traversal_tools
from agrag.agents.tools.aggregate import compute_over_evidence
from agrag.agents.tracing import run_callbacks
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult


TOOLS = [
    (search_tools.make_search_source_text_tool, {"query": "q"}),
    (search_tools.make_look_up_entity_tool, {"query": "q"}),
    (search_tools.make_explore_related_tool, {"query": "q"}),
    (search_tools.make_answer_from_graph_structure_tool, {"query": "q"}),
    (search_tools.make_answer_thematic_question_tool, {"query": "q"}),
    (search_tools.make_query_graph_directly_tool, {"query": "q"}),
    (traversal_tools.make_list_relationship_types_tool, {"entity": "Acme"}),
    (
        traversal_tools.make_find_related_entities_tool,
        {"entity": "Acme", "relation_type": "TREATS"},
    ),
    (traversal_tools.make_describe_entity_tool, {"entity": "Acme"}),
    (traversal_tools.make_traverse_from_entity_tool, {"entity": "Acme"}),
]


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a provider and exporter pair backed by one in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _stub_engine() -> Any:
    """Return a stub engine whose engine calls open a probe span each."""

    class ProbeEngine:
        """Stub engine that opens one span per retrieval call."""

        def __init__(self, tracer) -> None:
            """Bind the tracer the probe spans open with."""
            self.tracer = tracer
            self.calls: list[str] = []

        async def search(self, query, recipe, *, filters=None):
            """Open a probe span so the bridge has something to nest."""
            self.calls.append("search")
            with self.tracer.start_as_current_span("agrag.probe.search"):
                return []

        async def find_entity(self, name, *, filters=None):
            """Open a probe span so the bridge has something to nest."""
            self.calls.append("find_entity")
            with self.tracer.start_as_current_span("agrag.probe.find_entity"):
                return SearchResult(
                    item=Entity(id=_entity_id(), label="Person", name=name),
                    score=1.0,
                    method="entity",
                )

        async def traverse(self, seed, **kwargs):
            """Open a probe span so the bridge has something to nest."""
            self.calls.append("traverse")
            with self.tracer.start_as_current_span("agrag.probe.traverse"):
                return []

        async def list_relationship_types(self, seed, **kwargs):
            """Open a probe span so the bridge has something to nest."""
            self.calls.append("list_relationship_types")
            with self.tracer.start_as_current_span("agrag.probe.list_types"):
                return ["TREATS"]

    return ProbeEngine(None)


_entity_counter = {"n": 0}


def _entity_id():
    """Return a distinct id per call."""
    return uuid4()


class _Ledger:
    """A minimal ledger stub for render_results."""

    def render(self, result: SearchResult) -> str:
        """Render one result as a cited line."""
        return f"[c1] {result.item.name}"

    def cite(self, result: SearchResult) -> str:
        """Return a citation key."""
        return "c1"


@pytest.fixture(autouse=True)
def _reset_entity_counter():
    """Keep ids unique across tests."""
    _entity_counter["n"] = 0
    yield


class TestToolBridge:
    """Every engine-calling tool bridges into its own TOOL span."""

    @pytest.mark.parametrize(("factory", "args"), TOOLS)
    async def test_engine_spans_nest_under_the_tool_span(self, factory, args) -> None:
        """The stub's span has the tool's TOOL span as its parent."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        callbacks = run_callbacks(tracer)
        engine = _stub_engine()
        engine.tracer = tracer
        tool = factory(engine, _Ledger())

        await tool.ainvoke(args, config={"callbacks": callbacks})

        spans = exporter.get_finished_spans()
        tool_name = tool.name
        tool_spans = [
            span
            for span in spans
            if span.attributes.get("openinference.span.kind") == "TOOL"
            and span.name == tool_name
        ]
        assert len(tool_spans) == 1
        probes = [span for span in spans if span.name.startswith("agrag.probe.")]
        assert probes, f"no probe span exported for {tool_name}"
        for probe in probes:
            assert probe.parent is not None
            assert probe.parent.span_id == tool_spans[0].context.span_id

    @pytest.mark.parametrize(("factory", "args"), TOOLS)
    async def test_callbacks_is_not_in_the_schema(self, factory, args) -> None:
        """The model-visible tool schema omits the callbacks argument."""
        engine = _stub_engine()
        tool = factory(engine, _Ledger())
        schema_properties = tool.args_schema.model_json_schema()["properties"]
        assert "callbacks" not in schema_properties

    @pytest.mark.parametrize(("factory", "args"), TOOLS)
    async def test_no_callbacks_still_returns_text(self, factory, args) -> None:
        """Without a tracer the tool works and no TOOL span bridges."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        engine = _stub_engine()
        engine.tracer = tracer
        tool = factory(engine, _Ledger())

        text = await tool.ainvoke(args, config={"callbacks": []})

        assert isinstance(text, str)
        tool_spans = [
            span
            for span in exporter.get_finished_spans()
            if span.attributes.get("openinference.span.kind") == "TOOL"
        ]
        assert tool_spans == []
        # The stub's probe spans still export under the caller's context;
        # nothing nested under a TOOL span because there was none.
        for span in exporter.get_finished_spans():
            if span.name.startswith("agrag.probe."):
                assert span.parent is None or span.parent.span_id not in {
                    s.context.span_id for s in tool_spans
                }

    async def test_two_parallel_calls_nest_under_their_own_tool_spans(self) -> None:
        """Two parallel calls of one tool each nest under their own span."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        callbacks = run_callbacks(tracer)
        engine = _stub_engine()
        engine.tracer = tracer
        tool = search_tools.make_explore_related_tool(engine, _Ledger())

        await asyncio.gather(
            tool.ainvoke({"query": "a"}, config={"callbacks": callbacks}),
            tool.ainvoke({"query": "b"}, config={"callbacks": callbacks}),
        )

        spans = exporter.get_finished_spans()
        tool_spans = [
            span
            for span in spans
            if span.name == "explore_related"
            and span.attributes.get("openinference.span.kind") == "TOOL"
        ]
        probes = [span for span in spans if span.name == "agrag.probe.search"]
        assert len(tool_spans) == 2
        assert len(probes) == 2
        tool_ids = {span.context.span_id for span in tool_spans}
        children: dict[int, int] = {}
        for probe in probes:
            assert probe.parent is not None
            assert probe.parent.span_id in tool_ids
            children[probe.parent.span_id] = children.get(probe.parent.span_id, 0) + 1
        assert set(children.values()) == {1}

    async def test_a_span_after_the_tool_is_the_callers_child(self) -> None:
        """The bridge does not leak the tool span past the tool call."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        callbacks = run_callbacks(tracer)
        engine = _stub_engine()
        engine.tracer = tracer
        tool = search_tools.make_look_up_entity_tool(engine, _Ledger())

        with tracer.start_as_current_span("caller"):
            await tool.ainvoke({"query": "q"}, config={"callbacks": callbacks})
            with tracer.start_as_current_span("after"):
                pass

        spans = exporter.get_finished_spans()
        caller_span = next(s for s in spans if s.name == "caller")
        after_span = next(s for s in spans if s.name == "after")
        assert after_span.parent is not None
        assert after_span.parent.span_id == caller_span.context.span_id

    async def test_a_raising_tool_records_its_exception_once(self) -> None:
        """The bridge adds no second exception event to the TOOL span."""

        class ExplodingEngine:
            """Stub engine whose search always raises."""

            async def search(self, query, recipe, *, filters=None):
                """Raise inside the bridged body."""
                raise RuntimeError("search failed")

        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        callbacks = run_callbacks(tracer)
        tool = search_tools.make_look_up_entity_tool(ExplodingEngine(), _Ledger())

        with pytest.raises(RuntimeError, match="search failed"):
            await tool.ainvoke({"query": "q"}, config={"callbacks": callbacks})

        tool_spans = [
            span
            for span in exporter.get_finished_spans()
            if span.name == "look_up_entity"
            and span.attributes.get("openinference.span.kind") == "TOOL"
        ]
        assert len(tool_spans) == 1
        exceptions = [e for e in tool_spans[0].events if e.name == "exception"]
        assert len(exceptions) == 1


class TestComputeOverEvidenceUnchanged:
    """compute_over_evidence takes no callbacks (it calls no engine)."""

    def test_schema_has_no_callbacks(self) -> None:
        """The aggregate tool's schema never grew a callbacks argument."""
        schema_properties = compute_over_evidence.args_schema.model_json_schema()[
            "properties"
        ]
        assert "callbacks" not in schema_properties
