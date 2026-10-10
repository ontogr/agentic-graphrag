"""Tests for the discovery tool factories in agrag.agents.tools.search.

Every assertion targets the arguments the tool passed to a Mock
SearchEngine.search -- the Recipe and the SearchFilters -- so each test
proves what the tool actually searched with, not only that it returned text.
The presets are shared module-level objects, so the limit and min_score tests
also assert the preset itself was left unmutated. langchain_core is real
here; only the engine and the ledger are doubled.
"""

from unittest.mock import AsyncMock

import pytest

from agrag.agents.ledger import Ledger
from agrag.agents.tools.search import (
    MAX_TOOL_LIMIT,
    make_answer_from_graph_structure_tool,
    make_answer_thematic_question_tool,
    make_look_up_entity_tool,
    make_query_graph_directly_tool,
    make_search_source_text_tool,
)
from agrag.retrieval.errors import AllRetrievalMethodsFailedError
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.recipes import (
    CHUNK,
    HYBRID_RERANKED,
    THEMATIC,
)


class TestSearch:
    """Tests scoped discovery tool calls and their rendered evidence."""

    async def test_limit_reaches_the_recipe_without_mutating_the_preset(self) -> None:
        """A caller-supplied limit overrides only this call's recipe."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_search_source_text_tool(engine, Ledger())

        await tool.ainvoke({"query": "aspirin", "limit": 3})

        recipe = engine.search.await_args.args[1]
        assert recipe.limit == 3
        assert CHUNK.limit == 10

    async def test_limit_above_shared_bound_is_rejected(self) -> None:
        """Discovery tools reject limits that could flood model context."""
        engine = AsyncMock()
        tool = make_look_up_entity_tool(engine, Ledger())

        with pytest.raises(ValueError, match="limit must be between"):
            await tool.ainvoke({"query": "aspirin", "limit": MAX_TOOL_LIMIT + 1})
        engine.search.assert_not_awaited()

    async def test_base_scope_intersects_requested_labels(self) -> None:
        """An entity search cannot widen its caller's label scope."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_look_up_entity_tool(
            engine, Ledger(), filters=SearchFilters(labels=["Drug", "Condition"])
        )

        await tool.ainvoke({"query": "aspirin", "labels": ["Condition", "Person"]})

        assert engine.search.await_args.kwargs["filters"].labels == ["Condition"]

    async def test_min_score_overrides_only_this_call(self) -> None:
        """A caller-supplied min_score reaches the recipe, not the preset."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_answer_from_graph_structure_tool(engine, Ledger())

        await tool.ainvoke({"query": "does aspirin help?", "min_score": 0.5})

        assert engine.search.await_args.args[1].min_score == 0.5
        assert HYBRID_RERANKED.min_score is None

    async def test_limit_and_min_score_combine(self) -> None:
        """Both overrides land on the same per-call recipe."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_answer_from_graph_structure_tool(engine, Ledger())

        await tool.ainvoke(
            {"query": "does aspirin help?", "limit": 2, "min_score": 0.1}
        )

        recipe = engine.search.await_args.args[1]
        assert recipe.limit == 2
        assert recipe.min_score == pytest.approx(0.1)
        assert HYBRID_RERANKED.limit == 10

    async def test_thematic_limit_reaches_the_recipe(self) -> None:
        """A caller-supplied limit overrides only this call's recipe."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_answer_thematic_question_tool(engine, Ledger())

        await tool.ainvoke({"query": "what is this graph about?", "limit": 2})

        assert engine.search.await_args.args[1].limit == 2
        assert THEMATIC.limit == 5

    def test_exposes_limit_only_no_filter_dimension(self) -> None:
        """The tool's schema offers no label or document filter."""
        engine = AsyncMock()
        tool = make_answer_thematic_question_tool(engine, Ledger())

        assert set(tool.args_schema.model_fields) == {"query", "limit"}

    async def test_returns_an_error_message_when_the_query_fails(self) -> None:
        """A failed generated query is an error message, not "no results"."""
        engine = AsyncMock()
        engine.search.side_effect = AllRetrievalMethodsFailedError(
            {"text2cypher": RuntimeError("llm down")}
        )
        tool = make_query_graph_directly_tool(engine, Ledger())

        rendered = await tool.ainvoke({"query": "how many people?"})

        assert rendered.startswith("Error:")
        assert "No results" not in rendered

    def test_exposes_query_only(self) -> None:
        """The tool's schema offers no limit or filter parameters."""
        engine = AsyncMock()
        tool = make_query_graph_directly_tool(engine, Ledger())

        assert set(tool.args_schema.model_fields) == {"query"}
