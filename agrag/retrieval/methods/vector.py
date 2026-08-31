"""Shared vector search helper for GraphStore and VectorStore."""

from agrag.common.data_models.vector_record import VectorHit
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


async def vector_search(
    query: str,
    *,
    embedder: Embedder,
    graph_store: GraphStore,
    vector_store: VectorStore | None,
    label_or_collection: str,
    limit: int,
    filters: SearchFilters | None,
    settings: RetrievalSettings,
) -> list[VectorHit]:
    """Embed query and search on whichever store is configured.

    When vector_store is set, runs hybrid_search there (dense plus
    BM25, blended by settings.hybrid_alpha) against
    label_or_collection as a VectorStore collection name. When it is
    None, runs GraphStore's native vector_search instead, treating
    label_or_collection as a node label and ignoring hybrid_alpha,
    since that path is dense-only.

    Args:
        query: The natural-language query text to embed.
        embedder: Produces the query's dense vector.
        graph_store: The GraphStore-native fallback target.
        vector_store: The optional VectorStore target; None selects
            the GraphStore-native path.
        label_or_collection: A node label (GraphStore path) or
            collection name (VectorStore path).
        limit: Maximum hits to return.
        filters: Constraints translated to whichever store is
            searched.
        settings: Supplies hybrid_alpha for the VectorStore path.

    Returns:
        Ranked VectorHits, from whichever store was searched.
    """
    query_vector = await embedder.embed_one(query)
    payload_filters = filters.to_payload_filter() if filters else None

    if vector_store is not None:
        return await vector_store.hybrid_search(
            label_or_collection,
            query_vector,
            query,
            limit=limit,
            filters=payload_filters or None,
            alpha=settings.hybrid_alpha,
        )

    return await graph_store.vector_search(
        label=label_or_collection,
        vector_property="embedding",
        query_vector=query_vector,
        limit=limit,
        filters=payload_filters or None,
    )
