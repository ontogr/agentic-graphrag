"""Tests for entity-resolution support primitives."""

from uuid import uuid4

from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.vector_record import VectorHit
from agrag.ingestion.resolve.candidate_source import GraphCandidateSource


class TestResolutionSupport:
    """Small pure resolution support units."""

    async def test_reads_valid_global_candidates(self, monkeypatch) -> None:
        """Global search maps a persisted entity payload into an Entity."""
        entity_id, chunk_id = uuid4(), uuid4()

        async def search(*args, **kwargs):
            return [
                VectorHit(
                    id=entity_id,
                    score=0.9,
                    payload={"label": "Person", "name": "Ada"},
                )
            ]

        monkeypatch.setattr(
            "agrag.ingestion.resolve.candidate_source.vector_search", search
        )
        source = GraphCandidateSource(graph_store=None, embedder=None)  # type: ignore[arg-type]
        mention = ExtractedEntity(
            chunk_id=chunk_id,
            label="Person",
            text="Ada",
            char_start=0,
            char_end=3,
        )
        assert [
            entity.id for entity, _ in await source.global_candidates_for(mention)
        ] == [entity_id]

    async def test_restores_label_for_native_graph_candidates(
        self, monkeypatch
    ) -> None:
        """Native graph hit properties gain the searched entity label."""
        entity_id, chunk_id = uuid4(), uuid4()

        async def search(*args, **kwargs):
            return [VectorHit(id=entity_id, score=0.9, payload={"name": "Ada"})]

        monkeypatch.setattr(
            "agrag.ingestion.resolve.candidate_source.vector_search", search
        )
        source = GraphCandidateSource(graph_store=None, embedder=None)  # type: ignore[arg-type]
        mention = ExtractedEntity(
            chunk_id=chunk_id,
            label="Person",
            text="Ada",
            char_start=0,
            char_end=3,
        )
        assert [
            entity.id for entity, _ in await source.global_candidates_for(mention)
        ] == [entity_id]
