"""Community retriever: dense vector search over community reports."""

from opentelemetry.trace import Tracer

from agrag.common.data_models.community import COMMUNITY_LABEL, Community
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.observability import get_tracer, record_swallowed_exception
from agrag.retrieval.community_context import _parse_community_node
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.vector import vector_search
from agrag.retrieval.retrievers.base import Retriever
from agrag.retrieval.settings import RetrievalSettings
from agrag.retrieval.tracing import record_results, retrieval_span
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
        tracer: Tracer | None = None,
    ) -> None:
        """Construct a CommunityRetriever.

        Args:
            graph_store: Where community nodes live.
            embedder: Produces query vectors.
            vector_store: Optional VectorStore for hybrid search.
            settings: Retrieval configuration; defaults from environment.
            tracer: Opens the retriever and its children's spans. None
                opens no recorded span.
        """
        self._graph_store = graph_store
        self._embedder = embedder
        self._vector_store = vector_store
        self._settings = settings or RetrievalSettings()
        self._tracer = tracer

    async def retrieve(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        limit: int | None = None,
    ) -> list[SearchResult]:
        """Run community-report search and return loaded results.

        Args:
            query: The natural-language query text.
            filters: Constraints applied to the search.
            limit: Maximum results. None uses settings.community_top_k.
                Zero or negative returns no results without searching.
        """
        effective_limit = limit if limit is not None else self._settings.community_top_k
        with retrieval_span(
            self._tracer,
            "agrag.retrieval.community",
            query=query,
            filters=filters,
            attributes={"agrag.limit": effective_limit},
        ) as span:
            if effective_limit <= 0:
                record_results(span, [])
                return []
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
                tracer=self._tracer,
            )
            if not hits:
                record_results(span, [])
                return []
            ids = [str(h.id) for h in hits]
            with get_tracer(self._tracer).start_as_current_span(
                "agrag.retrieval.load_communities",
                attributes={"agrag.requested_count": len(hits)},
            ) as load:
                try:
                    rows = await self._graph_store.execute_read(
                        f"UNWIND $ids AS id MATCH (n:{NODE_IDENTITY_LABEL}:"
                        f"{COMMUNITY_LABEL} {{id: id}}) "
                        "WHERE n._pending_job_id IS NULL RETURN n",
                        {"ids": ids},
                    )
                except Exception as exc:  # noqa: BLE001
                    record_swallowed_exception(exc)
                    record_results(span, [])
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
                if load.is_recording():
                    load.set_attribute("agrag.loaded_count", len(by_id))
            results: list[SearchResult] = []
            for hit in hits:
                try:
                    community = by_id.get(str(hit.id))
                    if community is not None:
                        results.append(
                            SearchResult(
                                item=community, score=hit.score, method=self.name
                            )
                        )
                except Exception:
                    continue
            record_results(span, results)
            return results
