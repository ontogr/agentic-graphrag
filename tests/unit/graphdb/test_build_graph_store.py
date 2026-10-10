"""Tests for build_graph_store.

Covers passthrough of an already-constructed GraphStore instance, and
rejecting a tracer passed alongside one.
"""

import pytest
from opentelemetry import trace

from agrag.graphdb import build_graph_store
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
