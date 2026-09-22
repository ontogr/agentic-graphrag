"""Tests for materialized resolved-entity data models."""

from uuid import uuid4

from agrag.common.data_models.resolved_entity import (
    MATCHES_RELATION,
    RESOLVED_AS_RELATION,
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

    def test_constants(self) -> None:
        """Label and relation constants have expected values."""
        assert RESOLVED_ENTITY_LABEL == "ResolvedEntity"
        assert MATCHES_RELATION == "MATCHES"
        assert RESOLVED_AS_RELATION == "RESOLVED_AS"

    def test_is_a_valid_retrieval_result_item(self) -> None:
        """Grouped retrieval keeps its derived type instead of faking a raw entity."""
        entity = ResolvedEntity(
            id=uuid4(), label="Person", name="Ada", member_ids=[uuid4()]
        )

        result = SearchResult(item=entity, score=0.9, method="entity")

        assert result.item is entity
