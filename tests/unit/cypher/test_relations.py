"""Tests for upsert_relation_query in agrag.cypher.relations.

Covers relationship-type validation before the query is built.
"""

import pytest

from agrag.cypher.relations import upsert_relation_query


class TestUpsertRelationQuery:
    """upsert_relation_query validates its relationship type."""

    def test_validates_type(self) -> None:
        """An unsafe relationship type raises before the query is built."""
        with pytest.raises(ValueError):
            upsert_relation_query("Bad Type")
