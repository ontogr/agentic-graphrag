"""Tests for the Cypher write builders in agrag.cypher.resolution_write.

Each builder is asserted against a fixed expected string, so any change
to the generated Cypher fails loudly here.
"""

from agrag.cypher.resolution_write import (
    clear_resolved_entity_vector_deletions_query,
    enqueue_resolved_entity_vector_deletions_query,
)


class TestResolutionWriteQueries:
    """Resolution write builders emit fixed Cypher."""

    def test_enqueue_resolved_entity_vector_deletions_query(self) -> None:
        """Failed vector deletions are persisted for a later retry."""
        assert enqueue_resolved_entity_vector_deletions_query() == (
            "UNWIND $records AS record "
            "MERGE (pending:ResolvedEntityVectorDeletion {id: record.id}) "
            "SET pending.collection = record.collection, "
            "pending.error = record.error, pending.updated_at = datetime()"
        )

    def test_clear_resolved_entity_vector_deletions_query(self) -> None:
        """Successfully retried vector deletions are removed."""
        assert clear_resolved_entity_vector_deletions_query() == (
            "UNWIND $ids AS pending_id "
            "MATCH (pending:ResolvedEntityVectorDeletion {id: pending_id}) "
            "DETACH DELETE pending"
        )
