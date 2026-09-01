"""Tests for new Cypher entity builders: hydration and resolve."""

import pytest

from agrag.cypher.entities import (
    hydrate_chunks_by_id_query,
    hydrate_entities_by_id_query,
    resolve_merged_into_query,
    set_chunk_embedding_query,
)


class TestResolveMergedIntoQuery:
    """resolve_merged_into_query reads the merged_into property."""

    def test_reads_merged_into_property(self) -> None:
        """The query returns the merged_into property, not a path."""
        q = resolve_merged_into_query()
        assert "n.merged_into AS merged_into" in q
        assert "MERGED_INTO" not in q

    def test_returns_node(self) -> None:
        """The query returns the matched node."""
        q = resolve_merged_into_query()
        assert "RETURN n AS node" in q

    def test_expects_id_parameter(self) -> None:
        """The query expects an $id parameter."""
        q = resolve_merged_into_query()
        assert "$id" in q


class TestHydrateEntitiesByIdQuery:
    """hydrate_entities_by_id_query filters out tombstones."""

    def test_filters_merged_into(self) -> None:
        """The query filters on merged_into IS NULL."""
        q = hydrate_entities_by_id_query()
        assert "merged_into IS NULL" in q

    def test_unwinds_ids(self) -> None:
        """The query UNWINDs over $ids."""
        q = hydrate_entities_by_id_query()
        assert "UNWIND $ids AS id" in q

    def test_returns_nodes(self) -> None:
        """The query returns matched nodes."""
        q = hydrate_entities_by_id_query()
        assert "RETURN n" in q


class TestHydrateChunksByIdQuery:
    """hydrate_chunks_by_id_query fetches chunks by id."""

    def test_includes_chunk_label(self) -> None:
        """The query matches on the Chunk label."""
        q = hydrate_chunks_by_id_query()
        assert "Chunk" in q

    def test_unwinds_ids(self) -> None:
        """The query UNWINDs over $ids."""
        q = hydrate_chunks_by_id_query()
        assert "UNWIND $ids AS id" in q


class TestSetChunkEmbeddingQuery:
    """set_chunk_embedding_query guards on text."""

    def test_guards_on_text(self) -> None:
        """The query checks text matches before writing."""
        q = set_chunk_embedding_query("embedding")
        assert "n.text = record.expected_text" in q

    def test_sets_vector_property(self) -> None:
        """The query sets the specified vector property."""
        q = set_chunk_embedding_query("embedding")
        assert "n.embedding = record.vector" in q

    def test_validates_property_name(self) -> None:
        """An unsafe property name raises."""
        with pytest.raises(ValueError):
            set_chunk_embedding_query("bad name")
