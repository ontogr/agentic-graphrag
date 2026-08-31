"""Entity retriever: dense vector search over entities."""

from agrag.common.data_models.search_result import SearchResult
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.identity import resolve_entity
from agrag.retrieval.methods.vector import vector_search
from agrag.retrieval.retrievers.base import Retriever
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


class EntityRetriever(Retriever):
    """Dense entity search via vector similarity.

    Embeds the query, searches via the GraphStore-native or
    VectorStore path, then resolves every hit through
    ``resolve_entity`` so the caller can trust ``item.id`` is live.
    """

    name = "entity"

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        embedder: Embedder,
        vector_store: VectorStore | None = None,
        settings: RetrievalSettings | None = None,
    ) -> None:
        """Construct an EntityRetriever.

        Args:
            graph_store: Backs entity search when vector_store is
                absent.
            embedder: Produces query vectors.
            vector_store: Optional VectorStore for hybrid search.
            settings: Retrieval configuration; defaults from
                environment.
        """
        self._graph_store = graph_store
        self._embedder = embedder
        self._vector_store = vector_store
        self._settings = settings or RetrievalSettings()

    async def retrieve(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        limit: int | None = None,
    ) -> list[SearchResult]:
        """Run entity search and return hydrated results.

        Args:
            query: The natural-language query text.
            filters: Constraints applied to the search.
            limit: Maximum results. None uses settings.entity_top_k.

        Returns:
            Ranked SearchResults with resolved entity ids.
        """
        effective_limit = limit or self._settings.entity_top_k
        label = self._settings.entity_collection
        hits = await vector_search(
            query,
            embedder=self._embedder,
            graph_store=self._graph_store,
            vector_store=self._vector_store,
            label_or_collection=label,
            limit=effective_limit,
            filters=filters,
            settings=self._settings,
        )
        results: list[SearchResult] = []
        for hit in hits:
            try:
                entity = await resolve_entity(self._graph_store, hit.id)
                results.append(
                    SearchResult(item=entity, score=hit.score, method=self.name)
                )
            except (ValueError, Exception):
                continue
        return results
