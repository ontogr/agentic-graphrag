"""Entity retriever: dense vector search over entities."""

from collections.abc import Sequence
from uuid import UUID

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.entities import hydrate_entities_by_id_query
from agrag.cypher.relations import entities_in_documents_query
from agrag.cypher.resolution_read import fetch_active_resolved_member_ids_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.identity import resolve_entity
from agrag.retrieval.methods.vector import vector_search
from agrag.retrieval.resolved_entities import hydrate_resolved_entities
from agrag.retrieval.retrievers.base import Retriever
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


class EntityRetriever(Retriever):
    """Dense entity search via vector similarity.

    Embeds the query, searches via the GraphStore-native or
    VectorStore path, then resolves every hit through
    ``resolve_entity`` so the caller can trust ``item.id`` is live.

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
    ) -> None:
        """Construct an EntityRetriever.

        Args:
            graph_store: Backs entity search when vector_store is
                absent.
            embedder: Produces query vectors.
            vector_store: Optional VectorStore for hybrid search.
            settings: Retrieval configuration; defaults from
                environment.
            entity_labels: The schema entity labels native search runs
                against. None uses settings.entity_labels.
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

    async def retrieve(  # noqa: PLR0912, PLR0915
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        limit: int | None = None,
    ) -> list[SearchResult]:
        """Run entity search and return hydrated results.

        Args:
            query: The natural-language query text.
            filters: Constraints applied to the search.
            limit: Maximum results. None uses settings.entity_top_k.
                Zero or negative returns no results without searching.

        Returns:
            Ranked SearchResults with resolved entity ids.

        Raises:
            ValueError: Native search was selected and neither the
                filter nor the configuration names an entity label.
        """
        effective_limit = limit if limit is not None else self._settings.entity_top_k
        if effective_limit <= 0:
            return []
        labels = filters.labels if filters and filters.labels else self._entity_labels
        hits = await vector_search(
            query,
            embedder=self._embedder,
            graph_store=self._graph_store,
            vector_store=self._vector_store,
            collection=self._settings.entity_collection,
            labels=labels,
            limit=effective_limit,
            filters=filters,
            settings=self._settings,
        )
        results: list[SearchResult] = []
        if hits:
            allowed_ids = await self._allowed_entity_ids(filters)
            if allowed_ids is not None:
                hits = [hit for hit in hits if str(hit.id) in allowed_ids]
            ids = [str(h.id) for h in hits]
            entities_by_id: dict[str, Entity] = {}
            try:
                rows = await self._graph_store.execute_read(
                    hydrate_entities_by_id_query(), {"ids": ids}
                )
                from agrag.ingestion.graph import _parse_entity_node  # noqa: PLC0415

                for row in rows:
                    try:
                        node = (
                            row.get("n")
                            if isinstance(row, dict) and "n" in row
                            else row
                        )
                        ent = _parse_entity_node(node)
                        if ent is None:
                            ent = _parse_entity_node(row)  # type: ignore[arg-type]
                        if ent is not None:
                            entities_by_id[str(ent.id)] = ent
                    except Exception:
                        continue
            except Exception:
                entities_by_id = {}
            active_member_ids = await self._active_resolved_member_ids(
                [hit.id for hit in hits]
            )
            for hit in hits:
                if hit.id in active_member_ids:
                    continue
                try:
                    entity: Entity | None = entities_by_id.get(str(hit.id))
                    if entity is None:
                        try:
                            entity = await resolve_entity(self._graph_store, hit.id)
                        except Exception:
                            continue
                    results.append(
                        SearchResult(item=entity, score=hit.score, method=self.name)
                    )
                except Exception:
                    continue

        resolved_limit = (
            limit if limit is not None else self._settings.resolved_entity_top_k
        )
        resolved_filters = filters
        if filters is not None and filters.labels:
            resolved_filters = SearchFilters(
                relation_types=filters.relation_types,
                document_ids=filters.document_ids,
                properties={**filters.properties, "label": filters.labels},
            )
        try:
            resolved_hits = await vector_search(
                query,
                embedder=self._embedder,
                graph_store=self._graph_store,
                vector_store=self._vector_store,
                collection=self._settings.resolved_entity_collection,
                labels=("ResolvedEntity",),
                limit=resolved_limit,
                filters=resolved_filters,
                settings=self._settings,
            )
            resolved_by_id = await hydrate_resolved_entities(
                self._graph_store, [hit.id for hit in resolved_hits]
            )
        except Exception:
            resolved_hits = []
            resolved_by_id = {}
        results.extend(
            SearchResult(item=entity, score=hit.score, method=self.name)
            for hit in resolved_hits
            if (entity := resolved_by_id.get(hit.id)) is not None
            and (not filters or not filters.labels or entity.label in filters.labels)
        )
        results.sort(key=lambda result: result.score, reverse=True)
        return results[:effective_limit]

    async def _allowed_entity_ids(
        self, filters: SearchFilters | None
    ) -> set[str] | None:
        """Return entity ids mentioned by a document scope, when one exists."""
        if not filters or not filters.document_ids:
            return None
        rows = await self._graph_store.execute_read(
            entities_in_documents_query(),
            {"document_ids": filters.document_ids},
        )
        return {
            str(row["id"])
            for row in rows
            if isinstance(row, dict) and row.get("id") is not None
        }

    async def _active_resolved_member_ids(self, ids: list[UUID]) -> set[UUID]:
        """Return raw hit ids that active resolved entities supersede."""
        if not ids:
            return set()
        try:
            rows = await self._graph_store.execute_read(
                fetch_active_resolved_member_ids_query(),
                {"ids": [str(item_id) for item_id in ids]},
            )
        except Exception:
            return set()
        return {
            hit_id
            for row in rows
            if isinstance(row, dict)
            and (entity_id := row.get("entity_id")) is not None
            and (
                hit_id := next(
                    (item_id for item_id in ids if str(item_id) == str(entity_id)), None
                )
            )
            is not None
        }
