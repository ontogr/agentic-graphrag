"""Entity retriever: dense vector search over entities."""

from collections.abc import Sequence

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.entities import hydrate_entities_by_id_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.identity import resolve_entity
from agrag.retrieval.methods.vector import vector_search
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

    async def retrieve(
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

        Returns:
            Ranked SearchResults with resolved entity ids.

        Raises:
            ValueError: Native search was selected and neither the
                filter nor the configuration names an entity label.
        """
        effective_limit = limit or self._settings.entity_top_k
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
        if not hits:
            return []
        ids = [str(h.id) for h in hits]
        entities_by_id: dict[str, Entity] = {}
        try:
            rows = await self._graph_store.execute_read(
                hydrate_entities_by_id_query(), {"ids": ids}
            )
            from agrag.ingestion.graph import _parse_entity_node  # noqa: PLC0415

            for row in rows:
                try:
                    node = row.get("n") if isinstance(row, dict) and "n" in row else row
                    ent = _parse_entity_node(node)
                    if ent is None:
                        ent = _parse_entity_node(row)  # type: ignore[arg-type]
                    if ent is not None:
                        entities_by_id[str(ent.id)] = ent
                except Exception:
                    continue
        except Exception:
            entities_by_id = {}
        results: list[SearchResult] = []
        for hit in hits:
            try:
                entity: Entity | None = entities_by_id.get(str(hit.id))
                if entity is None:
                    try:
                        entity = await resolve_entity(self._graph_store, hit.id)
                    except (ValueError, Exception):
                        continue
                results.append(
                    SearchResult(item=entity, score=hit.score, method=self.name)
                )
            except (ValueError, Exception):
                continue
        return results
