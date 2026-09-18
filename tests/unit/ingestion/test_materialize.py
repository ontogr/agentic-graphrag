"""Regression coverage for deterministic semantic component materialization."""

from uuid import uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.ingestion.match_decision import MatchDecision, matches_id
from agrag.ingestion.materialize import materialize_component


def _schema() -> GraphSchema:
    """Build the smallest schema needed to materialize people."""
    return GraphSchema(
        name="test",
        version="1",
        entities=[EntityType(label="Person", description="A person.", properties={})],
        relations=[],
    )


class TestMatchDecision:
    """Match decisions have reversible, order-independent identities."""

    def test_reuses_id_when_endpoints_are_reversed(self) -> None:
        """The same pair cannot create two directed match edges."""
        left_id, right_id = uuid4(), uuid4()

        forward = MatchDecision.create(
            left_entity_id=left_id,
            right_entity_id=right_id,
            comparator="FuzzyMatch",
        )
        reverse = MatchDecision.create(
            left_entity_id=right_id,
            right_entity_id=left_id,
            comparator="FuzzyMatch",
        )

        assert forward.id == reverse.id == matches_id(left_id, right_id)

    def test_rejects_self_pair(self) -> None:
        """A raw entity cannot semantically match itself."""
        entity_id = uuid4()

        with pytest.raises(ValueError, match="distinct raw entities"):
            MatchDecision.create(
                left_entity_id=entity_id,
                right_entity_id=entity_id,
                comparator="FuzzyMatch",
            )


class TestMaterializeComponent:
    """Resolved components retain raw membership without order-dependent output."""

    async def test_is_stable_when_database_member_order_changes(self) -> None:
        """Shuffled raw members produce the same resolved materialization."""
        first = Entity(id=uuid4(), label="Person", name="Ada Lovelace", merge_count=2)
        second = Entity(id=uuid4(), label="Person", name="A. Lovelace", merge_count=1)

        forward = await materialize_component([first, second], schema=_schema())
        reverse = await materialize_component([second, first], schema=_schema())

        assert forward.model_dump(exclude={"created_at"}) == reverse.model_dump(
            exclude={"created_at"}
        )
        assert forward.member_ids == sorted([first.id, second.id], key=str)
        assert forward.merge_count == 3
