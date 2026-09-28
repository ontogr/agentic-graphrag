"""Tests for build_graph_store and the backend lookup table.

Covers passthrough of an already-constructed GraphStore instance,
and a reflection check that every ``Literal`` backend name in
``build_graph_store``'s type annotation has a matching entry in
``_GRAPH_STORE_FACTORIES``.
"""

import typing
from typing import get_args, get_origin

import pytest
from opentelemetry import trace

from agrag.graphdb import _GRAPH_STORE_FACTORIES, build_graph_store
from agrag.graphdb.neo4j import Neo4jGraphStore
from agrag.graphdb.settings import Neo4jSettings


class TestBuildGraphStore:
    """build_graph_store resolves a name or passes an instance through."""

    def test_passthrough_instance(self) -> None:
        """An existing GraphStore is returned unchanged."""
        store = Neo4jGraphStore(settings=Neo4jSettings())
        assert build_graph_store(store) is store

    def test_tracer_with_instance_raises(self) -> None:
        """Passing tracer with an already-built store raises ValueError."""
        store = Neo4jGraphStore(settings=Neo4jSettings())
        with pytest.raises(ValueError, match="tracer has no effect"):
            build_graph_store(store, tracer=trace.get_tracer("test"))


class TestBackendTable:
    """Every Literal backend name must have a factory entry."""

    def test_every_literal_value_has_a_table_entry(self) -> None:
        """The Literal and the factory table stay in sync."""
        annotation = build_graph_store.__annotations__["value"]
        union_args = get_args(annotation)
        literal = next(a for a in union_args if get_origin(a) is typing.Literal)
        for name in get_args(literal):
            assert name in _GRAPH_STORE_FACTORIES
