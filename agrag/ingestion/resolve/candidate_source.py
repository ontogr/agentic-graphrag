"""Candidate generation for in-batch and persisted graph entities."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import UUID

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.vector_record import VectorHit
from agrag.cypher.entities import (
    fetch_entity_neighbors_query,
    hydrate_entities_by_id_query,
)
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.vector import vector_search
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


MAX_NEIGHBORS_PER_ENTITY = 5


def build_relation_neighbors(
    entities: list[ExtractedEntity],
    relations: Sequence[ExtractedRelation],
    *,
    max_neighbors: int = MAX_NEIGHBORS_PER_ENTITY,
) -> dict[int, list[str]]:
    """Build LLMVerify neighbor context from one batch's extracted relations.

    Args:
        entities: The batch's mentions, indexed as ``relations`` references
            them.
        relations: Relation mentions from the same extraction batch.
        max_neighbors: Maximum neighbor strings kept per entity index.

    Returns:
        Entity index to a list of ``"{relation_label} {other_entity_text}"``
        strings, each direction of a relation contributing one entry to
        both endpoints, capped at ``max_neighbors`` per index. An index with no
        relation names has no key at all.
    """
    neighbors: dict[int, list[str]] = {}
    for relation in relations:
        source_index, target_index = relation.source_index, relation.target_index
        if source_index >= len(entities) or target_index >= len(entities):
            continue
        _append_neighbor(
            neighbors,
            source_index,
            f"{relation.label} {entities[target_index].text}",
            max_neighbors,
        )
        _append_neighbor(
            neighbors,
            target_index,
            f"{relation.label} {entities[source_index].text}",
            max_neighbors,
        )
    return neighbors


def _append_neighbor(
    neighbors: dict[int, list[str]], index: int, value: str, max_neighbors: int
) -> None:
    """Append one neighbor string to an index's bucket until it hits the cap."""
    bucket = neighbors.setdefault(index, [])
    if len(bucket) >= max_neighbors:
        return
    bucket.append(value)


async def fetch_persisted_neighbors(
    entity_ids: Sequence[UUID],
    *,
    graph_store: GraphStore,
    exclude_relation_types: Sequence[str],
    max_neighbors: int = MAX_NEIGHBORS_PER_ENTITY,
) -> dict[UUID, list[str]]:
    """Fetch a bounded neighbor-relationship sample for persisted entities.

    Args:
        entity_ids: Persisted entity ids to fetch neighbors for.
        graph_store: Store to read from.
        exclude_relation_types: Relation types to omit, such as resolution's
            own system relation types (``MATCHES``, ``RESOLVED_AS``, etc.) —
            passed by the caller rather than imported here, since importing
            ``agrag.ingestion.graph``'s ``SYSTEM_RELATION_TYPES`` into this
            module would invert the existing import direction
            (``graph.py`` already imports from this module).
        max_neighbors: Maximum neighbor strings kept per entity id.

    Returns:
        Entity id to a list of ``"{rel_type} {neighbor_name}"`` strings. An
        id with no matching relations, and a malformed row, contribute
        nothing, so that id is simply absent from the map — every caller
        reads through ``.get(id, [])``.
    """
    if not entity_ids:
        return {}
    rows = await graph_store.execute_read(
        fetch_entity_neighbors_query(),
        {
            "ids": [str(entity_id) for entity_id in entity_ids],
            "exclude_types": list(exclude_relation_types),
            "limit": max_neighbors,
        },
    )
    neighbors: dict[UUID, list[str]] = {}
    for row in rows:
        try:
            entity_id = UUID(str(row["entity_id"]))
            rel_type = str(row["rel_type"])
            neighbor_name = str(row["neighbor_name"])
        except (KeyError, ValueError):
            continue
        bucket = neighbors.setdefault(entity_id, [])
        if len(bucket) < max_neighbors:
            bucket.append(f"{rel_type} {neighbor_name}")
    return neighbors


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

    async def global_candidates_for(
        self, mention: ExtractedEntity
    ) -> list[tuple[Entity, float]]:
        """Return persisted entities found by the shared vector-search route.

        The GraphStore-native path's payload already carries the real node
        properties and is validated directly. The VectorStore path's payload
        only carries ``label`` and ``text`` (the embedding source text), so
        candidates are hydrated from the graph by hit id instead; a hit that
        fails to hydrate, for example a tombstoned or deleted node, is
        skipped rather than reconstructed from ``text``.

        Each candidate is paired with the cosine similarity of the
        ``VectorHit`` it came from. The association is keyed by hit id, never
        by position: either branch can drop an entity (malformed payload,
        label mismatch, failed hydration) without dropping the corresponding
        score, so zipping the two lists positionally would silently shift
        scores onto the wrong entities.

        Returns:
            ``(Entity, score)`` pairs in hit order. ``score`` is ``0.0`` for
            an entity whose id is absent from the hit map, which should not
            happen since candidate ids come from those same hits.
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
        hit_scores = {hit.id: hit.score for hit in hits}
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
            return [(entity, hit_scores.get(entity.id, 0.0)) for entity in entities]
        hydrated = await self._hydrate_hits(hits, mention.label)
        return [(entity, hit_scores.get(entity.id, 0.0)) for entity in hydrated]

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
) -> tuple[dict[int, list[int]], dict[tuple[int, int], float]]:
    """Return ANN candidate indices, with a bounded exhaustive fallback.

    The fallback only applies when no indexed candidates are available. It
    keeps first-time and small-graph consolidation deterministic without
    returning to an unbounded pairwise scan for established graphs.

    Returns:
        Mention index to its candidate entity indices, plus each compared
        pair's real embedding cosine similarity keyed by ``(min, max)``
        index order (matching how ``Resolver.resolve`` builds its own pair
        keys). The exhaustive-fallback branch reports no scores, so its
        similarity map is empty.
    """
    index_by_id = {entity.id: index for index, entity in enumerate(entities)}
    candidates_by_index: dict[int, list[int]] = {}
    similarity_by_pair: dict[tuple[int, int], float] = {}
    for index, mention in enumerate(mentions):
        try:
            candidates = await source.global_candidates_for(mention)
        except Exception:  # noqa: BLE001
            continue
        candidate_indices: set[int] = set()
        for candidate, score in candidates:
            candidate_index = index_by_id.get(candidate.id)
            if (
                candidate_index is None
                or candidate_index == index
                or entities[candidate_index].label != mention.label
            ):
                continue
            candidate_indices.add(candidate_index)
            pair = (min(index, candidate_index), max(index, candidate_index))
            similarity_by_pair[pair] = score
        if candidate_indices:
            candidates_by_index[index] = sorted(candidate_indices)
    if candidates_by_index or len(entities) > fallback_limit:
        return candidates_by_index, similarity_by_pair
    return (
        {
            index: [
                candidate_index
                for candidate_index, entity in enumerate(entities)
                if candidate_index != index and entity.label == mention.label
            ]
            for index, mention in enumerate(mentions)
        },
        {},
    )


async def exact_match_lookup(
    mentions: list[ExtractedEntity], *, graph_store: GraphStore
) -> dict[int, Entity]:
    """Return persisted exact matches, including resolved tombstone aliases."""
    from agrag.ingestion._ingest_pipeline import _global_exact_match  # noqa: PLC0415

    return await _global_exact_match(mentions, graph_store=graph_store)
