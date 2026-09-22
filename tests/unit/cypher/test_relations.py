"""Tests for upsert_relation_query in agrag.cypher.relations.

Covers the base match-and-merge shape keyed by relationship id, deleting a
stale relationship found at different endpoints under the same id,
relationship-type validation, and that ``source_chunk_ids`` is read and
unioned inside the query (via ``coalesce``) rather than overwritten, with
the read happening before the blind ``SET r += record.properties`` so a
concurrent writer's contribution is not lost.
"""

import pytest

from agrag.cypher.relations import (
    close_part_of_query,
    entities_in_documents_query,
    upsert_relation_query,
)


def test_close_part_of_query_only_closes_open_edges() -> None:
    """The lifecycle query preserves superseded edge timestamps."""
    query = close_part_of_query()
    assert "$document_node_id" in query
    assert "r.invalid_at IS NULL" in query
    assert "SET r.invalid_at = datetime()" in query
    assert "RETURN count(r) AS closed" in query


class TestEntitiesInDocumentsQuery:
    """entities_in_documents_query reads only through open PART_OF edges."""

    def test_filters_to_open_part_of_edges(self) -> None:
        """Superseded chunks cannot contribute their entities."""
        query = entities_in_documents_query()
        assert "part.invalid_at IS NULL" in query
        assert "$document_ids" in query

    def test_excludes_tombstoned_entities(self) -> None:
        """Merged-away entities never surface through the traversal."""
        query = entities_in_documents_query()
        assert "entity.merged_into IS NULL" in query


class TestUpsertRelationQuery:
    """upsert_relation_query builds a validated, id-keyed merge."""

    def test_builds_match_merge(self) -> None:
        """The query matches both endpoints and merges the relationship by id."""
        q = upsert_relation_query("MENTIONS")
        assert "MATCH (a {id: record.start_id})" in q
        assert "MATCH (b {id: record.end_id})" in q
        assert "MERGE (a)-[r:MENTIONS {id: record.id}]->(b)" in q
        assert "SET r += CASE WHEN can_update THEN record.properties" in q

    def test_replaces_stale_relationship_at_old_endpoints(self) -> None:
        """A same-id relationship at different endpoints is deleted first."""
        q = upsert_relation_query("MENTIONS")
        assert "OPTIONAL MATCH (x)-[stale:MENTIONS {id: record.id}]->(y)" in q
        assert "WHERE (x.id <> record.start_id OR y.id <> record.end_id)" in q
        assert "DELETE stale" in q

    def test_validates_type(self) -> None:
        """An unsafe relationship type raises before the query is built."""
        with pytest.raises(ValueError):
            upsert_relation_query("Bad Type")

    def test_tags_the_pending_job_only_when_the_merge_creates_the_edge(self) -> None:
        """An edge a job only writes over must stay untagged.

        Tagging it on every write, not just creation, would hide a
        committed edge from retrieval and put it in reach of that job's
        rollback.
        """
        q = upsert_relation_query("MENTIONS")
        assert "ON CREATE SET r._pending_job_id = record.pending_job_id" in q
        assert "ON MATCH SET r._pending_job_id" not in q

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
            "SET r += CASE WHEN can_update THEN record.properties"
        )
        assert "stale._pending_job_id = record.pending_job_id" in q
