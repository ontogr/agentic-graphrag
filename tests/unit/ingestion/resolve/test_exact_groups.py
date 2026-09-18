"""Tests for exact-name raw-entity grouping."""

from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.ingestion.resolve.exact_groups import exact_resolution_groups


def _mention(text: str, *, label: str = "Person") -> ExtractedEntity:
    """Build a minimal extracted entity mention."""
    return ExtractedEntity(
        chunk_id=uuid4(), label=label, text=text, char_start=0, char_end=len(text)
    )


class TestExactResolutionGroups:
    """Only exact identity can merge raw mentions."""

    def test_keeps_fuzzy_mentions_as_separate_raw_entities(self) -> None:
        """Near names do not share a raw entity before MATCHES materialization."""
        groups = exact_resolution_groups(
            [_mention("Ada"), _mention("Ada Lovelace")], {}
        )
        assert [group.entity_indices for group in groups] == [[0], [1]]

    def test_unifies_aliases_that_resolve_to_one_existing_entity(self) -> None:
        """Different exact aliases contribute to the same persisted raw entity."""
        entity = Entity(id=uuid4(), label="Person", name="Ada Lovelace")
        groups = exact_resolution_groups(
            [_mention("Ada"), _mention("Ada Lovelace")], {0: entity, 1: entity}
        )
        assert [group.entity_indices for group in groups] == [[0, 1]]
