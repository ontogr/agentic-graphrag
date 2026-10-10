"""Tests for bfs_expand_query and relationship_types_from_query in cypher.relations.

Covers bfs_expand_query rejecting an injection attempt in a relation type or
an unsupported direction, and clamping depth to [1, 10] and limit to
[1, 1000] rather than passing extreme values through. Also covers
relationship_types_from_query rejecting an unsafe relation type.
"""

import pytest

from agrag.cypher.relations import (
    bfs_expand_query,
    relationship_types_from_query,
)


class TestBfsExpandQuery:
    """bfs_expand_query builds a bounded BFS expansion."""

    def test_unsafe_relation_type_raises(self) -> None:
        """An injection attempt in a relation type is rejected."""
        with pytest.raises(ValueError):
            bfs_expand_query(relation_types=["TREATS]-() MATCH (x) DETACH DELETE x //"])

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

    @pytest.mark.parametrize("direction", ["OUTGOING", "outgoing ", "sideways"])
    def test_invalid_direction_raises_value_error(self, direction: str) -> None:
        """Unsupported directions fail before query construction."""
        with pytest.raises(ValueError, match="expected one of"):
            bfs_expand_query(direction=direction)


class TestRelationshipTypesFromQuery:
    """relationship_types_from_query validates its relation types."""

    def test_unsafe_relation_type_raises(self) -> None:
        """An injection attempt in a relation type is rejected."""
        with pytest.raises(ValueError):
            relationship_types_from_query(
                relation_types=["TREATS]->() MATCH (x) DETACH DELETE x //"]
            )
