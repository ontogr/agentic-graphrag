"""Tests for persisted raw-entity candidate blocking."""

from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.ingestion.resolve.candidate_source import persisted_candidate_indices


def _entity(name: str, label: str = "Person") -> Entity:
    """Build a raw entity for candidate-index tests."""
    return Entity(id=uuid4(), label=label, name=name)


def _mention(entity: Entity) -> ExtractedEntity:
    """Build the synthetic mention used by consolidation."""
    return ExtractedEntity(
        chunk_id=uuid4(),
        label=entity.label,
        text=entity.name,
        char_start=0,
        char_end=len(entity.name),
    )


class _CandidateSource:
    """Configurable graph-candidate double."""

    def __init__(self, candidates: dict[str, list[Entity]]) -> None:
        self.candidates = candidates

    async def global_candidates_for(self, mention: ExtractedEntity) -> list[Entity]:
        """Return configured candidates by mention text."""
        return self.candidates.get(mention.text, [])


class TestPersistedCandidateIndices:
    """Consolidation blocks through raw graph candidates."""

    async def test_maps_ann_candidates_back_to_entity_indices(self) -> None:
        """Only returned same-label raw nodes become resolver pairs."""
        first, second, other = _entity("Ada"), _entity("Ada L."), _entity("Org", "Org")

        indices = await persisted_candidate_indices(
            [_mention(first), _mention(second), _mention(other)],
            [first, second, other],
            source=_CandidateSource({"Ada": [second, other]}),  # type: ignore[arg-type]
        )

        assert indices == {0: [1]}

    async def test_uses_bounded_full_scan_when_index_has_no_candidates(self) -> None:
        """Small first-time graphs still compare every same-label raw entity."""
        first, second = _entity("Ada"), _entity("Ada L.")

        indices = await persisted_candidate_indices(
            [_mention(first), _mention(second)],
            [first, second],
            source=_CandidateSource({}),  # type: ignore[arg-type]
        )

        assert indices == {0: [1], 1: [0]}
