"""Tests for new Cypher relation builders: BFS and MENTIONED_IN."""

from agrag.cypher.relations import (
    bfs_expand_query,
    chunks_mentioning_entities_query,
    entities_mentioned_in_chunks_query,
)


class TestBfsExpandQuery:
    """bfs_expand_query builds a bounded BFS expansion."""

    def test_contains_variable_length_pattern(self) -> None:
        """The query uses a variable-length path pattern."""
        q = bfs_expand_query(depth=3)
        assert "*1..3" in q

    def test_limits_results(self) -> None:
        """The query has a LIMIT clause."""
        q = bfs_expand_query(limit=25)
        assert "LIMIT 25" in q

    def test_excludes_seed_ids(self) -> None:
        """The query excludes seed ids from results."""
        q = bfs_expand_query()
        assert "NOT neighbor.id IN $seed_ids" in q

    def test_expects_seed_ids_parameter(self) -> None:
        """The query expects $seed_ids."""
        q = bfs_expand_query()
        assert "$seed_ids" in q


class TestChunksMentioningEntitiesQuery:
    """chunks_mentioning_entities_query walks MENTIONED_IN."""

    def test_walks_mentioned_in(self) -> None:
        """The query traverses MENTIONED_IN edges."""
        q = chunks_mentioning_entities_query()
        assert "MENTIONED_IN" in q

    def test_filters_tombstones(self) -> None:
        """The query filters out tombstoned chunks."""
        q = chunks_mentioning_entities_query()
        assert "merged_into IS NULL" in q

    def test_expects_entity_ids(self) -> None:
        """The query expects $entity_ids."""
        q = chunks_mentioning_entities_query()
        assert "$entity_ids" in q


class TestEntitiesMentionedInChunksQuery:
    """entities_mentioned_in_chunks_query walks MENTIONED_IN reverse."""

    def test_walks_mentioned_in(self) -> None:
        """The query traverses MENTIONED_IN edges."""
        q = entities_mentioned_in_chunks_query()
        assert "MENTIONED_IN" in q

    def test_filters_tombstones(self) -> None:
        """The query filters out tombstoned entities."""
        q = entities_mentioned_in_chunks_query()
        assert "merged_into IS NULL" in q

    def test_expects_chunk_ids(self) -> None:
        """The query expects $chunk_ids."""
        q = entities_mentioned_in_chunks_query()
        assert "$chunk_ids" in q
