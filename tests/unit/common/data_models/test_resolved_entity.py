"""Tests for materialized resolved-entity data models."""

from uuid import uuid4

from agrag.common.data_models.resolved_entity import (
    RESOLVED_ENTITY_LABEL,
    ResolvedEntity,
)


class TestResolvedEntity:
    """ResolvedEntity preserves derived identity and vector state."""

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

    def test_to_node_record_round_trip(self) -> None:
        """ResolvedEntity survives to_node_record with expected labels and props."""
        m1, m2 = uuid4(), uuid4()
        entity = ResolvedEntity(
            id=uuid4(),
            label="Person",
            name="Ada Lovelace",
            properties={"description": "Mathematician"},
            member_ids=[m1, m2],
            embedding=[0.1, 0.2],
            vector_sync_status="synced",
        )

        record = entity.to_node_record()

        assert record.id == entity.id
        assert record.labels == [RESOLVED_ENTITY_LABEL]
        assert record.properties == {
            "description": "Mathematician",
            "name": "Ada Lovelace",
            "label": "Person",
            "member_ids": [str(m1), str(m2)],
            "created_at": entity.created_at.isoformat(),
            "vector_sync_status": "synced",
            "embedding": [0.1, 0.2],
        }
