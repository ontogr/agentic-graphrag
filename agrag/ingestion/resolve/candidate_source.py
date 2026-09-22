"""Candidate generation for in-batch and persisted graph entities."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.vector_record import VectorHit
from agrag.cypher.entities import hydrate_entities_by_id_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.vector import vector_search
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


class CandidateSource(ABC):
    """Narrows which in-batch entity pairs resolution compares."""

    @abstractmethod
    async def candidates_for(
        self, index: int, entities: list[ExtractedEntity]
    ) -> list[int]:
        """Return indices worth comparing against ``entities[index]``."""


class GraphCandidateSource(CandidateSource):
    """Blocks by label in-batch; ANN-searches persisted entities globally."""

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        embedder: Embedder,
        vector_store: VectorStore | None = None,
        vector_collection: str = "",
        entity_labels: Sequence[str] = (),
        top_k: int = 50,
    ) -> None:
        """Create a candidate source backed by the configured graph indexes."""
        self.graph_store = graph_store
        self.embedder = embedder
        self.vector_store = vector_store
        self.vector_collection = vector_collection
        self.entity_labels = tuple(entity_labels)
        self.top_k = top_k

    async def candidates_for(
        self, index: int, entities: list[ExtractedEntity]
    ) -> list[int]:
        """Return every other mention sharing the indexed mention's label."""
        label = entities[index].label
        return [
            other_index
            for other_index, entity in enumerate(entities)
            if other_index != index and entity.label == label
        ]

    async def global_candidates_for(self, mention: ExtractedEntity) -> list[Entity]:
        """Return persisted entities found by the shared vector-search route.

        The GraphStore-native path's payload already carries the real node
        properties and is validated directly. The VectorStore path's payload
        only carries ``label`` and ``text`` (the embedding source text), so
        candidates are hydrated from the graph by hit id instead; a hit that
        fails to hydrate, for example a tombstoned or deleted node, is
        skipped rather than reconstructed from ``text``.
        """
        hits = await vector_search(
            mention.text,
            embedder=self.embedder,
            graph_store=self.graph_store,
            vector_store=self.vector_store,
            collection=self.vector_collection,
            labels=(mention.label,),
            limit=self.top_k,
            filters=SearchFilters(labels=[mention.label]),
            settings=RetrievalSettings(),
        )
        if not hits:
            return []
        if self.vector_store is None:
            entities: list[Entity] = []
            for hit in hits:
                payload = dict(hit.payload)
                payload.setdefault("id", hit.id)
                payload.setdefault("label", mention.label)
                if payload.get("label") != mention.label:
                    continue
                try:
                    entities.append(Entity.model_validate(payload))
                except Exception:  # malformed payloads are not candidates
                    continue
            return entities
        return await self._hydrate_hits(hits, mention.label)

    async def _hydrate_hits(
        self, hits: Sequence[VectorHit], label: str
    ) -> list[Entity]:
        """Hydrate VectorStore hits into real entities by graph id.

        Reconstructing the name from the payload's display text corrupts
        any name containing ":" (e.g. "Star Trek: Voyager"), so this fetches
        the actual nodes instead.
        """
        from agrag.ingestion._ingest_pipeline import _parse_entity_node  # noqa: PLC0415

        ids = [str(hit.id) for hit in hits]
        try:
            rows = await self.graph_store.execute_read(
                hydrate_entities_by_id_query(), {"ids": ids, "job_id": None}
            )
        except Exception:
            return []
        entities: list[Entity] = []
        for row in rows:
            try:
                node = row.get("n") if isinstance(row, dict) and "n" in row else row
                entity = _parse_entity_node(node)
                if entity is None:
                    entity = _parse_entity_node(row)  # type: ignore[arg-type]
                if entity is not None and entity.label == label:
                    entities.append(entity)
            except Exception:
                continue
        return entities


class PersistedCandidateSource(CandidateSource):
    """Supplies only candidate pairs between new mentions and raw graph entities."""

    def __init__(self, candidates_by_index: dict[int, list[int]]) -> None:
        """Create a source from mention-indexed persisted candidate indices."""
        self.candidates_by_index = candidates_by_index

    async def candidates_for(
        self, index: int, entities: list[ExtractedEntity]
    ) -> list[int]:
        """Return persisted candidates for a newly extracted mention."""
        return self.candidates_by_index.get(index, [])


async def persisted_candidate_indices(
    mentions: list[ExtractedEntity],
    entities: list[Entity],
    *,
    source: GraphCandidateSource,
    fallback_limit: int = 128,
) -> dict[int, list[int]]:
    """Return ANN candidate indices, with a bounded exhaustive fallback.

    The fallback only applies when no indexed candidates are available. It
    keeps first-time and small-graph consolidation deterministic without
    returning to an unbounded pairwise scan for established graphs.
    """
    index_by_id = {entity.id: index for index, entity in enumerate(entities)}
    candidates_by_index: dict[int, list[int]] = {}
    for index, mention in enumerate(mentions):
        try:
            candidates = await source.global_candidates_for(mention)
        except Exception:  # noqa: BLE001
            continue
        candidate_indices = sorted(
            {
                candidate_index
                for candidate in candidates
                if (candidate_index := index_by_id.get(candidate.id)) is not None
                and candidate_index != index
                and entities[candidate_index].label == mention.label
            }
        )
        if candidate_indices:
            candidates_by_index[index] = candidate_indices
    if candidates_by_index or len(entities) > fallback_limit:
        return candidates_by_index
    return {
        index: [
            candidate_index
            for candidate_index, entity in enumerate(entities)
            if candidate_index != index and entity.label == mention.label
        ]
        for index, mention in enumerate(mentions)
    }


async def exact_match_lookup(
    mentions: list[ExtractedEntity], *, graph_store: GraphStore
) -> dict[int, Entity]:
    """Return persisted exact matches, including resolved tombstone aliases."""
    from agrag.ingestion._ingest_pipeline import _global_exact_match  # noqa: PLC0415

    return await _global_exact_match(mentions, graph_store=graph_store)
