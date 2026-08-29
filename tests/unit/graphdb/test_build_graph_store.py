"""Tests for build_graph_store and the backend lookup table."""

import typing
from typing import get_args, get_origin

from agrag.graphdb import _GRAPH_STORE_FACTORIES, build_graph_store
from agrag.graphdb.neo4j import Neo4jGraphStore
from agrag.graphdb.settings import Neo4jSettings


class TestBuildGraphStore:
    """build_graph_store resolves a name or passes an instance through."""

    def test_build_neo4j_from_name(self) -> None:
        """The "neo4j" name builds a Neo4jGraphStore."""
        store = build_graph_store("neo4j")
        assert isinstance(store, Neo4jGraphStore)
        assert isinstance(store._settings, Neo4jSettings)

    def test_passthrough_instance(self) -> None:
        """An existing GraphStore is returned unchanged."""
        store = Neo4jGraphStore(settings=Neo4jSettings())
        assert build_graph_store(store) is store


class TestBackendTable:
    """Every Literal backend name must have a factory entry."""

    def test_every_literal_value_has_a_table_entry(self) -> None:
        """The Literal and the factory table stay in sync."""
        annotation = build_graph_store.__annotations__["value"]
        union_args = get_args(annotation)
        literal = next(a for a in union_args if get_origin(a) is typing.Literal)
        for name in get_args(literal):
            assert name in _GRAPH_STORE_FACTORIES
