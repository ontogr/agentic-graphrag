"""Tests for the discovery tool factories in agrag.agents.tools.search.

Every assertion targets the arguments the tool passed to a Mock
SearchEngine.search -- the Recipe and the SearchFilters -- so each test
proves what the tool actually searched with, not only that it returned text.
The presets are shared module-level objects, so the limit and min_score tests
also assert the preset itself was left unmutated. langchain_core is real
here; only the engine and the ledger are doubled.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agrag.agents.ledger import Ledger
from agrag.agents.tools.search import (
    make_answer_from_graph_structure_tool,
    make_answer_thematic_question_tool,
    make_explore_related_tool,
    make_look_up_entity_tool,
    make_query_graph_directly_tool,
    make_search_source_text_tool,
)
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.recipes import (
    CHUNK,
    ENTITY,
    HYBRID,
    HYBRID_RERANKED,
    TEXT2CYPHER,
    THEMATIC,
)


def _entity() -> SearchResult:
    """Return one entity result for a tool to render."""
    return SearchResult(
        item=Entity(id=uuid4(), label="Drug", name="Aspirin"),
        score=0.9,
        method="entity",
    )


class TestSearchSourceTextTool:
    """search_source_text searches passages, narrowed per call."""

    async def test_default_limit_passes_the_chunk_preset(self) -> None:
        """A call with no arguments searches with the CHUNK preset itself."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_search_source_text_tool(engine, Ledger())

        await tool.ainvoke({"query": "aspirin"})

        engine.search.assert_awaited_once_with("aspirin", CHUNK, filters=None)

    async def test_limit_reaches_the_recipe_without_mutating_the_preset(self) -> None:
        """A caller-supplied limit overrides only this call's recipe."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_search_source_text_tool(engine, Ledger())

        await tool.ainvoke({"query": "aspirin", "limit": 3})

        recipe = engine.search.await_args.args[1]
        assert recipe.limit == 3
        assert CHUNK.limit == 10

    async def test_document_ids_become_a_filter(self) -> None:
        """A document_ids argument reaches the search as a filter."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_search_source_text_tool(engine, Ledger())

        await tool.ainvoke({"query": "aspirin", "document_ids": ["doc-1"]})

        engine.search.assert_awaited_once_with(
            "aspirin", CHUNK, filters=SearchFilters(document_ids=["doc-1"])
        )

    async def test_renders_cited_passages(self) -> None:
        """Results come back as cited evidence."""
        engine = AsyncMock()
        engine.search.return_value = [_entity()]
        tool = make_search_source_text_tool(engine, Ledger())

        rendered = await tool.ainvoke({"query": "aspirin"})

        assert "[E1]" in rendered
        assert "Aspirin" in rendered

    async def test_no_results_message(self) -> None:
        """An empty result set is reported rather than rendered as blank."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_search_source_text_tool(engine, Ledger())

        assert await tool.ainvoke({"query": "aspirin"}) == "No results found."


class TestLookUpEntityTool:
    """look_up_entity searches entities, narrowed per call."""

    async def test_default_call_uses_the_entity_preset(self) -> None:
        """A call with no arguments searches with the ENTITY preset."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_look_up_entity_tool(engine, Ledger())

        await tool.ainvoke({"query": "aspirin"})

        engine.search.assert_awaited_once_with("aspirin", ENTITY, filters=None)

    async def test_labels_become_a_filter(self) -> None:
        """A labels argument reaches the search as a label filter."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_look_up_entity_tool(engine, Ledger())

        await tool.ainvoke({"query": "aspirin", "labels": ["Drug"]})

        engine.search.assert_awaited_once_with(
            "aspirin", ENTITY, filters=SearchFilters(labels=["Drug"])
        )

    async def test_limit_reaches_the_recipe(self) -> None:
        """A caller-supplied limit overrides only this call's recipe."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_look_up_entity_tool(engine, Ledger())

        await tool.ainvoke({"query": "aspirin", "limit": 4})

        assert engine.search.await_args.args[1].limit == 4
        assert ENTITY.limit == 10


class TestExploreRelatedTool:
    """explore_related fans out to entities and passages."""

    async def test_default_call_uses_the_hybrid_preset(self) -> None:
        """A call with no arguments searches with the HYBRID preset."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_explore_related_tool(engine, Ledger())

        await tool.ainvoke({"query": "aspirin"})

        engine.search.assert_awaited_once_with("aspirin", HYBRID, filters=None)

    async def test_both_filter_dimensions_reach_the_search(self) -> None:
        """Labels and document ids are both applied when both are given."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_explore_related_tool(engine, Ledger())

        await tool.ainvoke(
            {"query": "aspirin", "labels": ["Drug"], "document_ids": ["doc-1"]}
        )

        engine.search.assert_awaited_once_with(
            "aspirin",
            HYBRID,
            filters=SearchFilters(labels=["Drug"], document_ids=["doc-1"]),
        )


class TestAnswerFromGraphStructureTool:
    """answer_from_graph_structure reranks, with an optional score floor."""

    async def test_no_min_score_passes_the_preset_unmodified(self) -> None:
        """Omitting min_score leaves the shared preset untouched."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_answer_from_graph_structure_tool(engine, Ledger())

        await tool.ainvoke({"query": "does aspirin help?"})

        assert engine.search.await_args.args[1] is HYBRID_RERANKED
        assert engine.search.await_args.kwargs["filters"] is None

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


class TestAnswerThematicQuestionTool:
    """answer_thematic_question searches community summaries."""

    async def test_default_call_uses_the_thematic_preset(self) -> None:
        """A call with no arguments searches with the THEMATIC preset."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_answer_thematic_question_tool(engine, Ledger())

        await tool.ainvoke({"query": "what is this graph about?"})

        engine.search.assert_awaited_once_with(
            "what is this graph about?", THEMATIC, filters=None
        )

    async def test_limit_reaches_the_recipe(self) -> None:
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


class TestQueryGraphDirectlyTool:
    """query_graph_directly runs one generated read-only Cypher query."""

    async def test_uses_the_text2cypher_recipe(self) -> None:
        """A call searches with the TEXT2CYPHER preset, unmodified."""
        engine = AsyncMock()
        engine.search.return_value = []
        tool = make_query_graph_directly_tool(engine, Ledger())

        await tool.ainvoke({"query": "how many drugs treat headaches?"})

        engine.search.assert_awaited_once_with(
            "how many drugs treat headaches?", TEXT2CYPHER, filters=None
        )

    def test_exposes_query_only(self) -> None:
        """The tool's schema offers no limit or filter parameters."""
        engine = AsyncMock()
        tool = make_query_graph_directly_tool(engine, Ledger())

        assert set(tool.args_schema.model_fields) == {"query"}
