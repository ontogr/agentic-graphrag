"""Tests for GraphCandidateSource.global_candidates_for.

Covers the VectorStore-backed candidate path, which must hydrate the
persisted Entity by id rather than reconstructing its name from the display
text. Patches ``agrag.ingestion.resolve.candidate_source.vector_search`` the
way ``tests/unit/retrieval/retrievers/test_entity.py`` patches its
module-local ``vector_search`` import.

Also covers the neighbor-context builders LLMVerify's batched verification
reads: ``build_relation_neighbors`` from a batch's own extraction, and
``fetch_persisted_neighbors`` from the persisted graph.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.vector_record import VectorHit
from agrag.ingestion.resolve.candidate_source import (
    MAX_NEIGHBORS_PER_ENTITY,
    GraphCandidateSource,
    build_relation_neighbors,
    fetch_persisted_neighbors,
)


class MockEmbedder:
    """Mock embedder for candidate-source tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Method under test."""
        return [0.1, 0.2]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Method under test."""
        return [[0.1, 0.2] for _ in texts]


def _mention(text: str, label: str = "Show") -> ExtractedEntity:
    """Build a mention for candidate-source tests."""
    return ExtractedEntity(
        chunk_id=uuid4(),
        label=label,
        text=text,
        char_start=0,
        char_end=len(text),
    )


def _relation(
    source_index: int, target_index: int, label: str = "WORKS_AT"
) -> ExtractedRelation:
    """Build a relation mention for the neighbor-builder tests."""
    return ExtractedRelation(
        chunk_id=uuid4(),
        label=label,
        source_index=source_index,
        target_index=target_index,
    )


class TestGraphCandidateSourceGlobalCandidatesFor:
    """global_candidates_for resolves vector hits into persisted entities."""

    async def test_returns_untruncated_name_for_vector_store_hit(self) -> None:
        """A colon in the real name is not truncated by the VectorStore path.

        Regression: the payload only carries embedding_text under "text", so
        guessing the name by splitting on ":" turned "Star Trek: Voyager"
        into "Star Trek". The fix hydrates the real node by id instead.
        """
        entity_id = uuid4()
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [
            {
                "n": {
                    "id": str(entity_id),
                    "labels": ["Show", "_AgragNode"],
                    "properties": {"name": "Star Trek: Voyager"},
                }
            }
        ]
        source = GraphCandidateSource(
            graph_store=graph_store,
            embedder=MockEmbedder(),
            vector_store=AsyncMock(),
            vector_collection="entities",
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=entity_id,
                    score=0.9,
                    payload={"label": "Show", "text": "Star Trek: Voyager"},
                )
            ],
        ):
            candidates = await source.global_candidates_for(
                _mention("Star Trek: Voyager")
            )

        assert len(candidates) == 1
        assert candidates[0][0].name == "Star Trek: Voyager"
        assert candidates[0][1] == 0.9

    async def test_skips_hits_that_fail_to_hydrate(self) -> None:
        """A hit whose node cannot be hydrated is dropped, not guessed."""
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = []
        source = GraphCandidateSource(
            graph_store=graph_store,
            embedder=MockEmbedder(),
            vector_store=AsyncMock(),
            vector_collection="entities",
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=uuid4(),
                    score=0.9,
                    payload={"label": "Show", "text": "Star Trek: Voyager"},
                )
            ],
        ):
            candidates = await source.global_candidates_for(
                _mention("Star Trek: Voyager")
            )

        assert candidates == []

    async def test_native_path_validates_payload_directly(self) -> None:
        """With no VectorStore, the native payload already has the real name.

        The native path must not be touched by the hydrate-by-id fix, and
        must not issue a graph read to get the name.
        """
        entity_id = uuid4()
        graph_store = AsyncMock()
        source = GraphCandidateSource(
            graph_store=graph_store, embedder=MockEmbedder(), vector_store=None
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=entity_id,
                    score=0.9,
                    payload={"name": "Star Trek: Voyager"},
                )
            ],
        ):
            candidates = await source.global_candidates_for(
                _mention("Star Trek: Voyager")
            )

        graph_store.execute_read.assert_not_called()
        assert len(candidates) == 1
        assert candidates[0][0].name == "Star Trek: Voyager"
        assert candidates[0][1] == 0.9

    async def test_hydration_keeps_each_score_with_its_own_entity(self) -> None:
        """Dropping an unhydrated hit does not shift scores onto other entities.

        Regression guard: associating scores with entities by position would
        give the surviving entity the dropped hit's score instead of its own.
        """
        dropped_id, kept_id = uuid4(), uuid4()
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [
            {
                "n": {
                    "id": str(kept_id),
                    "labels": ["Show", "_AgragNode"],
                    "properties": {"name": "Voyager"},
                }
            }
        ]
        source = GraphCandidateSource(
            graph_store=graph_store,
            embedder=MockEmbedder(),
            vector_store=AsyncMock(),
            vector_collection="entities",
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(id=dropped_id, score=0.2, payload={"text": "Dropped"}),
                VectorHit(id=kept_id, score=0.95, payload={"text": "Voyager"}),
            ],
        ):
            candidates = await source.global_candidates_for(_mention("Voyager"))

        assert [entity.id for entity, _ in candidates] == [kept_id]
        assert [score for _, score in candidates] == [0.95]

    async def test_native_payload_mismatch_keeps_each_score_with_its_entity(
        self,
    ) -> None:
        """A label-mismatched native hit's score is not shifted onto the next."""
        source = GraphCandidateSource(
            graph_store=AsyncMock(), embedder=MockEmbedder(), vector_store=None
        )
        kept_id = uuid4()

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=uuid4(),
                    score=0.1,
                    payload={"label": "Place", "name": "Paris"},
                ),
                VectorHit(
                    id=kept_id,
                    score=0.88,
                    payload={"label": "Show", "name": "Voyager"},
                ),
            ],
        ):
            candidates = await source.global_candidates_for(_mention("Voyager"))

        assert [entity.id for entity, _ in candidates] == [kept_id]
        assert [score for _, score in candidates] == [0.88]


