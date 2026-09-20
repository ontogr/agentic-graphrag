"""Entity resolution and seeded traversal, callable without a SearchEngine.

Free functions, not methods, for the same reason ``vector.py``'s
``vector_search`` is: the retrieval building blocks stay independently
testable and ``SearchEngine`` stays an orchestrator over them.
"""

import logging
from collections.abc import Sequence
from uuid import UUID

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.relations import TraversalDirection, relationship_types_from_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.retrieval.community_context import expand_with_communities
from agrag.retrieval.errors import ScopeDeniedError
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.retrievers.bfs import BFSRetriever
from agrag.retrieval.retrievers.entity import EntityRetriever
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


logger = logging.getLogger(__name__)


def extract_entity_ids(results: list[SearchResult]) -> list[UUID]:
    """Return raw entity ids from results, preserving order.

    Used for BFS seeds and node-distance reranking. Keeps the
    first-seen id of each entity so the fusion ranking is respected. A
    ResolvedEntity contributes its raw member ids, since graph
    traversal and distance run over raw entity nodes: a resolved
    entity's own id names no ``_AgragNode`` an entity traversal can
    start from, so seeding with it would silently match nothing.
    Chunks and other non-entity result items are skipped.

    Args:
        results: The result list to read entity ids from.

    Returns:
        Each entity id once, in first-seen order.
    """
    seen: set[UUID] = set()
    ids: list[UUID] = []
    for result in results:
        if isinstance(result.item, Entity):
            item_ids: list[UUID] = [result.item.id]
        elif isinstance(result.item, ResolvedEntity):
            item_ids = result.item.member_ids
        else:
            continue
        for item_id in item_ids:
            if item_id not in seen:
                seen.add(item_id)
                ids.append(item_id)
    return ids


async def find_entity(
    name: str,
    *,
    graph_store: GraphStore,
    embedder: Embedder,
    vector_store: VectorStore | None,
    settings: RetrievalSettings,
    entity_labels: Sequence[str],
    filters: SearchFilters | None = None,
) -> SearchResult | None:
    """Resolve a named entity to its top search hit, or None.

    Runs one entity search and returns its best result, which callers
    keep whole rather than unwrapping: the item renders as evidence,
    and the result itself is what :func:`extract_entity_ids` can turn
    into traversal seeds.

    Args:
        name: The entity name (or description) to resolve.
        graph_store: Backs entity search when vector_store is absent.
        embedder: Produces the query vector.
        vector_store: Optional vector store for hybrid search.
        settings: Retrieval configuration.
        entity_labels: The labels native entity search runs against by
            default, one vector index each.
        filters: Scope to resolve within. Labels, document ids, and
            ``properties`` are projected through, matching the
            projection a plain search's own entity step applies; a
            ``filters.labels`` value replaces ``entity_labels`` rather
            than narrowing within it, so a scope carrying only
            unrelated fields must not be mistaken for a deliberate
            label override. An entity that exists only outside this
            scope resolves to None, the same as one that does not
            exist.

    Returns:
        The top-ranked SearchResult, or None when nothing matched.
    """
    projected = (
        SearchFilters(
            labels=filters.labels,
            document_ids=filters.document_ids,
            properties=filters.properties,
        )
        if filters and (filters.labels or filters.document_ids or filters.properties)
        else None
    )
    retriever = EntityRetriever(
        graph_store=graph_store,
        embedder=embedder,
        vector_store=vector_store,
        settings=settings,
        entity_labels=entity_labels,
    )
    results = await retriever.retrieve(name, filters=projected, limit=1)
    return results[0] if results else None


