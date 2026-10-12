"""Tests for upsert_relation_query in agrag.cypher.relations.

Covers relationship-type validation before the query is built.
"""

import pytest

from agrag.common.data_models.candidate import CANDIDATE_EDGE_TYPES
from agrag.cypher.relations import upsert_relation_query


class TestUpsertRelationQuery:
    """upsert_relation_query validates its relationship type."""

    def test_validates_type(self) -> None:
        """An unsafe relationship type raises before the query is built."""
        with pytest.raises(ValueError):
            upsert_relation_query("Bad Type")

    @pytest.mark.parametrize("edge_type", sorted(CANDIDATE_EDGE_TYPES))
    def test_rejects_candidate_edge_types(self, edge_type: str) -> None:
        """Only the candidate writer can create candidate edge types."""
        with pytest.raises(ValueError, match="reserved"):
            upsert_relation_query(edge_type)
