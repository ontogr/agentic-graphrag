"""Shared vector search helper for GraphStore and VectorStore."""

import asyncio
from collections.abc import Sequence

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
    collection: str,
    labels: Sequence[str],
    limit: int,
    filters: SearchFilters | None,
    settings: RetrievalSettings,
) -> list[VectorHit]:
    """Embed query and search on whichever store is configured.

    When vector_store is set, runs hybrid_search there (dense plus
    BM25, blended by settings.hybrid_alpha) against ``collection``.
    When it is None, runs GraphStore's native vector_search once per
    label in ``labels`` and merges the hits, ignoring hybrid_alpha
    since that path is dense-only. One native vector index exists per
    label, so a search over several labels is several searches.

    Args:
        query: The natural-language query text to embed.
        embedder: Produces the query's dense vector.
        graph_store: The GraphStore-native fallback target.
        vector_store: The optional VectorStore target; None selects
            the GraphStore-native path.
        collection: The VectorStore collection name.
        labels: The node labels to search on the GraphStore-native
            path, each backed by its own vector index.
        limit: Maximum hits to return.
        filters: Constraints translated to whichever store is
            searched. Labels are a payload key on the VectorStore
            path and choose the searched indexes on the native path,
            so they are not sent as node property filters.
        settings: Supplies hybrid_alpha for the VectorStore path.

    Returns:
        Ranked VectorHits, from whichever store was searched.

    Raises:
        ValueError: The native path was selected with no labels to
            search.
    """
    query_vector = await embedder.embed_one(query)

    if vector_store is not None:
        payload_filters = filters.to_payload_filter() if filters else None
        return await vector_store.hybrid_search(
            collection,
            query_vector,
            query,
            limit=limit,
            filters=payload_filters or None,
            alpha=settings.hybrid_alpha,
        )

    if not labels:
        raise ValueError(
            "Native vector search needs at least one label. Set "
            "RETRIEVAL_ENTITY_LABELS or pass entity_labels to SearchEngine."
        )

    property_filters = filters.to_property_filter() if filters else None
    per_label = await asyncio.gather(
        *(
            graph_store.vector_search(
                label=label,
                vector_property="embedding",
                query_vector=query_vector,
                limit=limit,
                filters=property_filters or None,
            )
            for label in labels
        )
    )
    hits = [hit for label_hits in per_label for hit in label_hits]
    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits[:limit]
