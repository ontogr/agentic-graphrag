"""Shared vector search helper over the GraphStore native vector indexes."""

import asyncio
from collections.abc import Sequence
from typing import Any

from opentelemetry.trace import Span, Tracer

from agrag.common.data_models.vector_record import VectorHit, VectorKind
from agrag.cypher.vector_hits import external_hits_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.observability import get_tracer
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.tracing import filters_json
from agrag.vectordb.base import VectorStore
from agrag.vectordb.kinds import kind_for_label


async def vector_search(
    query: str,
    *,
    embedder: Embedder,
    graph_store: GraphStore,
    labels: Sequence[str],
    limit: int,
    filters: SearchFilters | None,
    query_vector: Sequence[float] | None = None,
    vector_store: VectorStore | None = None,
    hybrid: bool = False,
    alpha: float = 0.5,
    tracer: Tracer | None = None,
) -> list[VectorHit]:
    """Embed query and run GraphStore's native vector search for each label.

    Native vector search uses one index per label. An external store groups
    labels by vector kind and joins candidates back to committed graph nodes.

    The vector query excludes records an in-flight Cutover Job wrote, so a
    caller never receives an uncommitted job's node or vector.

    Args:
        query: The natural-language query text to embed.
        embedder: Produces the query's dense vector.
        graph_store: Runs the native vector search.
        labels: The node labels to search, each backed by its own vector index.
        limit: Maximum hits to return.
        filters: Constraints applied as node property filters. Labels choose
            the searched indexes, so they are not sent as property filters.
        query_vector: Precomputed query embedding. None embeds ``query``.
        vector_store: Optional external store for vector candidates.
        hybrid: Use the store's dense and lexical hybrid search when available.
        alpha: Dense weight for external hybrid search.
        tracer: Opens the search span. None opens no recorded span.

    Returns:
        Ranked VectorHits.

    Raises:
        ValueError: No labels were given to search.
    """
    if not labels:
        raise ValueError("Native vector search needs at least one label.")
    with get_tracer(tracer).start_as_current_span(
        "agrag.retrieval.vector_search"
    ) as span:
        if span.is_recording():
            span.set_attributes(
                {
                    "agrag.labels": list(labels),
                    "agrag.limit": limit,
                    "agrag.filters": filters_json(filters),
                    "agrag.store": (
                        vector_store.name
                        if vector_store is not None
                        else "graph_native"
                    ),
                }
            )

        dense_vector = query_vector
        if dense_vector is None:
            dense_vector = await embedder.embed_one(query)

        property_filters = filters.to_property_filter() if filters else None
        if vector_store is not None:
            hits = await _external_search(
                query,
                vector=dense_vector,
                graph_store=graph_store,
                vector_store=vector_store,
                labels=labels,
                limit=limit,
                filters=property_filters,
                hybrid=hybrid,
                alpha=alpha,
            )
        else:
            per_label = await asyncio.gather(
                *(
                    graph_store.vector_search(
                        label=label,
                        vector_property="embedding",
                        query_vector=dense_vector,
                        limit=limit,
                        filters=property_filters or None,
                    )
                    for label in labels
                )
            )
            hits = [hit for label_hits in per_label for hit in label_hits]
            hits.sort(key=lambda hit: hit.score, reverse=True)
            hits = hits[:limit]

        _record_hits(span, hits)
        return hits


async def _external_search(
    query: str,
    *,
    vector: Sequence[float],
    graph_store: GraphStore,
    vector_store: VectorStore,
    labels: Sequence[str],
    limit: int,
    filters: dict[str, Any] | None,
    hybrid: bool,
    alpha: float,
) -> list[VectorHit]:
    """Fetch and graph-validate external candidates until enough hits remain."""
    kinds = {kind_for_label(label) for label in labels}
    if len(kinds) != 1:
        raise ValueError("External vector search requires one vector kind")
    kind = next(iter(kinds))
    search_labels = list(labels) if kind is VectorKind.ENTITY else None
    fetch = min(limit * 4, vector_store.max_results)
    statement, params = external_hits_query(filters, kind=kind)
    hits: list[VectorHit] = []
    while True:
        if hybrid:
            raw_hits = await vector_store.hybrid_search(
                kind,
                vector,
                query,
                limit=fetch,
                alpha=alpha,
                labels=search_labels,
            )
        else:
            raw_hits = await vector_store.search(
                kind, vector, limit=fetch, labels=search_labels
            )
        if not raw_hits:
            return hits[:limit]
        rows = await graph_store.execute_read(
            statement,
            {
                **params,
                "rows": [
                    {"id": str(hit.id), "score": hit.score, "rank": rank}
                    for rank, hit in enumerate(raw_hits)
                ],
            },
        )
        hits = [
            VectorHit(id=row["id"], score=float(row["score"]), payload={})
            for row in rows
        ]
        if (
            len(hits) >= limit
            or len(raw_hits) < fetch
            or fetch == vector_store.max_results
        ):
            return hits[:limit]
        fetch = min(fetch * 4, vector_store.max_results)


def _record_hits(span: Span, hits: Sequence[VectorHit]) -> None:
    """Add returned hit details to the active trace span."""
    if not span.is_recording():
        return
    span.set_attribute("agrag.hit_count", len(hits))
    if hits:
        span.set_attribute("agrag.hit_ids", [str(hit.id) for hit in hits])
        span.set_attribute("agrag.hit_scores", [hit.score for hit in hits])
