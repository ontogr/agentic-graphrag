"""Community-report enrichment: local-search-style budget-capped context."""

import logging
from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.common.data_models.community import Community
from agrag.common.data_models.search_result import SearchResult
from agrag.common.graph_rows import node_properties
from agrag.cypher.community_read import communities_for_entities_query
from agrag.graphdb.base import GraphStore
from agrag.observability import get_tracer, record_swallowed_exception
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.fusion import fuse
from agrag.retrieval.tracing import record_results


logger = logging.getLogger(__name__)


def _parse_community_node(node: object) -> Community | None:
    """Parse a GraphStore node row into a Community, or None on failure."""
    try:
        props = node_properties(node)
        node_id = props.get("id")
        if node_id is None:
            return None

        community = Community(
            id=UUID(str(node_id)),
            title=str(props.get("title", "")),
            summary=str(props.get("summary", "")),
            rating=float(props.get("rating", 0.0)),
            rating_explanation=str(props.get("rating_explanation", "")),
            findings=list(props.get("findings") or []),
            member_ids=[UUID(str(m)) for m in props.get("member_ids") or []],
            internal_weight=float(props.get("internal_weight", 0.0)),
        )
        embedding = props.get("embedding")
        if embedding is not None:
            community.embedding = list(embedding)
        return community
    except Exception:
        return None


async def expand_with_communities(
    fused: list[SearchResult],
    seed_ids: list[UUID],
    *,
    graph_store: GraphStore,
    top_k: int,
    filters: SearchFilters | None,
    rrf_k: int,
    tracer: Tracer | None = None,
) -> list[SearchResult]:
    """Fuse community reports overlapping seed entities into a result list.

    A convenience over ``community_context``. It looks up the communities
    that overlap ``seed_ids`` and fuses whatever comes back into ``fused``
    under a ``"community"`` key, so callers that already have a fused
    result list do not repeat the fetch-then-fuse pattern (or the
    error handling below).

    A community lookup that raises is recorded on the expansion span and
    swallowed rather than propagated. Community reports are enrichment on
    top of results that already exist, so a community-store failure must
    not discard them.

    Args:
        fused: The already-fused results to enrich. Returned unchanged
            when no community overlaps the seeds.
        seed_ids: The entity ids to look for overlapping communities.
        graph_store: Where the overlap lookup runs.
        top_k: The maximum number of communities to add.
        filters: Applied to the candidate community node. See
            ``community_context`` for what a scoped filter does and
            does not match. Community nodes carry no entity label and no
            document scope of their own, so a document-scoped or
            property-scoped caller gets no community enrichment at all.
            This matches a plain search. It is not an error.
        rrf_k: The reciprocal-rank-fusion constant, from
            ``RetrievalSettings.rrf_k``.
        tracer: Opens the expansion spans. None opens no recorded span.

    Returns:
        ``fused`` with the overlapping communities fused in, or ``fused``
        itself when there were none.
    """
    with get_tracer(tracer).start_as_current_span(
        "agrag.retrieval.community_expand",
        attributes={"agrag.seed_count": len(seed_ids), "agrag.top_k": top_k},
    ) as span:
        try:
            community_results = await community_context(
                seed_ids,
                graph_store=graph_store,
                top_k=top_k,
                filters=filters,
                tracer=tracer,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Community expansion failed; continuing: %s", exc)
            record_swallowed_exception(exc)
            record_results(span, fused)
            return fused
        if not community_results:
            record_results(span, fused)
            return fused
        expanded = fuse(
            {"methods": fused, "community": community_results},
            rrf_k=rrf_k,
            tracer=tracer,
        )
        if span.is_recording():
            span.set_attribute("agrag.added_count", len(expanded) - len(fused))
        record_results(span, expanded)
        return expanded


async def community_context(
    entity_ids: list[UUID],
    *,
    graph_store: GraphStore,
    top_k: int = 3,
    filters: SearchFilters | None = None,
    tracer: Tracer | None = None,
) -> list[SearchResult]:
    """Return the top-overlapping communities' reports for a set of entities.

    Ranks candidate communities by how many of entity_ids are their
    members (Microsoft GraphRAG's local-search pattern), then returns the
    top_k as SearchResults so they flow through the same Fusion/Ledger
    machinery as any other result.

    Args:
        entity_ids: The entity ids already found by a search's other
            retrieval methods.
        graph_store: Where the overlap lookup runs.
        top_k: The maximum number of communities to return. Zero or
            negative returns no results without querying.
        filters: Applied to the candidate community node via
            ``document_ids``/``properties`` (``to_cypher_where``); labels
            are not applied, since they check node labels and a Community
            node never carries an entity label. Community nodes carry no
            document or tenant scope of their own, so a filter naming a
            property Community nodes never have matches no communities --
            a document- or property-scoped search gets no community
            enrichment rather than one drawn from outside its scope.
        tracer: Opens the context span. None opens no recorded span.

    Returns:
        Up to top_k SearchResults wrapping Community items, highest overlap
        first. Empty when entity_ids is empty or no community overlaps.
    """
    if not entity_ids:
        return []
    if top_k <= 0:
        return []
    with get_tracer(tracer).start_as_current_span(
        "agrag.retrieval.community_context",
        attributes={"agrag.seed_count": len(entity_ids), "agrag.top_k": top_k},
    ) as span:
        where_clause, where_params = (
            SearchFilters(
                document_ids=filters.document_ids, properties=filters.properties
            ).to_cypher_where("c")
            if filters
            else ("", {})
        )
        rows = await graph_store.execute_read(
            communities_for_entities_query(where_clause),
            {
                "entity_ids": [str(e) for e in entity_ids],
                "job_id": None,
                "top_k": top_k,
                **where_params,
            },
        )
        results: list[SearchResult] = []
        for row in rows[:top_k]:
            try:
                community = _parse_community_node(row.get("c", row))
                if community is None:
                    continue
                results.append(
                    SearchResult(
                        item=community, score=float(row["overlap"]), method="community"
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        record_results(span, results)
        return results