async def traverse(
    seed: SearchResult,
    *,
    graph_store: GraphStore,
    settings: RetrievalSettings,
    relation_type: str | None = None,
    direction: TraversalDirection = "both",
    depth: int = 1,
    limit: int = 10,
    community_expand: bool = False,
    community_top_k: int = 3,
    filters: SearchFilters | None = None,
) -> list[SearchResult]:
    """Expand one resolved entity into its neighbours.

    Args:
        seed: The resolved entity to expand from. A ResolvedEntity seed
            expands from its raw member ids, never its own id.
        graph_store: The graph to traverse.
        settings: Retrieval configuration, carrying the BFS defaults
            this call's explicit arguments override.
        relation_type: Restrict the traversal to this single
            relationship type. None crosses every type the scope
            allows.
        direction: Which way a hop walks each relationship, relative to
            the seed entity.
        depth: Maximum hops. Clamped by the query builder.
        limit: Maximum neighbours returned.
        community_expand: Also fuse in the reports of communities
            overlapping the seed, ranked by membership overlap.
        community_top_k: Maximum community reports to add when
            ``community_expand`` is set.
        filters: Scope for the traversal. ``relation_types`` here is an
            immutable allowlist the caller set, not something a
            ``relation_type`` argument can widen: a request outside it
            is refused without querying the graph. ``properties``
            applies to neighbour nodes. ``document_ids`` is deliberately
            not forwarded, since entities are not document-scoped the
            way chunks are.

    Returns:
        The neighbouring entities, deduplicated, highest-ranked first,
        with any requested community reports fused in.

    Raises:
        ScopeDeniedError: relation_type names a type the caller's scope
            does not permit.
    """
    seed_ids = extract_entity_ids([seed])
    base_relation_types = list(filters.relation_types) if filters else []
    allowed_relation_types = _intersect_relation_types(
        base_relation_types, relation_type
    )
    if relation_type is not None and base_relation_types and not allowed_relation_types:
        raise ScopeDeniedError(
            f"relation type {relation_type!r} is outside the permitted "
            f"relation types {base_relation_types!r}"
        )

    retriever = BFSRetriever(graph_store=graph_store, settings=settings)
    results = await retriever.retrieve(
        query="",
        filters=SearchFilters(
            relation_types=allowed_relation_types,
            properties=filters.properties if filters else {},
        ),
        seed_ids=seed_ids,
        depth=depth,
        limit=limit,
        direction=direction,
    )

    if not community_expand:
        return results
    return await expand_with_communities(
        results,
        seed_ids,
        graph_store=graph_store,
        top_k=community_top_k,
        filters=filters,
        rrf_k=settings.rrf_k,
    )


async def list_relationship_types(
    seed: SearchResult,
    *,
    graph_store: GraphStore,
    relation_type_filter: str | None = None,
    filters: SearchFilters | None = None,
) -> list[str]:
    """List the relationship types directly attached to a resolved entity.

    Depth-1 only: it reports what is attached to the seed, never what
    lies past it. Any relation type allowlist in ``filters`` is applied
    before the query runs.

    Args:
        seed: The resolved entity to read attached types from.
        graph_store: The graph to read.
        relation_type_filter: Only report this type, if present.
        filters: Scope that limits which relationship types are visible.

    Returns:
        The distinct attached relationship type names.
    """
    if (
        relation_type_filter
        and filters
        and filters.relation_types
        and relation_type_filter not in filters.relation_types
    ):
        raise ScopeDeniedError(
            f"relation type {relation_type_filter!r} is outside the permitted "
            f"relation types {filters.relation_types!r}"
        )
    seed_ids = extract_entity_ids([seed])
    query = relationship_types_from_query(
        relation_types=(
            [relation_type_filter]
            if relation_type_filter
            else filters.relation_types
            if filters and filters.relation_types
            else None
        )
    )
    rows = await graph_store.execute_read(
        query, {"seed_ids": [str(seed_id) for seed_id in seed_ids]}
    )
    types: list[str] = []
    for row in rows:
        rel_type = row.get("rel_type") if isinstance(row, dict) else None
        if isinstance(rel_type, str) and rel_type not in types:
            types.append(rel_type)
    return types


def _intersect_relation_types(base: list[str], requested: str | None) -> list[str]:
    """Return the relation types a traversal may actually cross.

    An empty ``base`` means the caller set no allowlist, so a request
    passes through as given. A non-empty ``base`` is an authorization
    boundary: a request outside it is not permitted, and an empty
    return means the traversal must not run.

    Args:
        base: The caller's allowlist of relation types, empty when the
            caller set none.
        requested: The single relation type this call asked for, or
            None when the call asked for no restriction.

    Returns:
        The relation types to traverse, or an empty list when the
        request is outside the caller's allowlist.
    """
    if not base:
        return [requested] if requested else []
    if requested is None:
        return list(base)
    if requested in base:
        return [requested]
    return []
