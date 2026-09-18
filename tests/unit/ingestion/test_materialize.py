"""Tests for non-destructive entity-resolution materialization."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.ingestion.materialize import compute_resolved_entity, matches_id


def _schema() -> GraphSchema:
    """Build a minimal entity schema."""
    return GraphSchema(
        name="test",
        version="1",
        entities=[EntityType(label="Person", description="", properties={})],
        relations=[],
    )


def _entity(name: str, entity_id=None) -> Entity:
    """Build a persisted test entity."""
    return Entity(
        id=entity_id or uuid4(),
        created_at=datetime.now(UTC),
        label="Person",
        name=name,
    )


class TestMatchesId:
    """Deterministic MATCHES relationship identifiers."""

    def test_is_order_independent(self) -> None:
        """Both endpoint orders produce the same identifier."""
        first, second = uuid4(), uuid4()
        assert matches_id(first, second) == matches_id(second, first)


class TestComputeResolvedEntity:
    """Pure resolved-entity materialization."""

    async def test_is_order_independent(self) -> None:
        """Member order does not affect cluster identity or membership."""
        first, second = _entity("Ada"), _entity("Ada Lovelace")
        forward = await compute_resolved_entity([first, second], _schema())
        reverse = await compute_resolved_entity([second, first], _schema())
        assert forward.id == reverse.id
        assert forward.member_ids == reverse.member_ids

    async def test_rejects_singleton_membership(self) -> None:
        """A materialized cluster must have at least two members."""
        with pytest.raises(ValueError, match="at least two"):
            await compute_resolved_entity([_entity("Ada")], _schema())
