"""Tests for SearchEngine in agrag.retrieval.search_engine.

Patches retriever-level ``vector_search``/``_parse_chunk_node`` functions and
BFSRetriever/node_distance_rerank with AsyncMock/MagicMock, using an AsyncMock
graph store that loads entities by id, so no real database or
embedding call is made. Covers reranker slot reservation, BFS seeds used for
rerank, entity labels checked against the graph schema, and error handling:
every method failing raises AllRetrievalMethodsFailedError, a partial failure
keeps surviving results and logs a warning, and an unknown recipe method name
raises UnknownRecipeMethodError instead of silently returning no hits.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.community import Community
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    RelationType,
)
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.search_result import SearchResult
from agrag.common.data_models.vector_record import VectorHit
from agrag.cypher.entities import load_entities_by_id_query
from agrag.retrieval.errors import (
    AllRetrievalMethodsFailedError,
    UnknownRecipeMethodError,
)
from agrag.retrieval.recipes import HYBRID, Recipe
from agrag.retrieval.search_engine import SearchEngine


class MockEmbedder:
    """Mock embedder for search engine tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Return a mock vector."""
        return [0.1, 0.2]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return mock vectors for a batch."""
        return [[0.1, 0.2] for _ in texts]


def _loading(store: AsyncMock, *entities: Entity) -> AsyncMock:
    """Make ``store`` load ``entities`` by id and answer other reads as before."""
    load_query = load_entities_by_id_query()

    async def execute_read(query: str, params: dict) -> list:
        """Return entity nodes for loading reads, else the configured rows."""
        if query != load_query:
            return store.execute_read.return_value
        return [
            {
                "n": {
                    "id": str(entity.id),
                    "name": entity.name,
                    "merge_key": entity.merge_key,
                }
            }
            for entity in entities
            if str(entity.id) in params["ids"]
        ]

    store.execute_read.side_effect = execute_read
    return store


# A non-GENERIC schema, so a test cannot pass by matching the fallback's labels.
_CLINICAL_SCHEMA = GraphSchema(
    name="clinical",
    version="1",
    entities=[
        EntityType(label="Drug", description="A medication."),
        EntityType(label="Disease", description="A diagnosed condition."),
    ],
    relations=[
        RelationType(
            label="TREATS",
            description="A drug treats a disease.",
            patterns=[("Drug", "Disease")],
        )
    ],
)


