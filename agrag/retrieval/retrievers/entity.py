"""Entity retriever: dense vector search over entities."""

from collections.abc import Sequence
from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.search_result import SearchResult
from agrag.common.data_models.vector_record import VectorHit
from agrag.common.validation import MAX_SEARCH_LIMIT
from agrag.cypher.relations import entities_in_documents_query
from agrag.cypher.resolution_read import fetch_active_resolved_member_ids_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.graphdb.entities import load_entities
from agrag.observability import get_tracer
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.vector import vector_search
from agrag.retrieval.resolved_entities import load_resolved_entities
from agrag.retrieval.retrievers.base import Retriever
from agrag.retrieval.settings import RetrievalSettings
from agrag.retrieval.tracing import record_results, retrieval_span
from agrag.vectordb.base import VectorStore


class EntityRetriever(Retriever):
    """Dense entity search via vector similarity.

    Embeds the query, searches via the GraphStore-native or
    VectorStore path, then loads every hit from the graph. A hit that
    no longer exists in the graph is dropped.

    The native path searches one vector index per entity label, so it
    needs the labels ingestion provisioned indexes for: the label
    filter when the caller sets one, otherwise ``entity_labels``.
    """

    name = "entity"

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        embedder: Embedder,
        vector_store: VectorStore | None = None,
        settings: RetrievalSettings | None = None,
        entity_labels: Sequence[str] | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        """Construct an EntityRetriever.

        Args:
            graph_store: Backs entity search when vector_store is
                absent.
            embedder: Produces query vectors.
            vector_store: Optional VectorStore for hybrid search.
            settings: Retrieval configuration. Defaults from
                environment.
            entity_labels: The schema entity labels native search runs
                against. None uses settings.entity_labels.
            tracer: Opens the retriever and its children spans. None
                opens no recorded span.
        """
        self._graph_store = graph_store
        self._embedder = embedder
        self._vector_store = vector_store
        self._settings = settings or RetrievalSettings()
        self._entity_labels = (
            list(entity_labels)
            if entity_labels is not None
            else list(self._settings.entity_labels)
        )
        self._tracer = tracer

    async def retrieve(  # noqa: PLR0912, PLR0915
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        limit: int | None = None,
    ) -> list[SearchResult]:
        """Run entity search and return loaded results.

        Args:
            query: The natural-language query text.
            filters: Constraints applied to the search.
            limit: Maximum results. None uses settings.entity_top_k.
                Zero or negative returns no results without searching.

        Returns:
            Ranked SearchResults with resolved entity ids. The list is
                empty when the limit is not positive, or when the search ran and
                found nothing.

        Raises:
            ValueError: Native search was selected and neither the
                filter nor the configuration names an entity label, or a
                stored entity node cannot be parsed.
            Exception: Any embedding, vector search, or graph read
                failure propagates, so a failed search is not mistaken
                for an empty one.
        """
        effective_limit = limit if limit is not None else self._settings.entity_top_k
        with retrieval_span(
            self._tracer,
            "agrag.retrieval.entity",
            query=query,
            filters=filters,
            attributes={"agrag.limit": effective_limit},
        ) as span:
            if effective_limit <= 0:
                record_results(span, [])
                return []
            labels = (
                filters.labels if filters and filters.labels else self._entity_labels
            )
            allowed_ids = await self._allowed_entity_ids(filters)
            query_vector = (
                await self._embedder.embed_one(query)
                if allowed_ids is not None
                else None
            )
            search_filters = (
                filters.model_copy(update={"document_ids": []})
                if filters and filters.document_ids
                else filters
            )
            raw_candidate_limit = effective_limit
            hits: list[VectorHit] | None = None
            active_member_ids: set[UUID] | None = None
            passes = 0
            with get_tracer(self._tracer).start_as_current_span(
                "agrag.retrieval.entity_search",
                attributes={"agrag.limit": effective_limit},
            ) as entity_search:
                while True:
                    passes += 1
                    candidate_hits = await vector_search(
                        query,
                        embedder=self._embedder,
                        graph_store=self._graph_store,
                        vector_store=self._vector_store,
                        collection=self._settings.entity_collection,
                        labels=labels,
                        limit=raw_candidate_limit,
                        filters=search_filters,
                        settings=self._settings,
                        query_vector=query_vector,
                        tracer=self._tracer,
                    )
                    candidate_active_member_ids = (
                        await self._active_resolved_member_ids(
                            [hit.id for hit in candidate_hits]
                        )
                        if allowed_ids
                        else set()
                    )
                    hits = candidate_hits
                    if allowed_ids:
                        active_member_ids = candidate_active_member_ids
                    in_scope_count = (
                        sum(
                            str(hit.id) in allowed_ids
                            and hit.id not in candidate_active_member_ids
                            for hit in hits
                        )
                        if allowed_ids
                        else 0
                    )
                    if (
                        not allowed_ids
                        or len(hits) < raw_candidate_limit
                        or in_scope_count >= effective_limit
                        or raw_candidate_limit >= MAX_SEARCH_LIMIT
                    ):
                        break
                    raw_candidate_limit = min(raw_candidate_limit * 2, MAX_SEARCH_LIMIT)
                if entity_search.is_recording():
                    entity_search.set_attribute("agrag.passes", passes)
                    entity_search.set_attribute(
                        "agrag.hit_count", len(hits) if hits else 0
                    )
            results: list[SearchResult] = []
            if hits:
                if allowed_ids is not None:
                    hits = [hit for hit in hits if str(hit.id) in allowed_ids]
                entities_by_id = await load_entities(
                    self._graph_store,
                    [hit.id for hit in hits],
                    tracer=self._tracer,
                )
                if active_member_ids is None:
                    active_member_ids = await self._active_resolved_member_ids(
                        [hit.id for hit in hits]
                    )
                for hit in hits:
                    if hit.id in active_member_ids:
                        continue
                    entity = entities_by_id.get(hit.id)
                    if entity is None:
                        continue
                    results.append(
                        SearchResult(item=entity, score=hit.score, method=self.name)
                    )

            resolved_limit = (
                limit if limit is not None else self._settings.resolved_entity_top_k
            )
            resolved_filters = (
                filters.model_copy(update={"document_ids": []})
                if filters and filters.document_ids
                else filters
            )
            if filters is not None and filters.labels:
                resolved_filters = SearchFilters(
                    relation_types=filters.relation_types,
                    document_ids=[],
                    properties={**filters.properties, "label": filters.labels},
                )
            resolved_candidate_limit = resolved_limit
            resolved_hits: list[VectorHit] = []
            resolved_by_id: dict[UUID, ResolvedEntity] = {}
            with get_tracer(self._tracer).start_as_current_span(
                "agrag.retrieval.resolved_entity_search",
                attributes={"agrag.limit": resolved_limit},
            ) as resolved_search:
                resolved_passes = 0
                while True:
                    resolved_passes += 1
                    candidate_hits = await vector_search(
                        query,
                        embedder=self._embedder,
                        graph_store=self._graph_store,
                        vector_store=self._vector_store,
                        collection=self._settings.resolved_entity_collection,
                        labels=("ResolvedEntity",),
                        limit=resolved_candidate_limit,
                        filters=resolved_filters,
                        settings=self._settings,
                        query_vector=query_vector,
                        tracer=self._tracer,
                    )
                    candidate_by_id = await load_resolved_entities(
                        self._graph_store,
                        [hit.id for hit in candidate_hits],
                        tracer=self._tracer,
                    )
                    in_scope_count = (
                        sum(
                            entity is not None
                            and (
                                not filters
                                or not filters.labels
                                or entity.label in filters.labels
                            )
                            and any(
                                str(member_id) in allowed_ids
                                for member_id in entity.member_ids
                            )
                            for hit in candidate_hits
                            if (entity := candidate_by_id.get(hit.id)) is not None
                        )
                        if allowed_ids
                        else 0
                    )
                    resolved_hits = candidate_hits
                    resolved_by_id = candidate_by_id
                    if (
                        not allowed_ids
                        or len(resolved_hits) < resolved_candidate_limit
                        or in_scope_count >= resolved_limit
                        or resolved_candidate_limit >= MAX_SEARCH_LIMIT
                    ):
                        break
                    resolved_candidate_limit = min(
                        resolved_candidate_limit * 2, MAX_SEARCH_LIMIT
                    )
                if resolved_search.is_recording():
                    resolved_search.set_attribute("agrag.passes", resolved_passes)
                    resolved_search.set_attribute("agrag.hit_count", len(resolved_hits))
            results.extend(
                SearchResult(item=entity, score=hit.score, method=self.name)
                for hit in resolved_hits
                if (entity := resolved_by_id.get(hit.id)) is not None
                and (
                    not filters or not filters.labels or entity.label in filters.labels
                )
                and (
                    allowed_ids is None
                    or any(
                        str(member_id) in allowed_ids for member_id in entity.member_ids
                    )
                )
            )
            results.sort(key=lambda result: result.score, reverse=True)
            final = results[:effective_limit]
            record_results(span, final)
            return final

    async def _allowed_entity_ids(
        self, filters: SearchFilters | None
    ) -> set[str] | None:
        """Return entity ids mentioned by a document scope, when one exists."""
        if not filters or not filters.document_ids:
            return None
        with get_tracer(self._tracer).start_as_current_span(
            "agrag.retrieval.allowed_entity_ids"
        ) as span:
            rows = await self._graph_store.execute_read(
                entities_in_documents_query(),
                {
                    "document_ids": filters.document_ids,
                    "job_id": None,
                },
            )
            allowed = {
                str(row["id"])
                for row in rows
                if isinstance(row, dict) and row.get("id") is not None
            }
            if span.is_recording():
                span.set_attribute("agrag.document_count", len(filters.document_ids))
                span.set_attribute("agrag.entity_count", len(allowed))
            return allowed

    async def _active_resolved_member_ids(self, ids: list[UUID]) -> set[UUID]:
        """Return raw hit ids that active resolved entities supersede."""
        if not ids:
            return set()
        with get_tracer(self._tracer).start_as_current_span(
            "agrag.retrieval.active_member_ids",
            attributes={"agrag.requested_count": len(ids)},
        ) as span:
            rows = await self._graph_store.execute_read(
                fetch_active_resolved_member_ids_query(),
                {"ids": [str(item_id) for item_id in ids], "job_id": None},
            )
            superseded = {
                hit_id
                for row in rows
                if isinstance(row, dict)
                and (entity_id := row.get("entity_id")) is not None
                and (
                    hit_id := next(
                        (item_id for item_id in ids if str(item_id) == str(entity_id)),
                        None,
                    )
                )
                is not None
            }
            if span.is_recording():
                span.set_attribute("agrag.superseded_count", len(superseded))
            return superseded
