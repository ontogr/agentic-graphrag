"""Tests for agent tools."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from agrag.agents.ledger import Ledger
from agrag.agents.tools import make_tools
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult


class TestMakeTools:
    """make_tools builds the agent's tool set."""

    def test_returns_five_tools(self) -> None:
        """make_tools returns 5 tools."""
        engine = MagicMock()
        ledger = Ledger()
        tools = make_tools(engine, ledger)
        assert len(tools) == 5

    def test_tool_names(self) -> None:
        """Tools have the expected names."""
        engine = MagicMock()
        ledger = Ledger()
        tools = make_tools(engine, ledger)
        names = {t.name for t in tools}
        assert "search_source_text" in names
        assert "look_up_entity" in names
        assert "find_connection" in names
        assert "explore_related" in names
        assert "answer_from_graph_structure" in names

    async def test_tool_run_calls_engine(self) -> None:
        """A tool's ainvoke() calls SearchEngine.search()."""
        engine = AsyncMock()
        engine.search.return_value = [
            SearchResult(
                item=Entity(id=uuid4(), label="Person", name="Alice"),
                score=0.9,
                method="entity",
            )
        ]
        ledger = Ledger()
        tools = make_tools(engine, ledger)
        result = await tools[0].ainvoke({"query": "test query"})
        engine.search.assert_called_once()
        assert "Alice" in result
