"""Tests for GraphCandidateSource.

Covers same-label in-batch blocking with exact index sets and both
global_candidates_for routing branches.

Also covers how a native vector hit becomes a persisted Entity, and the
neighbor-context builders LLMVerify's batched verification reads:
``build_relation_neighbors`` from a batch's own extraction, and
``fetch_persisted_neighbors`` from the persisted graph.
"""

from unittest.mock import AsyncMock, MagicMock, patch
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


def _source() -> tuple[GraphCandidateSource, AsyncMock]:
    """Build a source with mocked stores for in-batch tests."""
    graph_store = AsyncMock()
    graph_store.vector_search = AsyncMock()
    source = GraphCandidateSource(
        graph_store=graph_store,
        embedder=MagicMock(),
    )
    return source, graph_store


class TestGraphCandidateSourceInBatch:
    """candidates_for blocks by label within the batch."""

    async def test_never_proposes_cross_label(self) -> None:
        """Only the same-label mention is proposed."""
        source, _ = _source()
        entities = [
            _mention("Ada", label="Person"),
            _mention("Apple", label="Organization"),
            _mention("Charles", label="Person"),
        ]
        assert await source.candidates_for(0, entities) == [2]

    async def test_proposes_all_same_label(self) -> None:
        """Every other same-label mention is proposed in order."""
        source, _ = _source()
        entities = [
            _mention("Ada", label="Person"),
            _mention("Charles", label="Person"),
            _mention("Grace", label="Person"),
        ]
        assert await source.candidates_for(0, entities) == [1, 2]
        assert await source.candidates_for(1, entities) == [0, 2]


class TestGraphCandidateSourceGlobalCandidatesFor:
    """global_candidates_for resolves vector hits into persisted entities."""

    async def test_native_path_validates_payload_directly(self) -> None:
        """The native payload already has the real name.

        The native path must not be touched by the load-by-id fix, and
        must not issue a graph read to get the name.
        """
        entity_id = uuid4()
        graph_store = AsyncMock()
        source = GraphCandidateSource(graph_store=graph_store, embedder=MockEmbedder())

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

    async def test_native_payload_mismatch_keeps_each_score_with_its_entity(
        self,
    ) -> None:
        """A label-mismatched native hit's score is not shifted onto the next."""
        source = GraphCandidateSource(graph_store=AsyncMock(), embedder=MockEmbedder())
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


class TestFetchPersistedNeighbors:
    """fetch_persisted_neighbors batches one read for every requested id."""

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

    async def test_caps_repeated_rows_for_the_same_entity(self) -> None:
        """Duplicate requested ids do not let returned rows exceed the cap."""
        entity_id = uuid4()
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [
            {
                "entity_id": str(entity_id),
                "rel_type": "KNOWS",
                "neighbor_name": f"Person {index}",
            }
            for index in range(MAX_NEIGHBORS_PER_ENTITY + 2)
        ]

        neighbors = await fetch_persisted_neighbors(
            [entity_id, entity_id],
            graph_store=graph_store,
            exclude_relation_types=[],
        )

        assert neighbors[entity_id] == [
            f"KNOWS Person {index}" for index in range(MAX_NEIGHBORS_PER_ENTITY)
        ]
