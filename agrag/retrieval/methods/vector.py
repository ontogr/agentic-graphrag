"""Shared vector search helper over the GraphStore native vector indexes."""

import asyncio
from collections.abc import Sequence

from opentelemetry.trace import Tracer

from agrag.common.data_models.vector_record import VectorHit
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.observability import get_tracer
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.tracing import filters_json


async def vector_search(
    query: str,
    *,
    embedder: Embedder,
    graph_store: GraphStore,
    labels: Sequence[str],
    limit: int,
    filters: SearchFilters | None,
    query_vector: Sequence[float] | None = None,
    tracer: Tracer | None = None,
) -> list[VectorHit]:
    """Embed query and run GraphStore's native vector search for each label.

    One native vector index exists per label, so a search over several
    labels is several searches. The results are merged and ranked by score.

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
        tracer: Opens the search span. None opens no recorded span.

    Returns:
        Ranked VectorHits.

    Raises:
        ValueError: No labels were given to search.
    """
    if not labels:
        raise ValueError(
            "Native vector search needs at least one label. Set "
            "RETRIEVAL_ENTITY_LABELS or pass entity_labels to SearchEngine."
        )
    with get_tracer(tracer).start_as_current_span(
        "agrag.retrieval.vector_search"
    ) as span:
        if span.is_recording():
            span.set_attributes(
                {
                    "agrag.labels": list(labels),
                    "agrag.limit": limit,
                    "agrag.filters": filters_json(filters),
                }
            )

        dense_vector = query_vector
        if dense_vector is None:
            dense_vector = await embedder.embed_one(query)

        property_filters = filters.to_property_filter() if filters else None
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

        if span.is_recording():
            span.set_attribute("agrag.hit_count", len(hits))
            if hits:
                span.set_attribute("agrag.hit_ids", [str(hit.id) for hit in hits])
                span.set_attribute("agrag.hit_scores", [hit.score for hit in hits])
        return hits
