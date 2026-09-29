"""BFS retriever: graph traversal from seed entity ids."""

from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.relations import TraversalDirection, bfs_expand_query
from agrag.graphdb.base import GraphStore
from agrag.ingestion._ingest_pipeline import _parse_entity_node
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.identity import resolve_entity
from agrag.retrieval.retrievers.base import Retriever
from agrag.retrieval.settings import RetrievalSettings
from agrag.retrieval.tracing import record_results, retrieval_span


class BFSRetriever(Retriever):
    """Graph traversal from seed entity ids.

    Takes seed entity ids (from a prior EntityRetriever call, or
    supplied directly), runs bfs_expand_query, and hydrates the
    returned entities through resolve_entity and relations directly.
    Degree-capped by RetrievalSettings.traversal_limit.
    """

    name = "bfs"

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        settings: RetrievalSettings | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        """Construct a BFSRetriever.

        Args:
            graph_store: The graph store to traverse.
            settings: Retrieval configuration; defaults from
                environment.
            tracer: Opens the retriever and its children's spans. None
                opens no recorded span.
        """
        self._graph_store = graph_store
        self._settings = settings or RetrievalSettings()
        self._tracer = tracer

    async def retrieve(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        limit: int | None = None,
        seed_ids: list[UUID] | None = None,
        depth: int | None = None,
        direction: TraversalDirection = "both",
    ) -> list[SearchResult]:
        """Run BFS expansion from seed entity ids.

        Args:
            query: The natural-language query text (unused for BFS,
                kept for interface consistency).
            filters: Constraints applied to traversal. relation_types
                restrict which relationships the traversal crosses;
                property filters, document_ids, and labels restrict
                returned neighbor nodes.
            limit: Maximum results. None uses traversal_limit.
            seed_ids: The entity ids to expand from. If None, BFS
                returns empty.
            depth: BFS hops. None uses
                RetrievalSettings.traversal_depth.
            direction: Which way a hop walks each relationship,
                relative to the seed entity. Defaults to ``"both"``.

        Returns:
            SearchResults with entities and relations found via BFS.
        """
        effective_limit = limit if limit is not None else self._settings.traversal_limit
        effective_depth = depth if depth is not None else self._settings.traversal_depth
        with retrieval_span(
            self._tracer,
            "agrag.retrieval.bfs",
            query=query,
            filters=filters,
            attributes={
                "agrag.seed_count": len(seed_ids) if seed_ids else 0,
                "agrag.depth": effective_depth,
                "agrag.direction": direction,
                "agrag.limit": effective_limit,
            },
        ) as span:
            if not seed_ids:
                record_results(span, [])
                return []

            bfs_query, filter_params = bfs_expand_query(
                depth=effective_depth,
                limit=effective_limit,
                filters=(
                    SearchFilters(properties=filters.properties).to_property_filter()
                    if filters
                    else None
                ),
                relation_types=filters.relation_types if filters else None,
                direction=direction,
                document_ids=filters.document_ids if filters else None,
                labels=filters.labels if filters else None,
            )
            params = {
                "seed_ids": [str(sid) for sid in seed_ids],
                "job_id": None,
                **filter_params,
            }
            if filters and filters.document_ids:
                params["document_ids"] = filters.document_ids

            rows = await self._graph_store.execute_read(bfs_query, params)

            results: list[SearchResult] = []
            seen_ids: set[UUID] = set()

            for row in rows:
                neighbor = (
                    row.get("neighbor")
                    if isinstance(row, dict) and "neighbor" in row
                    else row
                )
                entity = _parse_entity_node(neighbor)
                if entity is None:
                    continue

                # Resolve through merged_into if needed. A neighbour that
                # cannot be resolved is skipped without a record: a row the
                # caller never sees is not a step that fell back.
                try:
                    entity = await resolve_entity(
                        self._graph_store, entity.id, tracer=self._tracer
                    )
                except (ValueError, Exception):
                    continue

                if entity.id in seen_ids:
                    continue
                seen_ids.add(entity.id)

                results.append(
                    SearchResult(
                        item=entity,
                        score=1.0,
                        method=self.name,
                    )
                )

            record_results(span, results)
            return results
