"""Community retriever: dense vector search over community reports."""

from agrag.common.data_models.community import COMMUNITY_LABEL, Community
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.retrieval.community_context import _parse_community_node
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.vector import vector_search
from agrag.retrieval.retrievers.base import Retriever
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


class CommunityRetriever(Retriever):
    """Dense search over community reports, for direct thematic questions."""

    name = "community"

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        embedder: Embedder,
        vector_store: VectorStore | None = None,
        settings: RetrievalSettings | None = None,
    ) -> None:
        """Construct a CommunityRetriever."""
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
        """Run community-report search and return hydrated results."""
        effective_limit = limit if limit is not None else self._settings.community_top_k
        hits = await vector_search(
            query,
            embedder=self._embedder,
            graph_store=self._graph_store,
            vector_store=self._vector_store,
            collection=self._settings.community_collection,
            labels=[COMMUNITY_LABEL],
            limit=effective_limit,
            filters=filters,
            settings=self._settings,
        )
        if not hits:
            return []
        ids = [str(h.id) for h in hits]
        try:
            rows = await self._graph_store.execute_read(
                f"UNWIND $ids AS id MATCH (n:{NODE_IDENTITY_LABEL}:"
                f"{COMMUNITY_LABEL} {{id: id}}) RETURN n",
                {"ids": ids},
            )
        except Exception:
            return []
        by_id: dict[str, Community] = {}
        for row in rows:
            try:
                node = row.get("n", row) if isinstance(row, dict) else row
                community = _parse_community_node(node)
                if community is not None:
                    by_id[str(community.id)] = community
            except Exception:
                continue
        results: list[SearchResult] = []
        for hit in hits:
            try:
                community = by_id.get(str(hit.id))
                if community is not None:
                    results.append(
                        SearchResult(item=community, score=hit.score, method=self.name)
                    )
            except Exception:
                continue
        return results