class TestSearchEngine:
    """SearchEngine fans out methods, fuses, and reranks."""

    async def test_cross_encoder_reserves_slots_for_community_items(self) -> None:
        """cross_encoder reranking excludes communities and reserves them slots.

        Community items are never sent to cross_encoder_rerank, and the
        number of reserved slots after rerank is capped at
        recipe.community_top_k even when more community items are present.
        """
        ent1 = Entity(id=uuid4(), label="Person", name="E1")
        ent2 = Entity(id=uuid4(), label="Person", name="E2")
        comm1 = Community(
            id=uuid4(), title="C1", summary="S", rating=5, rating_explanation="e"
        )
        comm2 = Community(
            id=uuid4(), title="C2", summary="S", rating=5, rating_explanation="e"
        )
        gs = AsyncMock()
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)
        recipe = Recipe(
            methods=["entity"],
            reranker="cross_encoder",
            community_expand=True,
            community_top_k=1,
            limit=3,
        )

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.community_context.community_context",
                new_callable=AsyncMock,
            ) as mock_cc,
            patch(
                "agrag.retrieval.search_engine.cross_encoder_rerank",
                new_callable=AsyncMock,
            ) as mock_cer,
        ):
            mock_vs.return_value = [
                VectorHit(id=ent1.id, score=0.9, payload={}),
                VectorHit(id=ent2.id, score=0.8, payload={}),
            ]
            _loading(gs, ent1, ent2)
            mock_cc.return_value = [
                SearchResult(item=comm1, score=5.0, method="community"),
                SearchResult(item=comm2, score=4.0, method="community"),
            ]
            mock_cer.return_value = [
                SearchResult(item=ent1, score=0.99, method="cross_encoder"),
                SearchResult(item=ent2, score=0.5, method="cross_encoder"),
            ]

            results = await engine.search("test", recipe)

            rerank_call_items = mock_cer.call_args.args[1]
            assert all(not isinstance(r.item, Community) for r in rerank_call_items)

            community_results = [r for r in results if isinstance(r.item, Community)]
            assert len(community_results) == 1

    async def test_bfs_seeds_exclude_bfs_neighbours_for_rerank(self) -> None:
        """Reranker seeds stay the pre-BFS hits after BFS expansion."""
        seed_ent = Entity(id=uuid4(), label="Person", name="Seed")
        neighbour = Entity(id=uuid4(), label="Person", name="Neighbour")
        gs = AsyncMock()
        engine = SearchEngine(graph_store=gs, embedder=MockEmbedder())
        recipe = Recipe(methods=["entity"], bfs=True, reranker="node_distance")

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_ev,
            patch(
                "agrag.retrieval.search_engine.BFSRetriever",
                new_callable=MagicMock,
            ) as mock_bfs,
            patch(
                "agrag.retrieval.search_engine.node_distance_rerank",
                new_callable=AsyncMock,
            ) as mock_ndr,
        ):
            mock_ev.return_value = [VectorHit(id=seed_ent.id, score=0.9, payload={})]
            _loading(gs, seed_ent)
            bfs_inst = mock_bfs.return_value
            bfs_inst.retrieve = AsyncMock(
                return_value=[SearchResult(item=neighbour, score=1.0, method="bfs")]
            )
            mock_ndr.return_value = []

            await engine.search("test", recipe)

            seed_ids = mock_ndr.call_args.kwargs["seed_ids"]
            assert seed_ids == [seed_ent.id]

    def test_entity_labels_must_match_graph_schema(self) -> None:
        """Entity labels outside the schema are rejected, not ignored."""
        with pytest.raises(ValueError, match="entity_labels must name exactly"):
            SearchEngine(
                graph_store=AsyncMock(),
                embedder=MockEmbedder(),
                entity_labels=["Person"],
                graph_schema=_CLINICAL_SCHEMA,
            )

    async def test_raises_when_every_method_fails(self) -> None:
        """A total retriever outage raises instead of returning no hits."""
        gs = AsyncMock()
        engine = SearchEngine(graph_store=gs, embedder=MockEmbedder())

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=RuntimeError("graph store down"),
            ),
            patch(
                "agrag.retrieval.retrievers.chunk.vector_search",
                new_callable=AsyncMock,
                side_effect=RuntimeError("vector store down"),
            ),
            pytest.raises(AllRetrievalMethodsFailedError) as excinfo,
        ):
            await engine.search("test", HYBRID)

        assert set(excinfo.value.failures) == {"entity", "chunk"}
        assert isinstance(excinfo.value.__cause__, RuntimeError)

    async def test_partial_failure_keeps_surviving_methods(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """One failing method does not sink the others or pass silently."""
        ch = Chunk(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="Some text",
            provenance=TextProvenance(char_start=0, char_end=9),
        )
        gs = AsyncMock()
        engine = SearchEngine(graph_store=gs, embedder=MockEmbedder())

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
                side_effect=RuntimeError("graph store down"),
            ),
            patch(
                "agrag.retrieval.retrievers.chunk.vector_search",
                new_callable=AsyncMock,
            ) as mock_cv,
            patch(
                "agrag.common.data_models.chunk.Chunk.from_node",
            ) as mock_cp,
        ):
            mock_cv.return_value = [VectorHit(id=ch.id, score=0.8, payload={})]
            mock_cp.return_value = ch
            gs.execute_read.return_value = [{"n": {"id": str(ch.id)}}]

            with caplog.at_level(
                logging.WARNING, logger="agrag.retrieval.search_engine"
            ):
                results = await engine.search("test", HYBRID)

        assert [r.item.id for r in results] == [ch.id]
        assert any("entity" in record.message for record in caplog.records)

    async def test_unknown_recipe_method_raises(self) -> None:
        """A misspelled method name raises instead of returning no hits.

        Silently skipping an unknown method would let an empty
        successful search hide a typo. A configuration error must
        surface at search time.
        """
        gs = AsyncMock()
        engine = SearchEngine(graph_store=gs, embedder=MockEmbedder())

        recipe = Recipe(methods=["enttiy"], limit=10)
        with pytest.raises(UnknownRecipeMethodError) as excinfo:
            await engine.search("test", recipe)

        assert excinfo.value.unknown == ["enttiy"]
        assert "entity" in excinfo.value.known

    async def test_community_expand_failure_keeps_search_results(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A community lookup error does not discard successful search results."""
        entity = Entity(id=uuid4(), label="Person", name="Ada", properties={})
        engine = SearchEngine(
            graph_store=_loading(AsyncMock(), entity), embedder=MockEmbedder()
        )
        recipe = Recipe(methods=["entity"], community_expand=True)

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_search,
            patch(
                "agrag.retrieval.community_context.community_context",
                new_callable=AsyncMock,
                side_effect=RuntimeError("community store unavailable"),
            ),
        ):
            mock_search.return_value = [VectorHit(id=entity.id, score=0.9, payload={})]

            with caplog.at_level(logging.WARNING):
                results = await engine.search("Ada", recipe)

        assert [result.item.id for result in results] == [entity.id]
        assert "Community expansion failed" in caplog.text
