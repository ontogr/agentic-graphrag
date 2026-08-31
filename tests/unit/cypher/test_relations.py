"""Tests for the Cypher relationship builders."""

import pytest

from agrag.cypher.relations import upsert_relation_query


class TestUpsertRelationQuery:
    """upsert_relation_query builds a validated, id-keyed merge."""

    def test_builds_match_merge(self) -> None:
        """The query matches both endpoints and merges the relationship by id."""
        q = upsert_relation_query("MENTIONS")
        assert "MATCH (a {id: record.start_id})" in q
        assert "MATCH (b {id: record.end_id})" in q
        assert "MERGE (a)-[r:MENTIONS {id: record.id}]->(b)" in q
        assert "SET r += record.properties" in q

    def test_replaces_stale_relationship_at_old_endpoints(self) -> None:
        """A same-id relationship at different endpoints is deleted first."""
        q = upsert_relation_query("MENTIONS")
        assert "OPTIONAL MATCH (x)-[stale:MENTIONS {id: record.id}]->(y)" in q
        assert "WHERE x.id <> record.start_id OR y.id <> record.end_id" in q
        assert "DELETE stale" in q

    def test_validates_type(self) -> None:
        """An unsafe relationship type raises before the query is built."""
        with pytest.raises(ValueError):
            upsert_relation_query("Bad Type")

    def test_unions_source_chunk_ids_instead_of_overwriting(self) -> None:
        """source_chunk_ids is read and unioned inside the query, not overwritten.

        Regression test: two concurrent upserts of the same relationship
        each compute their own union from a read taken before either write
        lands. Reading the relationship's current source_chunk_ids inside
        this same query (not a blind SET from the caller's properties) is
        what keeps a concurrent writer's chunk ids from being discarded.
        """
        q = upsert_relation_query("MENTIONS")
        assert "coalesce(r.source_chunk_ids, [])" in q
        assert "SET r.source_chunk_ids =" in q
        assert "coalesce(record.properties.source_chunk_ids, [])" in q
        # The union read must happen before the blind property SET, or it
        # would read back the value this same write just overwrote instead
        # of what another writer may have already committed.
        assert q.index("existing_source_chunk_ids") < q.index(
            "SET r += record.properties"
        )
