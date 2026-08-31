"""Retrieval's public entry point, independent of Graph (ADR 0035)."""

import asyncio

from agrag.common.data_models.search_result import SearchResult
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.fusion import fuse
from agrag.retrieval.recipes import Recipe
from agrag.retrieval.rerank.cross_encoder import cross_encoder_rerank
from agrag.retrieval.rerank.node_distance import node_distance_rerank
from agrag.retrieval.retrievers.bfs import BFSRetriever
from agrag.retrieval.retrievers.chunk import ChunkRetriever
from agrag.retrieval.retrievers.entity import EntityRetriever
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


class SearchEngine:
    """Retrieval's public entry point, independent of Graph.

    Fans a query out to every method a Recipe names, fuses the
    results, and optionally reranks them. Constructed from its own
    stores; does not depend on a Graph instance existing.
    """

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        embedder: Embedder,
        vector_store: VectorStore | None = None,
        settings: RetrievalSettings | None = None,
    ) -> None:
        """Construct a SearchEngine.

        Args:
            graph_store: Always required; backs entity/chunk search
                when vector_store is absent, and always backs BFS.
            embedder: Produces query vectors for dense and hybrid
                search.
            vector_store: Optional. When set, entity and chunk search
                run hybrid_search there instead of GraphStore's native
                search. Configuring one without a dual-write ingestion
                change gets an empty result set, not an error.
            settings: Retrieval configuration; defaults from
                environment.
        """
        self._graph_store = graph_store
        self._embedder = embedder
        self._vector_store = vector_store
        self._settings = settings or RetrievalSettings()

    async def search(
        self,
        query: str,
        recipe: Recipe,
        *,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        """Run recipe's methods, fuse, expand, and optionally rerank.

        Runs recipe.methods concurrently and fuses their output
        first. When recipe.bfs is set, BFS runs as a second,
        sequential step seeded from the fused entity results. BFS
        results are fused into the same list a second time before
        reranking.

        Args:
            query: The natural-language query text.
            recipe: Which methods to run, whether to expand via BFS
                afterward, and which reranker, if any, follows.
            filters: Constraints applied identically to every method.

        Returns:
            Up to recipe.limit results, ranked highest-relevance
            first.
        """
        retrievers = self._build_retrievers()

        # Fan out recipe.methods concurrently.
        tasks = []
        method_names = []
        for method_name in recipe.methods:
            if method_name in retrievers:
                tasks.append(
                    retrievers[method_name].retrieve(
                        query, filters=filters, limit=recipe.limit
                    )
                )
                method_names.append(method_name)

        method_results = await asyncio.gather(*tasks, return_exceptions=True)

        results_by_method: dict[str, list[SearchResult]] = {}
        for name, result in zip(method_names, method_results, strict=True):
            if isinstance(result, Exception):
                continue
            results_by_method[name] = result

        # First fusion pass.
        fused = fuse(results_by_method, rrf_k=self._settings.rrf_k)

        # BFS expansion as sequential follow-up.
        if recipe.bfs:
            seed_ids = [
                r.item.id
                for r in fused
                if hasattr(r.item, "id") and type(r.item).__name__ == "Entity"
            ]
            bfs_retriever = BFSRetriever(
                graph_store=self._graph_store, settings=self._settings
            )
            bfs_results = await bfs_retriever.retrieve(
                query,
                filters=filters,
                limit=recipe.limit,
                seed_ids=seed_ids,
            )
            if bfs_results:
                fused = fuse(
                    {
                        **{f"fused_{i}": [r] for i, r in enumerate(fused)},
                        "bfs": bfs_results,
                    },
                    rrf_k=self._settings.rrf_k,
                )

        # Rerank.
        if recipe.reranker == "cross_encoder":
            fused = await cross_encoder_rerank(
                query,
                fused,
                min_score=self._settings.reranker_min_score,
            )
        elif recipe.reranker == "node_distance":
            seed_ids = [
                r.item.id
                for r in fused
                if hasattr(r.item, "id") and type(r.item).__name__ == "Entity"
            ]
            fused = await node_distance_rerank(
                fused,
                graph_store=self._graph_store,
                seed_ids=seed_ids,
            )

        return fused[: recipe.limit]

    def _build_retrievers(self) -> dict:
        """Build the retriever map from current stores."""
        return {
            "entity": EntityRetriever(
                graph_store=self._graph_store,
                embedder=self._embedder,
                vector_store=self._vector_store,
                settings=self._settings,
            ),
            "chunk": ChunkRetriever(
                graph_store=self._graph_store,
                embedder=self._embedder,
                vector_store=self._vector_store,
                settings=self._settings,
            ),
        }