class TestBuildRelationNeighbors:
    """build_relation_neighbors renders each direction of every relation."""

    def test_contributes_both_directions(self) -> None:
        """Both endpoints name the other, with the relation label."""
        entities = [_mention("Ada", "Person"), _mention("Acme", "Org")]

        neighbors = build_relation_neighbors(entities, [_relation(0, 1)])

        assert neighbors == {0: ["WORKS_AT Acme"], 1: ["WORKS_AT Ada"]}

    def test_caps_each_index_at_max_neighbors(self) -> None:
        """An index with more relations than the cap keeps only the cap."""
        entities = [_mention("Ada")] + [_mention(f"Other {i}") for i in range(7)]
        relations = [_relation(0, target) for target in range(1, 8)]

        neighbors = build_relation_neighbors(entities, relations)

        assert len(neighbors[0]) == MAX_NEIGHBORS_PER_ENTITY
        assert neighbors[0] == [
            "WORKS_AT Other 0",
            "WORKS_AT Other 1",
            "WORKS_AT Other 2",
            "WORKS_AT Other 3",
            "WORKS_AT Other 4",
        ]

    def test_entity_with_no_relations_has_no_key(self) -> None:
        """An index no relation names is absent, not present and empty."""
        entities = [_mention("Ada"), _mention("Acme"), _mention("Grace")]

        neighbors = build_relation_neighbors(entities, [_relation(0, 1)])

        assert 2 not in neighbors

    def test_empty_relations_returns_empty_map(self) -> None:
        """No relation mentions means no neighbor context at all."""
        assert build_relation_neighbors([_mention("Ada")], []) == {}


class TestFetchPersistedNeighbors:
    """fetch_persisted_neighbors batches one read for every requested id."""

    async def test_batches_all_ids_into_one_read(self) -> None:
        """Every id goes into one query, and rows become neighbor strings."""
        first, second = uuid4(), uuid4()
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [
            {"entity_id": str(first), "rel_type": "WORKS_AT", "neighbor_name": "Acme"},
            {"entity_id": str(second), "rel_type": "KNOWS", "neighbor_name": "Ada"},
        ]

        neighbors = await fetch_persisted_neighbors(
            [first, second],
            graph_store=graph_store,
            exclude_relation_types=["MATCHES"],
        )

        graph_store.execute_read.assert_awaited_once()
        _, params = graph_store.execute_read.await_args.args
        assert params["ids"] == [str(first), str(second)]
        assert params["exclude_types"] == ["MATCHES"]
        assert neighbors == {first: ["WORKS_AT Acme"], second: ["KNOWS Ada"]}

    async def test_skips_malformed_rows(self) -> None:
        """A row missing keys or carrying a bad uuid is skipped, not raised."""
        entity_id = uuid4()
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [
            {"entity_id": str(entity_id), "rel_type": "WORKS_AT"},
            {"entity_id": "not-a-uuid", "rel_type": "KNOWS", "neighbor_name": "Ada"},
            {"entity_id": str(entity_id), "rel_type": "KNOWS", "neighbor_name": "Ada"},
        ]

        neighbors = await fetch_persisted_neighbors(
            [entity_id],
            graph_store=graph_store,
            exclude_relation_types=[],
        )

        assert neighbors == {entity_id: ["KNOWS Ada"]}

    async def test_empty_ids_skips_the_read(self) -> None:
        """No ids means no query at all."""
        graph_store = AsyncMock()

        neighbors = await fetch_persisted_neighbors(
            [], graph_store=graph_store, exclude_relation_types=["MATCHES"]
        )

        assert neighbors == {}
        graph_store.execute_read.assert_not_awaited()
