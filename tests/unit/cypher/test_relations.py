"""Tests for the Cypher relationship builders."""

import pytest

from agrag.cypher.relations import upsert_relation_query


class TestUpsertRelationQuery:
    """upsert_relation_query builds a validated, endpoint-matching merge."""

    def test_builds_match_merge(self) -> None:
        """The query matches both endpoints and merges the relationship."""
        q = upsert_relation_query("MENTIONS")
        assert "MATCH (a {id: record.start_id})" in q
        assert "MATCH (b {id: record.end_id})" in q
        assert "MERGE (a)-[r:MENTIONS]->(b)" in q
        assert "SET r += record.properties" in q

    def test_validates_type(self) -> None:
        """An unsafe relationship type raises before the query is built."""
        with pytest.raises(ValueError):
            upsert_relation_query("Bad Type")
