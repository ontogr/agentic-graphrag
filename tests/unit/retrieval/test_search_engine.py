"""Tests for SearchEngine in agrag.retrieval.search_engine.

Patches retriever-level ``vector_search``/``resolve_entity``/
``_parse_chunk_node`` functions and BFSRetriever/node_distance_rerank with
AsyncMock/MagicMock, using an AsyncMock graph store, so no real database or
embedding call is made. Covers single-method and HYBRID (fused entity+chunk)
recipes, forwarding a recipe's bfs_depth to BFSRetriever (or omitting it when
None), that SearchFilters route to only the retrievers they apply to
(relation_types to BFS, labels to entity search, document_ids to entity,
chunk, and community search), that BFS fusion uses one "bfs" key rather than
one per prior result,
that node-distance rerank seeds are the pre-BFS top-k entity ids only (never
chunk ids or every candidate), that entity_labels (not the collection name)
drive native entity search, and error handling: every method failing raises
AllRetrievalMethodsFailedError, a partial failure keeps surviving results and
logs a warning, and an unknown recipe method name raises
UnknownRecipeMethodError instead of silently returning no hits.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.community import Community
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_schema import (
    GENERIC,
    EntityType,
    GraphSchema,
    RelationType,
)
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.search_result import SearchResult
from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.errors import (
    AllRetrievalMethodsFailedError,
    UnknownRecipeMethodError,
)
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.traversal import extract_entity_ids
from agrag.retrieval.recipes import ENTITY, HYBRID, Recipe
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings


class MockEmbedder:
    """Mock embedder for search engine tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Return a mock vector."""
        return [0.1, 0.2]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return mock vectors for a batch."""
        return [[0.1, 0.2] for _ in texts]


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

    async def test_single_method_search(self) -> None:
        """A single-method recipe runs one retriever."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = AsyncMock()
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
        ):
            mock_vs.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_resolve.return_value = ent

            results = await engine.search("test", ENTITY)

            assert len(results) == 1
            assert results[0].item.id == ent.id

    async def test_hybrid_fuses_entity_and_chunk(self) -> None:
        """HYBRID recipe fuses entity and chunk results."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        ch = Chunk(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="Some text",
            provenance=TextProvenance(char_start=0, char_end=9),
        )

        gs = AsyncMock()
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_ev,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_er,
            patch(
                "agrag.retrieval.retrievers.chunk.vector_search",
                new_callable=AsyncMock,
            ) as mock_cv,
            patch(
                "agrag.retrieval.retrievers.chunk.ChunkRetriever._parse_chunk_node",
            ) as mock_cp,
        ):
            mock_ev.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_er.return_value = ent
            mock_cv.return_value = [VectorHit(id=ch.id, score=0.8, payload={})]
            mock_cp.return_value = ch

            gs.execute_read.return_value = [
                {
                    "n": {
                        "id": str(ch.id),
                        "properties": {
                            "document_id": str(ch.document_id),
                            "index": 0,
                            "text": "Some text",
                            "provenance": '{"kind":"text","char_start":0,"char_end":9}',
                            "heading_path": [],
                            "content_kind": "text",
                        },
                    }
                }
            ]

            results = await engine.search("test", HYBRID)

            assert len(results) >= 1

    async def test_bfs_passes_recipe_depth(self) -> None:
        """Recipe bfs_depth is forwarded to BFSRetriever."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = AsyncMock()
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)
        recipe = Recipe(methods=["entity"], bfs=True, bfs_depth=5)

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
            patch(
                "agrag.retrieval.search_engine.BFSRetriever",
                new_callable=MagicMock,
            ) as mock_bfs,
        ):
            mock_vs.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_resolve.return_value = ent
            bfs_inst = mock_bfs.return_value
            bfs_inst.retrieve = AsyncMock(return_value=[])

            await engine.search("test", recipe)

            bfs_inst.retrieve.assert_awaited_once()
            call_kwargs = bfs_inst.retrieve.call_args.kwargs
            assert call_kwargs["depth"] == 5

    async def test_bfs_depth_none_omits_depth_kwarg(self) -> None:
        """When bfs_depth is None, depth is not passed explicitly."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = AsyncMock()
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)
        recipe = Recipe(methods=["entity"], bfs=True, bfs_depth=None)

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
            patch(
                "agrag.retrieval.search_engine.BFSRetriever",
                new_callable=MagicMock,
            ) as mock_bfs,
        ):
            mock_vs.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_resolve.return_value = ent
            bfs_inst = mock_bfs.return_value
            bfs_inst.retrieve = AsyncMock(return_value=[])

            await engine.search("test", recipe)

            bfs_inst.retrieve.assert_awaited_once()
            call_kwargs = bfs_inst.retrieve.call_args.kwargs
            assert "depth" not in call_kwargs

    async def test_bfs_relation_types_filter_passed(self) -> None:
        """SearchFilters.relation_types reach BFSRetriever as filters."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = AsyncMock()
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)
        recipe = Recipe(methods=["entity"], bfs=True, bfs_depth=2)
        filters = SearchFilters(relation_types=["KNOWS", "WORKS_WITH"])

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
            patch(
                "agrag.retrieval.search_engine.BFSRetriever",
                new_callable=MagicMock,
            ) as mock_bfs,
        ):
            mock_vs.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_resolve.return_value = ent
            bfs_inst = mock_bfs.return_value
            bfs_inst.retrieve = AsyncMock(return_value=[])

            await engine.search("test", recipe, filters=filters)

            bfs_inst.retrieve.assert_awaited_once()
            call_kwargs = bfs_inst.retrieve.call_args.kwargs
            bfs_filters = call_kwargs["filters"]
            assert bfs_filters is not None
            assert bfs_filters.relation_types == ["KNOWS", "WORKS_WITH"]

    async def test_entity_label_filter_not_passed_to_chunk(self) -> None:
        """Labels in filters only reach entity search, not chunk search."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        ch = Chunk(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="t",
            provenance=TextProvenance(char_start=0, char_end=1),
        )
        gs = AsyncMock()
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)
        filters = SearchFilters(labels=["Person"])

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_ev,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_er,
            patch(
                "agrag.retrieval.retrievers.chunk.vector_search",
                new_callable=AsyncMock,
            ) as mock_cv,
            patch(
                "agrag.retrieval.retrievers.chunk.ChunkRetriever._parse_chunk_node",
            ) as mock_cp,
        ):
            mock_ev.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_er.return_value = ent
            mock_cv.return_value = [VectorHit(id=ch.id, score=0.8, payload={})]
            mock_cp.return_value = ch
            gs.execute_read.return_value = [{"n": {"id": str(ch.id)}}]

            await engine.search("test", HYBRID, filters=filters)

            # Raw entity search should have received the label filter as-is.
            entity_call = mock_ev.call_args_list[0]
            entity_filters = entity_call.kwargs.get("filters")
            assert entity_filters is not None
            assert entity_filters.labels == ["Person"]

            # Chunk search should NOT have received the label filter.
            chunk_call = mock_cv.call_args
            chunk_filters = chunk_call.kwargs.get("filters")
            assert chunk_filters is None or not chunk_filters.labels

    async def test_doc_id_filter_scopes_entity_and_chunk_search(self) -> None:
        """document_ids in filters reach entity search and chunk search."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = AsyncMock()
        gs.execute_read.return_value = []
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)
        doc_id = str(uuid4())
        filters = SearchFilters(document_ids=[doc_id])

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_ev,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_er,
            patch(
                "agrag.retrieval.retrievers.chunk.vector_search",
                new_callable=AsyncMock,
            ) as mock_cv,
        ):
            mock_ev.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_er.return_value = ent
            mock_cv.return_value = []

            results = await engine.search("test", HYBRID, filters=filters)

            # The entity has no mention in the scoped document, so it is dropped.
            assert not any(isinstance(r.item, Entity) for r in results)

            chunk_call = mock_cv.call_args
            chunk_filters = chunk_call.kwargs.get("filters")
            assert chunk_filters is not None
            assert chunk_filters.document_ids == [doc_id]

    async def test_community_expand_receives_scoping_filters(self) -> None:
        """document_ids/properties filters reach community_context.

        Regression test: community expansion used to ignore the active
        SearchFilters entirely, so a document- or property-scoped search
        could still be enriched with a community report drawn from
        outside that scope.
        """
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = AsyncMock()
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)
        recipe = Recipe(methods=["entity"], community_expand=True, community_top_k=2)
        doc_id = str(uuid4())
        filters = SearchFilters(document_ids=[doc_id])

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
            patch(
                "agrag.retrieval.community_context.community_context",
                new_callable=AsyncMock,
            ) as mock_cc,
        ):
            mock_vs.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_resolve.return_value = ent
            mock_cc.return_value = []

            await engine.search("test", recipe, filters=filters)

            mock_cc.assert_awaited_once()
            call_kwargs = mock_cc.call_args.kwargs
            community_filters = call_kwargs["filters"]
            assert community_filters is not None
            assert community_filters.document_ids == [doc_id]

    async def test_community_expand_fuses_nonempty_results(self) -> None:
        """Non-empty community_context results are fused into the output."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        community = Community(
            id=uuid4(),
            title="T",
            summary="S",
            rating=5,
            rating_explanation="e",
        )
        gs = AsyncMock()
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)
        recipe = Recipe(methods=["entity"], community_expand=True, community_top_k=2)

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
            patch(
                "agrag.retrieval.community_context.community_context",
                new_callable=AsyncMock,
            ) as mock_cc,
        ):
            mock_vs.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_resolve.return_value = ent
            mock_cc.return_value = [
                SearchResult(item=community, score=5.0, method="community")
            ]

            results = await engine.search("test", recipe)

            assert any(r.item.id == community.id for r in results)

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
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
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
            mock_resolve.side_effect = [ent1, ent2]
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

    async def test_bfs_fusion_not_split_per_prior_result(self) -> None:
        """BFS fusion uses a single methods key, not one per result."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        ent2 = Entity(id=uuid4(), label="Person", name="Bob")
        gs = AsyncMock()
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)
        recipe = Recipe(methods=["entity"], bfs=True, bfs_depth=2)

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
            patch(
                "agrag.retrieval.search_engine.BFSRetriever",
                new_callable=MagicMock,
            ) as mock_bfs,
            patch(
                "agrag.retrieval.search_engine.fuse",
                wraps=__import__("agrag.retrieval.fusion", fromlist=["fuse"]).fuse,
            ) as mock_fuse,
        ):
            mock_vs.return_value = [
                VectorHit(id=ent.id, score=0.9, payload={}),
                VectorHit(id=ent2.id, score=0.8, payload={}),
            ]
            mock_resolve.side_effect = [ent, ent2]
            bfs_inst = mock_bfs.return_value
            bfs_inst.retrieve = AsyncMock(
                return_value=[
                    SearchResult(item=ent2, score=1.0, method="bfs"),
                ]
            )

            await engine.search("test", recipe)

            # The second fuse call (BFS pass) should receive exactly
            # two keys: "methods" (the fused prior results) and "bfs".
            assert mock_fuse.call_count == 2
            bfs_fuse_call = mock_fuse.call_args_list[1]
            fuse_keys = list(bfs_fuse_call.args[0].keys())
            assert fuse_keys == ["methods", "bfs"]

    async def test_node_distance_uses_entity_ids_only(self) -> None:
        """node_distance_rerank receives only entity ids from results."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        ch = Chunk(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="t",
            provenance=TextProvenance(char_start=0, char_end=1),
        )
        gs = AsyncMock()
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)
        recipe = Recipe(
            methods=["entity", "chunk"],
            reranker="node_distance",
        )

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_ev,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_er,
            patch(
                "agrag.retrieval.retrievers.chunk.vector_search",
                new_callable=AsyncMock,
            ) as mock_cv,
            patch(
                "agrag.retrieval.retrievers.chunk.ChunkRetriever._parse_chunk_node",
            ) as mock_cp,
            patch(
                "agrag.retrieval.search_engine.node_distance_rerank",
                new_callable=AsyncMock,
            ) as mock_ndr,
        ):
            mock_ev.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_er.return_value = ent
            mock_cv.return_value = [VectorHit(id=ch.id, score=0.8, payload={})]
            mock_cp.return_value = ch
            gs.execute_read.return_value = [{"n": {"id": str(ch.id)}}]
            mock_ndr.return_value = [
                SearchResult(item=ent, score=0.9, method="entity"),
            ]

            await engine.search("test", recipe)

            mock_ndr.assert_awaited_once()
            call_kwargs = mock_ndr.call_args.kwargs
            seed_ids = call_kwargs["seed_ids"]
            # Only the entity id should be in seeds, not the chunk id.
            assert ent.id in seed_ids
            assert ch.id not in seed_ids

    async def test_node_distance_seeds_are_not_every_candidate(self) -> None:
        """Seeds are the top-k direct hits, so distances can differ."""
        entities = [Entity(id=uuid4(), label="Person", name=f"E{i}") for i in range(4)]
        gs = AsyncMock()
        engine = SearchEngine(
            graph_store=gs,
            embedder=MockEmbedder(),
            settings=RetrievalSettings(node_distance_seed_top_k=2),
        )
        recipe = Recipe(methods=["entity"], reranker="node_distance")

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_ev,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_er,
            patch(
                "agrag.retrieval.search_engine.node_distance_rerank",
                new_callable=AsyncMock,
            ) as mock_ndr,
        ):
            mock_ev.return_value = [
                VectorHit(id=e.id, score=0.9 - i / 10, payload={})
                for i, e in enumerate(entities)
            ]
            mock_er.side_effect = entities
            mock_ndr.return_value = []

            await engine.search("test", recipe)

            seed_ids = mock_ndr.call_args.kwargs["seed_ids"]
            candidate_ids = [r.item.id for r in mock_ndr.call_args.args[0]]
            assert seed_ids == [entities[0].id, entities[1].id]
            assert set(seed_ids) != set(candidate_ids)

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
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_er,
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
            mock_er.return_value = seed_ent
            bfs_inst = mock_bfs.return_value
            bfs_inst.retrieve = AsyncMock(
                return_value=[SearchResult(item=neighbour, score=1.0, method="bfs")]
            )
            mock_ndr.return_value = []

            await engine.search("test", recipe)

            seed_ids = mock_ndr.call_args.kwargs["seed_ids"]
            assert seed_ids == [seed_ent.id]

    async def test_entity_labels_reach_native_entity_search(self) -> None:
        """Schema labels, not the collection name, drive native search."""
        ent = Entity(id=uuid4(), label="Drug", name="Aspirin")
        gs = AsyncMock()
        engine = SearchEngine(
            graph_store=gs,
            embedder=MockEmbedder(),
            entity_labels=["Drug", "Disease"],
            graph_schema=_CLINICAL_SCHEMA,
        )

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_ev,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_er,
        ):
            mock_ev.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_er.return_value = ent

            await engine.search("test", ENTITY)

            raw_call, resolved_call = mock_ev.call_args_list
            assert raw_call.kwargs["labels"] == ["Drug", "Disease"]
            assert raw_call.kwargs["collection"] == "agrag_entities"
            assert resolved_call.kwargs["labels"] == ("ResolvedEntity",)

    async def test_graph_schema_labels_drive_entity_search(self) -> None:
        """A custom schema's labels drive native search with no second input."""
        ent = Entity(id=uuid4(), label="Drug", name="Aspirin")
        engine = SearchEngine(
            graph_store=AsyncMock(),
            embedder=MockEmbedder(),
            graph_schema=_CLINICAL_SCHEMA,
        )

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_ev,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_er,
        ):
            mock_ev.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_er.return_value = ent

            await engine.search("Aspirin", ENTITY)

            assert mock_ev.call_args_list[0].kwargs["labels"] == ["Drug", "Disease"]

    def test_graph_schema_none_falls_back_to_generic(self) -> None:
        """Omitting the schema resolves to the shared GENERIC constant."""
        engine = SearchEngine(graph_store=AsyncMock(), embedder=MockEmbedder())

        assert engine.graph_schema is GENERIC

        with patch(
            "agrag.retrieval.search_engine.Text2CypherRetriever"
        ) as mock_retriever:
            engine._build_retrievers()

        assert mock_retriever.call_args.kwargs["schema"] is GENERIC

    def test_entity_labels_must_match_graph_schema(self) -> None:
        """Entity labels outside the schema are rejected, not ignored."""
        with pytest.raises(ValueError, match="entity_labels must name exactly"):
            SearchEngine(
                graph_store=AsyncMock(),
                embedder=MockEmbedder(),
                entity_labels=["Person"],
                graph_schema=_CLINICAL_SCHEMA,
            )

    def test_entity_labels_matching_the_schema_are_accepted(self) -> None:
        """Entity labels naming exactly the schema's labels pass validation."""
        engine = SearchEngine(
            graph_store=AsyncMock(),
            embedder=MockEmbedder(),
            entity_labels=["Disease", "Drug"],
            graph_schema=_CLINICAL_SCHEMA,
        )

        assert engine.graph_schema is _CLINICAL_SCHEMA

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
                "agrag.retrieval.retrievers.chunk.ChunkRetriever._parse_chunk_node",
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
        engine = SearchEngine(graph_store=AsyncMock(), embedder=MockEmbedder())
        recipe = Recipe(methods=["entity"], community_expand=True)

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_search,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
            patch(
                "agrag.retrieval.community_context.community_context",
                new_callable=AsyncMock,
                side_effect=RuntimeError("community store unavailable"),
            ),
        ):
            mock_search.return_value = [VectorHit(id=entity.id, score=0.9, payload={})]
            mock_resolve.return_value = entity

            with caplog.at_level(logging.WARNING):
                results = await engine.search("Ada", recipe)

        assert [result.item for result in results] == [entity]
        assert "Community expansion failed" in caplog.text

    async def test_recipe_min_score_overrides_settings_value(self) -> None:
        """A per-call min_score beats the configured rerank threshold."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        engine = SearchEngine(
            graph_store=AsyncMock(),
            embedder=MockEmbedder(),
            settings=RetrievalSettings(reranker_min_score=0.2),
        )
        recipe = Recipe(methods=["entity"], reranker="cross_encoder", min_score=0.9)

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_ev,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_er,
            patch(
                "agrag.retrieval.search_engine.cross_encoder_rerank",
                new_callable=AsyncMock,
            ) as mock_rerank,
        ):
            mock_ev.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_er.return_value = ent
            mock_rerank.return_value = []

            await engine.search("test", recipe)

            assert mock_rerank.await_args.kwargs["min_score"] == 0.9

    async def test_recipe_min_score_none_falls_back_to_settings(self) -> None:
        """A recipe that sets no floor still uses the configured threshold."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        engine = SearchEngine(
            graph_store=AsyncMock(),
            embedder=MockEmbedder(),
            settings=RetrievalSettings(reranker_min_score=0.2),
        )
        recipe = Recipe(methods=["entity"], reranker="cross_encoder")

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_ev,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_er,
            patch(
                "agrag.retrieval.search_engine.cross_encoder_rerank",
                new_callable=AsyncMock,
            ) as mock_rerank,
        ):
            mock_ev.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_er.return_value = ent
            mock_rerank.return_value = []

            await engine.search("test", recipe)

            assert mock_rerank.await_args.kwargs["min_score"] == 0.2

    async def test_search_bfs_seeding_calls_extract_entity_ids(self) -> None:
        """search() seeds BFS through the relocated free function."""
        entity = Entity(id=uuid4(), label="Person", name="Ada")
        engine = SearchEngine(graph_store=AsyncMock(), embedder=MockEmbedder())
        recipe = Recipe(methods=["entity"], bfs=True, bfs_depth=1)

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
            patch(
                "agrag.retrieval.search_engine.extract_entity_ids",
                wraps=extract_entity_ids,
            ) as mock_extract,
            patch(
                "agrag.retrieval.search_engine.BFSRetriever",
            ) as mock_bfs,
        ):
            mock_vs.return_value = [VectorHit(id=entity.id, score=0.9, payload={})]
            mock_resolve.return_value = entity
            mock_bfs.return_value.retrieve = AsyncMock(return_value=[])

            await engine.search("Ada", recipe)

        assert mock_extract.call_count == 1
        assert mock_bfs.return_value.retrieve.call_args.kwargs["seed_ids"] == [
            entity.id
        ]

    async def test_search_community_expand_calls_expand_with_communities(
        self,
    ) -> None:
        """search() enriches through the shared community-expansion helper."""
        entity = Entity(id=uuid4(), label="Person", name="Ada")
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [{"id": str(entity.id)}]
        engine = SearchEngine(graph_store=graph_store, embedder=MockEmbedder())
        recipe = Recipe(methods=["entity"], community_expand=True, community_top_k=2)
        doc_id = str(uuid4())

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
            patch(
                "agrag.retrieval.search_engine.expand_with_communities",
                new_callable=AsyncMock,
            ) as mock_expand,
        ):
            mock_vs.return_value = [VectorHit(id=entity.id, score=0.9, payload={})]
            mock_resolve.return_value = entity
            mock_expand.return_value = []

            await engine.search(
                "Ada", recipe, filters=SearchFilters(document_ids=[doc_id])
            )

        kwargs = mock_expand.call_args.kwargs
        assert kwargs["top_k"] == 2
        assert kwargs["filters"].document_ids == [doc_id]
        assert mock_expand.call_args.args[1] == [entity.id]
