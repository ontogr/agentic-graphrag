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
        q, _ = bfs_expand_query(depth=3)
        assert "*1..3" in q

    def test_limits_results(self) -> None:
        """The query has a LIMIT clause."""
        q, _ = bfs_expand_query(limit=25)
        assert "LIMIT 25" in q

    def test_excludes_seed_ids(self) -> None:
        """The query excludes seed ids from results."""
        q, _ = bfs_expand_query()
        assert "NOT neighbor.id IN $seed_ids" in q

    def test_expects_seed_ids_parameter(self) -> None:
        """The query expects $seed_ids."""
        q, _ = bfs_expand_query()
        assert "$seed_ids" in q

    def test_no_filters_returns_empty_params(self) -> None:
        """Without filters the params dict is empty."""
        _, params = bfs_expand_query()
        assert params == {}

    def test_filters_add_where_clause(self) -> None:
        """Filters append a WHERE clause for the neighbor node."""
        q, params = bfs_expand_query(filters={"label": ["Person"]})
        assert "filter_label" in q
        assert params["filter_label"] == ["Person"]

    def test_filters_are_ANDed(self) -> None:
        """Multiple filters are AND-ed together."""
        q, params = bfs_expand_query(filters={"label": ["Person"], "name": "Alice"})
        assert "AND" in q
        assert "filter_label" in params
        assert "filter_name" in params

    def test_excludes_chunk_nodes(self) -> None:
        """The query excludes Chunk-labeled nodes from results."""
        q, _ = bfs_expand_query()
        assert "NOT neighbor:Chunk" in q

    def test_depth_clamped_to_safe_range(self) -> None:
        """Depth above 10 is clamped to 10."""
        q, _ = bfs_expand_query(depth=999)
        assert "*1..10" in q

    def test_depth_clamped_below_minimum(self) -> None:
        """Depth below 1 is clamped to 1."""
        q, _ = bfs_expand_query(depth=0)
        assert "*1..1" in q

    def test_limit_clamped_to_safe_range(self) -> None:
        """Limit above 1000 is clamped to 1000."""
        q, _ = bfs_expand_query(limit=99999)
        assert "LIMIT 1000" in q

    def test_limit_clamped_below_minimum(self) -> None:
        """Limit below 1 is clamped to 1."""
        q, _ = bfs_expand_query(limit=0)
        assert "LIMIT 1" in q


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
