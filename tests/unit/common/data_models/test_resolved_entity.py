"""Tests for materialized resolved-entity data models."""

from uuid import uuid4

from agrag.common.data_models.resolved_entity import (
    RESOLVED_ENTITY_LABEL,
    ResolvedEntity,
)
from agrag.common.data_models.search_result import SearchResult


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

    def test_is_a_valid_retrieval_result_item(self) -> None:
        """Grouped retrieval keeps its derived type instead of faking a raw entity."""
        entity = ResolvedEntity(
            id=uuid4(), label="Person", name="Ada", member_ids=[uuid4()]
        )

        result = SearchResult(item=entity, score=0.9, method="entity")

        assert result.item is entity
