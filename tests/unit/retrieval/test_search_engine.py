"""Tests for SearchEngine."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.search_result import SearchResult
from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.recipes import ENTITY, HYBRID, Recipe
from agrag.retrieval.search_engine import SearchEngine


class MockEmbedder:
    """Mock embedder for search engine tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Return a mock vector."""
        return [0.1, 0.2]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return mock vectors for a batch."""
        return [[0.1, 0.2] for _ in texts]


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

            # Entity search should have received the label filter.
            entity_call = mock_ev.call_args
            entity_filters = entity_call.kwargs.get("filters")
            assert entity_filters is not None
            assert entity_filters.labels == ["Person"]

            # Chunk search should NOT have received the label filter.
            chunk_call = mock_cv.call_args
            chunk_filters = chunk_call.kwargs.get("filters")
            assert chunk_filters is None or not chunk_filters.labels

    async def test_chunk_doc_id_filter_not_passed_to_entity(self) -> None:
        """document_ids in filters only reach chunk search, not entity."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = AsyncMock()
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

            await engine.search("test", HYBRID, filters=filters)

            # Entity search should NOT have received the doc_id filter.
            entity_call = mock_ev.call_args
            entity_filters = entity_call.kwargs.get("filters")
            assert entity_filters is None or not entity_filters.document_ids

            # Chunk search should have received the doc_id filter.
            chunk_call = mock_cv.call_args
            chunk_filters = chunk_call.kwargs.get("filters")
            assert chunk_filters is not None
            assert chunk_filters.document_ids == [doc_id]

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
