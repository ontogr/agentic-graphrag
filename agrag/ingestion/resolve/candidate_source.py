"""Candidate generation for in-batch and persisted graph entities."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
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
        """Return persisted entities found by the shared vector-search route."""
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
        entities: list[Entity] = []
        for hit in hits:
            payload = dict(hit.payload)
            payload.setdefault("id", hit.id)
            if self.vector_store is None:
                payload.setdefault("label", mention.label)
            if payload.get("label") != mention.label:
                continue
            try:
                entities.append(Entity.model_validate(payload))
            except Exception:  # malformed vector payloads are not candidates
                continue
        return entities


class InBatchCandidateSource(CandidateSource):
    """Compatibility candidate source for the existing Resolver callers."""

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


async def exact_match_lookup(
    mentions: list[ExtractedEntity], *, graph_store: GraphStore
) -> dict[int, Entity]:
    """Return persisted exact matches, including resolved tombstone aliases."""
    # Keep the established lookup behavior byte-for-byte until Phase 4 moves
    # the ingestion pipeline. That phase removes the legacy graph helper.
    from agrag.ingestion.graph import _global_exact_match  # noqa: PLC0415

    return await _global_exact_match(mentions, graph_store=graph_store)
