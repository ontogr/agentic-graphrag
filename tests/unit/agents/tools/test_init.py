"""Tests for make_tools in agrag.agents.tools.

Covers the assembled tool list, the caller-set base scope every tool starts
from (including that a tool argument can narrow it but never widen it or
cross it), and the import invariant that keeps ``agrag.agents.tools``
importable when the optional agents dependency is absent.

The SearchEngine is a Mock, so these assertions are about the filters the
tool layer passes downstream, not about what a backend does with them.
"""

import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock

from agrag.agents.ledger import Ledger
from agrag.agents.tools import make_tools
from agrag.retrieval.filters import SearchFilters


def _tool_named(tools: list, name: str):
    """Return the tool with the given name."""
    return next(tool for tool in tools if tool.name == name)


class TestMakeTools:
    """make_tools assembles the discovery and traversal tool set."""

    def test_returns_eleven_tools_unscoped(self) -> None:
        """Five discovery tools, four traversal tools, calculator, Cypher."""
        tools = make_tools(MagicMock(), Ledger())

        assert len(tools) == 11

    def test_returns_ten_tools_when_scoped(self) -> None:
        """A caller scope removes the unscoped-only Cypher tool."""
        tools = make_tools(
            MagicMock(), Ledger(), filters=SearchFilters(labels=["Drug"])
        )

        assert len(tools) == 10
        assert "query_graph_directly" not in {tool.name for tool in tools}

    def test_returns_ten_tools_for_an_empty_scope(self) -> None:
        """An empty SearchFilters is not a scope, so the Cypher tool stays."""
        tools = make_tools(MagicMock(), Ledger(), filters=SearchFilters())

        assert len(tools) == 11

    def test_tool_names(self) -> None:
        """The unscoped tool set is exactly the expected names."""
        tools = make_tools(MagicMock(), Ledger())

        assert {tool.name for tool in tools} == {
            "search_source_text",
            "look_up_entity",
            "explore_related",
            "answer_from_graph_structure",
            "answer_thematic_question",
            "list_relationship_types",
            "find_related_entities",
            "describe_entity",
            "traverse_from_entity",
            "compute_over_evidence",
            "query_graph_directly",
        }

    def test_tools_package_importable_without_langchain_installed(self) -> None:
        """Importing the package must not import langchain_core.

        ``agrag.agents.build`` imports this package at module scope, so the
        package -- and everything it imports at module scope -- has to stay
        importable when the optional agents dependency is missing.
        langchain_core is only reached when a tool factory is called, so this
        runs in a subprocess with langchain_core blocked from the start.
        """
        script = (
            "import sys\n"
            "sys.modules['langchain_core'] = None\n"
            "import agrag.agents.tools as tools\n"
            "assert callable(tools.make_tools)\n"
            "assert 'langchain_core.tools' not in sys.modules\n"
        )

        subprocess.run([sys.executable, "-c", script], check=True)  # noqa: S603


