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

    @pytest.mark.parametrize("factory_name", list(_TOOL_FACTORIES))
    async def test_base_filters_reach_find_entity(self, factory_name: str) -> None:
        """The caller's scope bounds entity resolution for every tool."""
        factory, arguments = _TOOL_FACTORIES[factory_name]
        resolved = _result()
        engine = _engine(resolved)
        scope = SearchFilters(properties={"tenant_id": "tenant-a"})
        tool = factory(engine, Ledger(), filters=scope)

        await tool.ainvoke(arguments)

        engine.find_entity.assert_awaited_once_with("Acme", filters=scope)

    async def test_renders_distinct_types(self) -> None:
        """The rendered text names every distinct type, sorted."""
        engine = _engine(_result())
        engine.list_relationship_types.return_value = ["WORKS_FOR", "FOUNDED"]
        tool = make_list_relationship_types_tool(engine, Ledger())

        rendered = await tool.ainvoke({"entity": "Acme"})

        assert "FOUNDED, WORKS_FOR" in rendered
        assert "Acme" in rendered

    async def test_filter_reaches_the_engine(self) -> None:
        """relation_type_filter reaches list_relationship_types."""
        resolved = _result()
        engine = _engine(resolved)
        tool = make_list_relationship_types_tool(engine, Ledger())

        await tool.ainvoke({"entity": "Acme", "relation_type_filter": "TREATS"})

        engine.list_relationship_types.assert_awaited_once_with(
            resolved, relation_type_filter="TREATS", filters=None
        )

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

    async def test_no_types_message(self) -> None:
        """An entity with no attached relationships says so."""
        engine = _engine(_result())
        engine.list_relationship_types.return_value = []
        tool = make_list_relationship_types_tool(engine, Ledger())

        rendered = await tool.ainvoke({"entity": "Acme"})

        assert rendered == "[E1] Entity: Acme (Organization)\nNo relationships found."

    async def test_relation_type_and_direction_reach_traverse(self) -> None:
        """The named relationship and direction reach engine.traverse."""
        resolved = _result()
        engine = _engine(resolved)
        tool = make_find_related_entities_tool(engine, Ledger())

        await tool.ainvoke(
            {"entity": "Acme", "relation_type": "FOUNDED", "direction": "outgoing"}
        )

        engine.traverse.assert_awaited_once_with(
            resolved,
            relation_type="FOUNDED",
            direction="outgoing",
            community_expand=False,
            filters=None,
        )

    @pytest.mark.parametrize("direction", ["outgoing", "incoming", "both"])
    async def test_direction_reaches_traverse(self, direction: str) -> None:
        """Each direction value reaches engine.traverse unchanged."""
        engine = _engine(_result())
        tool = make_find_related_entities_tool(engine, Ledger())

        await tool.ainvoke(
            {"entity": "Acme", "relation_type": "FOUNDED", "direction": direction}
        )

        assert engine.traverse.await_args.kwargs["direction"] == direction

    async def test_community_expand_reaches_traverse(self) -> None:
        """community_expand reaches engine.traverse."""
        engine = _engine(_result())
        tool = make_find_related_entities_tool(engine, Ledger())

        await tool.ainvoke(
            {"entity": "Acme", "relation_type": "FOUNDED", "community_expand": True}
        )

        assert engine.traverse.await_args.kwargs["community_expand"] is True

    async def test_find_related_entities_base_filters_reach_traverse(self) -> None:
        """The caller's scope bounds the traversal, not only the resolution."""
        resolved = _result()
        engine = _engine(resolved)
        scope = SearchFilters(properties={"tenant_id": "tenant-a"})
        tool = make_find_related_entities_tool(engine, Ledger(), filters=scope)

        await tool.ainvoke({"entity": "Acme", "relation_type": "FOUNDED"})

        engine.find_entity.assert_awaited_once_with("Acme", filters=scope)
        assert engine.traverse.await_args.kwargs["filters"] is scope

    async def test_renders_neighbours_as_cited_evidence(self) -> None:
        """Neighbours come back through the ledger."""
        engine = _engine(_result())
        engine.traverse.return_value = _neighbours(2)
        tool = make_find_related_entities_tool(engine, Ledger())

        rendered = await tool.ainvoke({"entity": "Acme", "relation_type": "FOUNDED"})

        assert "[E1]" in rendered
        assert "[E2]" in rendered

    async def test_find_related_entities_denied_relation_type_is_refused(self) -> None:
        """A traversal the caller's scope refuses returns the refusal text."""
        engine = _engine(_result())
        engine.traverse.side_effect = ScopeDeniedError("FOUNDED not permitted")
        tool = make_find_related_entities_tool(
            engine, Ledger(), filters=SearchFilters(relation_types=["WORKS_FOR"])
        )

        rendered = await tool.ainvoke({"entity": "Acme", "relation_type": "FOUNDED"})

        assert "outside this agent's permitted scope" in rendered

    async def test_renders_every_property(self) -> None:
        """Every property key and value appears, not just a citation line."""
        engine = _engine(
            _result(
                properties={
                    "description": "A maker of things.",
                    "founded_year": 1994,
                    "hq": "Springfield",
                }
            )
        )
        ledger = Ledger()
        tool = make_describe_entity_tool(engine, ledger)

        rendered = await tool.ainvoke({"entity": "Acme"})

        assert "[E1]" in rendered
        assert "Acme (Organization)" in rendered
        assert "- description: A maker of things." in rendered
        assert "- founded_year: 1994" in rendered
        assert "- hq: Springfield" in rendered

    async def test_entity_without_properties_says_so(self) -> None:
        """An entity with no properties renders a placeholder, not blank."""
        engine = _engine(_result())
        tool = make_describe_entity_tool(engine, Ledger())

        rendered = await tool.ainvoke({"entity": "Acme"})

        assert rendered.endswith("(no properties)")

    async def test_never_traverses(self) -> None:
        """Describing an entity touches no relationships."""
        engine = _engine(_result())
        tool = make_describe_entity_tool(engine, Ledger())

        await tool.ainvoke({"entity": "Acme"})

        engine.traverse.assert_not_awaited()
        engine.list_relationship_types.assert_not_awaited()

    async def test_relation_type_given_skips_fanout_check(self) -> None:
        """A named relationship traverses once, without listing types first."""
        resolved = _result()
        engine = _engine(resolved)
        engine.traverse.return_value = _neighbours(_TRAVERSAL_WIDE_FANOUT + 10)
        tool = make_traverse_from_entity_tool(engine, Ledger())

        await tool.ainvoke({"entity": "Acme", "relation_type": "FOUNDED", "depth": 2})

        assert engine.traverse.await_count == 1
        kwargs = engine.traverse.await_args.kwargs
        assert kwargs["relation_type"] == "FOUNDED"
        assert kwargs["depth"] == 2
        engine.list_relationship_types.assert_not_awaited()

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

    async def test_wide_fanout_requests_one_past_the_threshold(self) -> None:
        """The probe asks for just enough to detect a wide fan-out."""
        engine = _engine(_result())
        tool = make_traverse_from_entity_tool(engine, Ledger())

        await tool.ainvoke({"entity": "Acme"})

        assert engine.traverse.await_args.kwargs["limit"] == _TRAVERSAL_WIDE_FANOUT + 1

    async def test_within_threshold_renders_neighbours(self) -> None:
        """At or below the threshold, neighbours are returned."""
        engine = _engine(_result())
        engine.traverse.return_value = _neighbours(_TRAVERSAL_WIDE_FANOUT)
        tool = make_traverse_from_entity_tool(engine, Ledger())

        rendered = await tool.ainvoke({"entity": "Acme"})

        engine.list_relationship_types.assert_not_awaited()
        assert "[E1]" in rendered

    async def test_traverse_from_entity_base_filters_reach_traverse(self) -> None:
        """The caller's scope bounds this traversal too."""
        resolved = _result()
        engine = _engine(resolved)
        scope = SearchFilters(properties={"tenant_id": "tenant-a"})
        tool = make_traverse_from_entity_tool(engine, Ledger(), filters=scope)

        await tool.ainvoke({"entity": "Acme", "relation_type": "FOUNDED"})

        engine.find_entity.assert_awaited_once_with("Acme", filters=scope)
        assert engine.traverse.await_args.kwargs["filters"] is scope

    async def test_traverse_from_entity_denied_relation_type_is_refused(self) -> None:
        """A traversal the caller's scope refuses returns the refusal text."""
        engine = _engine(_result())
        engine.traverse.side_effect = ScopeDeniedError("FOUNDED not permitted")
        tool = make_traverse_from_entity_tool(
            engine, Ledger(), filters=SearchFilters(relation_types=["WORKS_FOR"])
        )

        rendered = await tool.ainvoke({"entity": "Acme", "relation_type": "FOUNDED"})

        assert "outside this agent's permitted scope" in rendered
