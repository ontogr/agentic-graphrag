"""Tests for entity-resolution support primitives."""

from uuid import uuid4

from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.vector_record import VectorHit
from agrag.cypher.resolution_write import deactivate_match_query, upsert_matches_query
from agrag.ingestion.resolve.candidate_source import GraphCandidateSource


class TestResolutionSupport:
    """Small pure resolution support units."""

    async def test_blocks_candidates_by_label(self) -> None:
        """In-batch candidates only include mentions with the same label."""
        source = GraphCandidateSource(graph_store=None, embedder=None)  # type: ignore[arg-type]
        chunk_id = uuid4()
        mentions = [
            ExtractedEntity(
                chunk_id=chunk_id, label="Person", text="Ada", char_start=0, char_end=3
            ),
            ExtractedEntity(
                chunk_id=chunk_id,
                label="Place",
                text="London",
                char_start=0,
                char_end=6,
            ),
            ExtractedEntity(
                chunk_id=chunk_id,
                label="Person",
                text="Grace",
                char_start=0,
                char_end=5,
            ),
        ]
        assert await source.candidates_for(0, mentions) == [2]

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

    def test_builds_resolution_queries(self) -> None:
        """Resolution query builders produce the required relationship operations."""
        queries = [upsert_matches_query(), deactivate_match_query()]
        assert all("MATCH" in query for query in queries)
        assert "ON CREATE SET" in upsert_matches_query()

    def test_serializes_resolved_entity(self) -> None:
        """Resolved entities retain member ids in graph records."""
        member_id = uuid4()
        entity = ResolvedEntity(
            id=uuid4(), label="Person", name="Ada", member_ids=[member_id]
        )
        assert entity.to_node_record().properties["member_ids"] == [str(member_id)]