class TestBaseScopeEnforcement:
    """A caller-set scope bounds every tool call the model makes."""

    async def test_no_base_scope_leaves_the_tool_argument_as_the_scope(
        self,
    ) -> None:
        """Without a base scope, a tool argument is the whole scope."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = _tool_named(make_tools(engine, Ledger()), "look_up_entity")

        await tool.ainvoke({"query": "aspirin", "labels": ["Drug"]})

        _, kwargs = engine.search.await_args
        assert kwargs["filters"] == SearchFilters(labels=["Drug"])

    async def test_base_scope_alone_reaches_the_search(self) -> None:
        """A base scope applies even when the call names no filter."""
        engine = AsyncMock()
        engine.search.return_value = []
        base = SearchFilters(labels=["Drug"])
        tools = make_tools(engine, Ledger(), filters=base)
        search_tools = [
            tool
            for tool in tools
            if tool.name
            in {
                "search_source_text",
                "look_up_entity",
                "explore_related",
                "answer_from_graph_structure",
                "answer_thematic_question",
            }
        ]

        for tool in search_tools:
            engine.search.reset_mock()
            await tool.ainvoke({"query": "aspirin"})
            _, kwargs = engine.search.await_args
            assert kwargs["filters"] == base
            assert kwargs["filters"] is not base

    async def test_base_filters_and_tool_filters_are_intersected(self) -> None:
        """A narrower tool argument is intersected with the base scope."""
        engine = AsyncMock()
        engine.search.return_value = []
        base = SearchFilters(labels=["Drug", "Condition"])
        tool = _tool_named(make_tools(engine, Ledger(), filters=base), "look_up_entity")

        await tool.ainvoke({"query": "asthma", "labels": ["Condition", "Person"]})

        effective = engine.search.await_args.kwargs["filters"]
        assert effective.labels == ["Condition"]
        assert not set(effective.labels) - set(base.labels)

    async def test_request_outside_the_base_scope_is_refused(self) -> None:
        """A request for labels the caller did not permit searches nothing."""
        engine = AsyncMock()
        engine.search.return_value = []
        base = SearchFilters(labels=["Drug"])
        tool = _tool_named(make_tools(engine, Ledger(), filters=base), "look_up_entity")

        rendered = await tool.ainvoke({"query": "asthma", "labels": ["Condition"]})

        engine.search.assert_not_awaited()
        assert "outside this agent's permitted scope" in rendered

    async def test_base_scope_carries_through_with_a_surviving_intersection(
        self,
    ) -> None:
        """A permitted narrower request keeps the rest of the base scope."""
        engine = AsyncMock()
        engine.search.return_value = []
        base = SearchFilters(
            labels=["Drug", "Condition"],
            relation_types=["TREATS"],
            properties={"tenant_id": "tenant-a"},
        )
        tool = _tool_named(make_tools(engine, Ledger(), filters=base), "look_up_entity")

        await tool.ainvoke({"query": "asthma", "labels": ["Condition"]})

        effective = engine.search.await_args.kwargs["filters"]
        assert effective == SearchFilters(
            labels=["Condition"],
            relation_types=["TREATS"],
            properties={"tenant_id": "tenant-a"},
        )

    async def test_document_ids_intersect_with_the_base_scope(self) -> None:
        """A document the call asks for must be one the caller permitted."""
        engine = AsyncMock()
        engine.search.return_value = []
        base = SearchFilters(document_ids=["doc-1"])
        tool = _tool_named(
            make_tools(engine, Ledger(), filters=base), "search_source_text"
        )

        await tool.ainvoke({"query": "aspirin", "document_ids": ["doc-1", "doc-2"]})

        effective = engine.search.await_args.kwargs["filters"]
        assert effective.document_ids == ["doc-1"]

    async def test_cross_document_request_is_refused(self) -> None:
        """A call for an out-of-scope document retrieves nothing."""
        engine = AsyncMock()
        engine.search.return_value = []
        base = SearchFilters(document_ids=["doc-1"])
        tool = _tool_named(
            make_tools(engine, Ledger(), filters=base), "search_source_text"
        )

        rendered = await tool.ainvoke({"query": "aspirin", "document_ids": ["doc-2"]})

        engine.search.assert_not_awaited()
        assert "outside this agent's permitted scope" in rendered

    async def test_explore_related_refuses_a_partly_out_of_scope_request(self) -> None:
        """Each filter dimension is checked, not just the first one given."""
        engine = AsyncMock()
        engine.search.return_value = []
        base = SearchFilters(labels=["Drug"], document_ids=["doc-1"])
        tool = _tool_named(
            make_tools(engine, Ledger(), filters=base), "explore_related"
        )

        rendered = await tool.ainvoke(
            {"query": "aspirin", "labels": ["Drug"], "document_ids": ["doc-2"]}
        )

        engine.search.assert_not_awaited()
        assert "outside this agent's permitted scope" in rendered
