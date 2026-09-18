"""Tests for materialized resolved-entity data models."""

from uuid import uuid4

from agrag.common.data_models.resolved_entity import (
    RESOLVED_ENTITY_LABEL,
    ResolvedEntity,
)


class TestResolvedEntity:
    """ResolvedEntity preserves derived identity and vector state."""

    def test_to_node_record_carries_pending_vector_state(self) -> None:
        """Fresh materializations are marked pending before their vector sync."""
        first_member_id, second_member_id = uuid4(), uuid4()
        entity = ResolvedEntity(
            id=uuid4(),
            label="Person",
            name="Ada Lovelace",
            properties={"description": "Mathematician"},
            member_ids=[first_member_id, second_member_id],
        )

        record = entity.to_node_record()

        assert record.id == entity.id
        assert record.labels == [RESOLVED_ENTITY_LABEL]
        assert record.properties["vector_sync_status"] == "pending"
        assert "vector_sync_error" not in record.properties
        assert "embedding" not in record.properties

    def test_to_node_record_carries_failed_vector_state(self) -> None:
        """A failed sync leaves enough state for a later reconciliation pass."""
        entity = ResolvedEntity(
            id=uuid4(),
            label="Person",
            name="Ada Lovelace",
            member_ids=[uuid4(), uuid4()],
            vector_sync_status="failed",
            vector_sync_error="vector store down",
        )

        record = entity.to_node_record()

        assert record.properties["vector_sync_status"] == "failed"
        assert record.properties["vector_sync_error"] == "vector store down"
