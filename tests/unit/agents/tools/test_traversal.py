"""Tests for the entity-graph tool factories in agrag.agents.tools.traversal.

The SearchEngine is a Mock, so every assertion is about what the tool passed
downstream -- which entity it resolved, which SearchEngine method it called,
and with which arguments -- not about what a backend does with those
arguments. langchain_core is real here; only the engine and the ledger are
doubled.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agrag.agents.ledger import Ledger
from agrag.agents.tools.traversal import (
    _TRAVERSAL_WIDE_FANOUT,
    make_describe_entity_tool,
    make_find_related_entities_tool,
    make_list_relationship_types_tool,
    make_traverse_from_entity_tool,
)
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.retrieval.errors import ScopeDeniedError
from agrag.retrieval.filters import SearchFilters


def _result(name: str = "Acme", properties: dict | None = None) -> SearchResult:
    """Return one resolved entity result for a tool to work from."""
    return SearchResult(
        item=Entity(
            id=uuid4(),
            label="Organization",
            name=name,
            properties=properties or {},
        ),
        score=0.9,
        method="entity",
    )


def _neighbours(count: int) -> list[SearchResult]:
    """Return `count` neighbour results."""
    return [_result(name=f"Neighbour {index}") for index in range(count)]


def _engine(resolved: SearchResult | None) -> AsyncMock:
    """Return an engine mock that resolves to the given result."""
    engine = AsyncMock()
    engine.find_entity.return_value = resolved
    engine.traverse.return_value = []
    engine.list_relationship_types.return_value = []
    return engine


_TOOL_FACTORIES = {
    "list_relationship_types": (
        make_list_relationship_types_tool,
        {"entity": "Acme"},
    ),
    "find_related_entities": (
        make_find_related_entities_tool,
        {"entity": "Acme", "relation_type": "FOUNDED"},
    ),
    "describe_entity": (make_describe_entity_tool, {"entity": "Acme"}),
    "traverse_from_entity": (make_traverse_from_entity_tool, {"entity": "Acme"}),
}


class TestTraversal:
    """Tests scoped entity and relationship traversal tool calls."""

    @pytest.mark.parametrize("factory_name", list(_TOOL_FACTORIES))
    async def test_entity_not_found_short_circuits(self, factory_name: str) -> None:
        """An unresolved entity returns a plain message and does nothing else."""
        factory, arguments = _TOOL_FACTORIES[factory_name]
        engine = _engine(None)
        tool = factory(engine, Ledger())

        rendered = await tool.ainvoke({**arguments, "entity": "Nope"})

        assert rendered == (
            "Entity not found. Check the name, or search for it with "
            "look_up_entity first."
        )
        engine.find_entity.assert_awaited_once()
        engine.traverse.assert_not_awaited()
        engine.list_relationship_types.assert_not_awaited()

    async def test_list_relationship_types_denied_is_refused(self) -> None:
        """An out-of-scope relationship type returns an authorization refusal."""
        engine = _engine(_result())
        engine.list_relationship_types.side_effect = ScopeDeniedError("not permitted")
        tool = make_list_relationship_types_tool(
            engine, Ledger(), filters=SearchFilters(relation_types=["TREATS"])
        )

        rendered = await tool.ainvoke(
            {"entity": "Acme", "relation_type_filter": "FOUNDED"}
        )

        assert "outside this agent's permitted scope" in rendered

    async def test_entity_without_properties_says_so(self) -> None:
        """An entity with no properties renders a placeholder, not blank."""
        engine = _engine(_result())
        tool = make_describe_entity_tool(engine, Ledger())

        rendered = await tool.ainvoke({"entity": "Acme"})

        assert rendered.endswith("(no properties)")

    async def test_wide_fanout_falls_back_to_relationship_types(self) -> None:
        """Too many neighbours returns the relationship types instead."""
        engine = _engine(_result())
        engine.traverse.return_value = _neighbours(_TRAVERSAL_WIDE_FANOUT + 1)
        engine.list_relationship_types.return_value = ["MENTIONED_IN", "WORKS_FOR"]
        tool = make_traverse_from_entity_tool(engine, Ledger())

        rendered = await tool.ainvoke({"entity": "Acme"})

        engine.list_relationship_types.assert_awaited_once()
        assert "MENTIONED_IN, WORKS_FOR" in rendered
        assert "relation_type" in rendered
        assert "Neighbour 0" not in rendered

    async def test_within_threshold_renders_neighbours(self) -> None:
        """At or below the threshold, neighbours are returned."""
        engine = _engine(_result())
        engine.traverse.return_value = _neighbours(_TRAVERSAL_WIDE_FANOUT)
        tool = make_traverse_from_entity_tool(engine, Ledger())

        rendered = await tool.ainvoke({"entity": "Acme"})

        engine.list_relationship_types.assert_not_awaited()
        assert "[E1]" in rendered

    async def test_traverse_from_entity_denied_relation_type_is_refused(self) -> None:
        """A traversal the caller's scope refuses returns the refusal text."""
        engine = _engine(_result())
        engine.traverse.side_effect = ScopeDeniedError("FOUNDED not permitted")
        tool = make_traverse_from_entity_tool(
            engine, Ledger(), filters=SearchFilters(relation_types=["WORKS_FOR"])
        )

        rendered = await tool.ainvoke({"entity": "Acme", "relation_type": "FOUNDED"})

        assert "outside this agent's permitted scope" in rendered
