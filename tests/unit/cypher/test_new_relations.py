"""Tests for bfs_expand_query and the MENTIONED_IN walk builders in cypher.relations.

Covers bfs_expand_query's variable-length path pattern, result LIMIT,
seed-id exclusion, relation_types restricting (or, when absent, leaving
untyped) the relationship pattern, rejecting an injection attempt in a
relation type, filter-to-WHERE-clause translation with AND-combined
multiple filters, excluding Chunk-labeled neighbors, and clamping depth to
[1, 10] and limit to [1, 1000] rather than passing extreme values through.
Also covers chunks_mentioning_entities_query and
entities_mentioned_in_chunks_query traversing MENTIONED_IN in each
direction while filtering tombstoned nodes.

Directions are asserted at the string level (the exact arrow in the pattern),
and relationship_types_from_query is asserted to stay depth-1 only.
"""

import pytest

from agrag.cypher.relations import (
    bfs_expand_query,
    chunks_mentioning_entities_query,
    entities_mentioned_in_chunks_query,
    relationship_types_from_query,
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

    def test_relation_types_restrict_the_pattern(self) -> None:
        """relation_types become the relationship type pattern."""
        q, _ = bfs_expand_query(depth=2, relation_types=["TREATS", "CAUSES"])
        assert "[:TREATS|CAUSES*1..2]" in q

    def test_no_relation_types_crosses_every_type(self) -> None:
        """Without relation_types the pattern stays untyped."""
        q, _ = bfs_expand_query(depth=2)
        assert "[*1..2]" in q

    def test_unsafe_relation_type_raises(self) -> None:
        """An injection attempt in a relation type is rejected."""
        with pytest.raises(ValueError):
            bfs_expand_query(relation_types=["TREATS]-() MATCH (x) DETACH DELETE x //"])

    def test_filters_add_where_clause(self) -> None:
        """Filters append a WHERE clause for the neighbor node."""
        q, params = bfs_expand_query(filters={"label": ["Person"]})
        assert "filter_label" in q
        assert params["filter_label"] == ["Person"]

    def test_multiple_filters_use_and_logic(self) -> None:
        """Multiple filters are combined with AND logic."""
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

    def test_direction_defaults_to_both(self) -> None:
        """With no direction argument the traversal stays undirected."""
        q, _ = bfs_expand_query(depth=2)
        assert "(start)-[*1..2]-(neighbor)" in q

    def test_direction_outgoing_uses_forward_arrow(self) -> None:
        """direction="outgoing" walks relationships leaving the seed."""
        q, _ = bfs_expand_query(depth=2, direction="outgoing")
        assert "(start)-[*1..2]->(neighbor)" in q
        assert "<-" not in q

    def test_direction_incoming_uses_reverse_arrow(self) -> None:
        """direction="incoming" walks relationships entering the seed."""
        q, _ = bfs_expand_query(depth=2, direction="incoming")
        assert "(start)<-[*1..2]-(neighbor)" in q
        assert "->" not in q

    def test_direction_both_uses_undirected_pattern(self) -> None:
        """direction="both" matches the relationship either way."""
        q, _ = bfs_expand_query(depth=2, direction="both")
        assert "(start)-[*1..2]-(neighbor)" in q
        assert "->" not in q
        assert "<-" not in q

    def test_direction_and_relation_types_together(self) -> None:
        """A typed traversal keeps the direction arrow around the type pattern."""
        q, _ = bfs_expand_query(
            depth=1, relation_types=["TREATS"], direction="outgoing"
        )
        assert "(start)-[:TREATS*1..1]->(neighbor)" in q


class TestRelationshipTypesFromQuery:
    """relationship_types_from_query lists attached types, depth-1 only."""

    def test_projects_distinct_types(self) -> None:
        """The query returns one row per distinct attached type."""
        q = relationship_types_from_query()
        assert "RETURN DISTINCT type(r) AS rel_type" in q

    def test_expects_seed_ids(self) -> None:
        """The query expects $seed_ids and binds seed nodes by id."""
        q = relationship_types_from_query()
        assert "UNWIND $seed_ids AS seed_id" in q
        assert "MATCH (seed:_AgragNode {id: seed_id})" in q

    def test_stays_depth_one(self) -> None:
        """The query is depth-1 only: no variable-length path anywhere."""
        q = relationship_types_from_query(
            relation_types=["TREATS"], direction="outgoing"
        )
        assert "*1.." not in q
        assert "*]" not in q

    def test_relation_types_reuse_the_type_pattern(self) -> None:
        """relation_types produce the same pattern bfs_expand_query builds."""
        q = relationship_types_from_query(relation_types=["TREATS", "CAUSES"])
        bfs, _ = bfs_expand_query(depth=1, relation_types=["TREATS", "CAUSES"])
        assert "[r:TREATS|CAUSES]" in q
        assert "[:TREATS|CAUSES*1..1]" in bfs

    def test_no_relation_types_leaves_pattern_untyped(self) -> None:
        """Without relation_types the relationship pattern stays untyped."""
        q = relationship_types_from_query()
        assert "[r]-" in q

    def test_unsafe_relation_type_raises(self) -> None:
        """An injection attempt in a relation type is rejected."""
        with pytest.raises(ValueError):
            relationship_types_from_query(
                relation_types=["TREATS]->() MATCH (x) DETACH DELETE x //"]
            )

    def test_direction_outgoing_uses_forward_arrow(self) -> None:
        """direction="outgoing" reads relationships leaving the seed."""
        q = relationship_types_from_query(direction="outgoing")
        assert "(seed)-[r]->(neighbor)" in q
        assert "<-" not in q

    def test_direction_incoming_uses_reverse_arrow(self) -> None:
        """direction="incoming" reads relationships entering the seed."""
        q = relationship_types_from_query(direction="incoming")
        assert "(seed)<-[r]-(neighbor)" in q
        assert "->" not in q

    def test_direction_both_uses_undirected_pattern(self) -> None:
        """direction="both" reads relationships either way."""
        q = relationship_types_from_query(direction="both")
        assert "(seed)-[r]-(neighbor)" in q
        assert "->" not in q
        assert "<-" not in q


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
