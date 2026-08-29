"""Tests for the Cypher schema builders."""

import pytest

from agrag.common.data_models.vector_record import Distance
from agrag.cypher.schema import (
    node_id_constraint_query,
    plain_index_query,
    vector_index_name,
    vector_index_query,
    vector_search_query,
)


class TestNodeConstraint:
    """node_id_constraint_query builds a uniqueness constraint on id."""

    def test_builds_unique_constraint(self) -> None:
        """A uniqueness constraint on id is created if absent."""
        q = node_id_constraint_query("Chunk")
        assert "CREATE CONSTRAINT Chunk_id_unique IF NOT EXISTS" in q
        assert "REQUIRE n.id IS UNIQUE" in q


class TestPlainIndex:
    """plain_index_query builds a range index on id."""

    def test_builds_range_index(self) -> None:
        """A range index on id is created if absent."""
        q = plain_index_query("Chunk")
        assert "CREATE INDEX Chunk_id_index IF NOT EXISTS" in q
        assert "ON (n.id)" in q


class TestVectorIndexName:
    """vector_index_name derives a deterministic name from label and property."""

    def test_deterministic(self) -> None:
        """The index name is the label, property, and a fixed suffix."""
        assert vector_index_name("Chunk", "embedding") == "Chunk_embedding_vector"


class TestVectorIndexQuery:
    """vector_index_query maps Distance to Neo4j similarity functions."""

    def test_cosine(self) -> None:
        """Cosine maps to Neo4j's 'cosine' similarity function."""
        q = vector_index_query("Chunk", "embedding", 4, Distance.COSINE)
        assert "CREATE VECTOR INDEX Chunk_embedding_vector IF NOT EXISTS" in q
        assert "FOR (n:Chunk) ON (n.embedding)" in q
        assert "`vector.similarity_function`: 'cosine'" in q
        assert "`vector.dimensions`: 4" in q

    def test_euclid(self) -> None:
        """Euclid maps to Neo4j's 'euclidean' similarity function."""
        q = vector_index_query("Chunk", "embedding", 4, Distance.EUCLID)
        assert "`vector.similarity_function`: 'euclidean'" in q

    def test_dot_unsupported(self) -> None:
        """Neo4j vector indexes have no dot-product function."""
        with pytest.raises(ValueError):
            vector_index_query("Chunk", "embedding", 4, Distance.DOT)

    def test_validates_label(self) -> None:
        """An unsafe label is rejected."""
        with pytest.raises(ValueError):
            vector_index_query("Bad Label", "embedding", 4, Distance.COSINE)


class TestVectorSearchQuery:
    """vector_search_query builds the native vector procedure call."""

    def test_no_filter(self) -> None:
        """Without a filter the query calls the vector procedure and returns."""
        q, params = vector_search_query("Chunk_embedding_vector")
        assert "CALL db.index.vector.queryNodes($index, $k, $vector)" in q
        assert "RETURN node, score" in q
        assert params == {}

    def test_with_filter(self) -> None:
        """A filter is appended as a WHERE clause with its own parameters."""
        q, params = vector_search_query("Chunk_embedding_vector", {"kind": "doc"})
        assert "WHERE node.kind = $filter_kind" in q
        assert params == {"filter_kind": "doc"}
