"""Resolve mentions and persisted entities against the graph.

Ingestion, consolidation, and re-evaluation call the functions here. Each
builds its candidates and neighbor context, runs one ``Resolver`` pass, and
returns the result.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from opentelemetry.trace import Tracer

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.community import MEMBER_OF_RELATION
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.text import normalize_text
from agrag.cypher.entities import fetch_by_merge_keys_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.graphdb.serialize import parse_entity_node
from agrag.ingestion.resolve.candidate_source import (
    GraphCandidateSource,
    PersistedCandidateSource,
    build_relation_neighbors,
    fetch_persisted_neighbors,
    persisted_candidate_indices,
)
from agrag.ingestion.resolve.exact_groups import exact_resolution_groups
from agrag.ingestion.resolve.resolver import (
    Comparator,
    ExactMatch,
    FuzzyMatch,
    LLMVerify,
    ResolutionGroup,
    ResolutionResult,
    Resolver,
)
from agrag.observability import get_tracer, record_swallowed_exception
from agrag.vectordb.base import VectorStore


# Relationship types Graph.open() always registers. Resolution leaves them out
# of the neighbor context it gives to the LLM.
SYSTEM_RELATION_TYPES = [
    "MENTIONED_IN",
    MEMBER_OF_RELATION,
    "PART_OF",
    "NEXT_CHUNK",
    "MATCHES",
    "RESOLVED_AS",
]


@dataclass
class BatchResolution:
    """The outcome of resolving one batch of mentions.

    Attributes:
        exact_matches: Mention index to the persisted entity it matches by
            merge key.
        groups: Mentions that share one raw entity identity.
        result: The semantic resolver pass over the mentions and their
            persisted candidates. ``None`` when the batch has no mentions.
        persisted_ids: Index of each synthetic candidate mention to the id of
            the persisted entity it stands for.
        candidate_entities: Persisted candidates by id.
    """

    exact_matches: dict[int, Entity]
    groups: list[ResolutionGroup]
    result: ResolutionResult | None
    persisted_ids: dict[int, UUID] = field(default_factory=dict)
    candidate_entities: dict[UUID, Entity] = field(default_factory=dict)


def synthetic_entity_mention(entity: Entity) -> tuple[ExtractedEntity, Chunk]:
    """Build a mention and distinct name context for a persisted raw entity."""
    chunk_id = uuid4()
    chunk = Chunk(
        id=chunk_id,
        document_id=chunk_id,
        index=0,
        text=entity.name,
        provenance=TextProvenance(char_start=0, char_end=len(entity.name)),
    )
    return (
        ExtractedEntity(
            chunk_id=chunk_id,
            label=entity.label,
            text=entity.name,
            char_start=0,
            char_end=len(entity.name),
        ),
        chunk,
    )


def synthesize_mentions(
    entities: list[Entity],
) -> tuple[list[ExtractedEntity], dict[UUID, Chunk]]:
    """Build resolver mentions and per-entity dummy chunks for persisted entities.

    Persisted entities have no real chunk text to compare against, so each
    gets a synthetic mention and a dummy chunk carrying its own name as
    LLMVerify context. Each entity's dummy chunk id is its own, independent
    of its real source_chunk_ids: two entities commonly share a first source
    chunk (they were extracted from the same passage), and keying the dummy
    chunk by that shared id would let the first entity processed silently
    stand in as every later entity's own context.

    Args:
        entities: The persisted entities to synthesize mentions for.

    Returns:
        One ExtractedEntity mention per entity and the dummy Chunk each
        mention's chunk_id resolves to, both index-aligned with entities.
    """
    synthetic_mentions: list[ExtractedEntity] = []
    dummy_chunks_by_id: dict[UUID, Chunk] = {}
    for ent in entities:
        mention, chunk = synthetic_entity_mention(ent)
        synthetic_mentions.append(mention)
        dummy_chunks_by_id[mention.chunk_id] = chunk
    return synthetic_mentions, dummy_chunks_by_id


async def find_exact_matches(
    mentions: list[ExtractedEntity],
    *,
    graph_store: GraphStore,
    job_id: UUID | str | None = None,
) -> dict[int, Entity]:
    """Return each mention index's matching persisted Entity, if it has one.

    One batched read per distinct label present in mentions. A row is
    mapped back to its mention(s) by the merge_key the row's alias was
    matched on -- returned alongside the node by fetch_by_merge_keys_query
    -- rather than by re-deriving a key from the resolved entity's current
    name: an accepted alias can name an entity by something other than its
    current canonical name (see upsert_merge_alias_query), so re-deriving
    would silently fail to map those mentions back. Rows without a returned
    merge_key (plain mocks) fall back to the resolved entity's own
    merge_key.

    Args:
        mentions: The entity mentions to look up.
        graph_store: Where the lookup runs.
        job_id: The in-flight Cutover Job's id, so the alias/node guards
            admit this job's own pending writes while excluding every
            other in-flight job's. None reads committed-only.

    Returns:
        A map from mention index to its matching Entity.
    """
    if not mentions:
        return {}
    grouped: dict[str, list[str]] = defaultdict(list)
    mk_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, mention in enumerate(mentions):
        mk = f"{mention.label}:{normalize_text(mention.text)}"
        grouped[mention.label].append(mk)
        mk_to_indices[mk].append(idx)

    result: dict[int, Entity] = {}
    for _label, mks in grouped.items():
        unique_mks = list(dict.fromkeys(mks))
        if not unique_mks:
            continue
        rows = await graph_store.execute_read(
            fetch_by_merge_keys_query(),
            {
                "merge_keys": unique_mks,
                "job_id": str(job_id) if job_id is not None else None,
            },
        )
        for row in rows:
            entity = parse_entity_node(row.get("n"))
            if entity is None:
                continue
            queried_mk = row.get("merge_key")
            mk = queried_mk if isinstance(queried_mk, str) else entity.merge_key
            for idx in mk_to_indices.get(mk, []):
                if mentions[idx].label == entity.label:
                    result[idx] = entity
    return result


async def resolve_batch(
    mentions: list[ExtractedEntity],
    relations: Sequence[ExtractedRelation],
    chunks_by_id: dict[UUID, Chunk],
    *,
    graph_store: GraphStore,
    embedder: Embedder,
    vector_store: VectorStore | None,
    vector_collection: str,
    entity_labels: Sequence[str],
    tracer: Tracer | None,
    max_llm_pairs: int,
    job_id: UUID | str | None = None,
) -> BatchResolution:
    """Resolve one extraction batch against itself and the persisted graph.

    The resolver sees the real mentions plus one synthetic mention per
    persisted ANN candidate, so a new mention can join a persisted cluster
    through one pass. Synthetic mentions never initiate a comparison.

    Args:
        mentions: The batch's extracted mentions.
        relations: The relations addressing ``mentions``, used as neighbor
            context.
        chunks_by_id: The batch's chunks, for LLM verification context.
        graph_store: Where exact-match, candidate, and neighbor reads run.
        embedder: Embeds mention text for candidate search and fuzzy review.
        vector_store: Optional vector store the candidate search reads.
        vector_collection: Collection name for the candidate search.
        entity_labels: The labels the schema defines.
        tracer: Opens the phase spans and traces the resolver.
        max_llm_pairs: The most ambiguous pairs per label sent to the LLM.
        job_id: The in-flight Cutover Job's id for the exact-match read.

    Returns:
        The exact matches, exact groups, resolver result, and persisted
        candidates for the batch.
    """
    resolved_tracer = get_tracer(tracer)
    with resolved_tracer.start_as_current_span(
        "agrag.resolution.global_exact_match",
        attributes={"agrag.mention_count": len(mentions)},
    ) as span:
        exact_matches = await find_exact_matches(
            mentions, graph_store=graph_store, job_id=job_id
        )
        span.set_attribute("agrag.exact_match_hits", len(exact_matches))

    chunks_by_id = dict(chunks_by_id)
    # One candidate source for both paths: candidates_for is pure
    # same-label in-batch blocking and never touches a store.
    candidate_source = GraphCandidateSource(
        graph_store=graph_store,
        embedder=embedder,
        vector_store=vector_store,
        vector_collection=vector_collection,
        entity_labels=entity_labels,
    )
    combined_mentions: list[ExtractedEntity] = list(mentions)
    persisted_candidates: dict[int, list[int]] = {}
    persisted_ids: dict[int, UUID] = {}
    candidate_entities: dict[UUID, Entity] = {}
    similarity_by_pair: dict[tuple[int, int], float] = {}
    with resolved_tracer.start_as_current_span(
        "agrag.resolution.candidate_generation",
        attributes={"agrag.mention_count": len(mentions)},
    ) as span:
        for mention_index, mention in enumerate(mentions):
            try:
                candidates = await candidate_source.global_candidates_for(mention)
            except Exception as exc:  # noqa: BLE001
                record_swallowed_exception(exc)
                candidates = []
            seen_candidate_ids: set[UUID] = set()
            exact_match = exact_matches.get(mention_index)
            for candidate, candidate_similarity in candidates:
                if candidate.id in seen_candidate_ids:
                    continue
                seen_candidate_ids.add(candidate.id)
                if exact_match is not None and candidate.id == exact_match.id:
                    continue
                candidate_index = len(combined_mentions)
                candidate_mention, candidate_chunk = synthetic_entity_mention(candidate)
                combined_mentions.append(candidate_mention)
                chunks_by_id[candidate_mention.chunk_id] = candidate_chunk
                persisted_candidates.setdefault(mention_index, []).append(
                    candidate_index
                )
                persisted_ids[candidate_index] = candidate.id
                candidate_entities[candidate.id] = candidate
                pair = (
                    min(mention_index, candidate_index),
                    max(mention_index, candidate_index),
                )
                similarity_by_pair[pair] = candidate_similarity
        # Same-label real pairs plus the persisted map. Synthetics never
        # initiate: no entry is keyed by a synthetic index.
        candidates_by_index: dict[int, list[int]] = {}
        for index, _mention in enumerate(mentions):
            real_peers = await candidate_source.candidates_for(index, mentions)
            if real_peers:
                candidates_by_index[index] = list(real_peers)
        for index, synthetic in persisted_candidates.items():
            candidates_by_index.setdefault(index, []).extend(synthetic)
        span.set_attribute(
            "agrag.persisted_candidate_count",
            sum(len(v) for v in persisted_candidates.values()),
        )
        span.set_attribute(
            "agrag.in_batch_candidate_count",
            sum(len(v) for v in candidates_by_index.values()),
        )
    # Neighbor context for LLM review: the batch's own mentions from their
    # extracted relations, each persisted candidate from its stored edges.
    neighbors_by_index = build_relation_neighbors(mentions, relations)
    if persisted_ids:
        persisted_neighbors = await fetch_persisted_neighbors(
            list(persisted_ids.values()),
            graph_store=graph_store,
            exclude_relation_types=SYSTEM_RELATION_TYPES,
        )
        for candidate_index, entity_id in persisted_ids.items():
            neighbors_by_index[candidate_index] = persisted_neighbors.get(entity_id, [])
    resolver = _build_resolver(
        chunks_by_id,
        candidates_by_index,
        embedder=embedder,
        tracer=tracer,
        max_llm_pairs=max_llm_pairs,
    )
    result = (
        await resolver.resolve(
            combined_mentions,
            neighbors_by_index=neighbors_by_index,
            similarity_by_pair=similarity_by_pair,
        )
        if mentions
        else None
    )
    return BatchResolution(
        exact_matches=exact_matches,
        groups=exact_resolution_groups(mentions, exact_matches),
        result=result,
        persisted_ids=persisted_ids,
        candidate_entities=candidate_entities,
    )


async def resolve_persisted(
    entities: list[Entity],
    *,
    graph_store: GraphStore,
    embedder: Embedder,
    vector_store: VectorStore | None,
    vector_collection: str,
    entity_labels: Sequence[str],
    tracer: Tracer | None,
    max_llm_pairs: int,
) -> ResolutionResult:
    """Resolve persisted entities against each other.

    ANN search bounds the pairs the resolver compares.

    Args:
        entities: The persisted entities to compare, all of one label.
        graph_store: Where the candidate and neighbor reads run.
        embedder: Embeds entity names for candidate search and fuzzy review.
        vector_store: Optional vector store the candidate search reads.
        vector_collection: Collection name for the candidate search.
        entity_labels: The labels the schema defines.
        tracer: Traces the resolver.
        max_llm_pairs: The most ambiguous pairs per label sent to the LLM.

    Returns:
        The resolver result, indexed like ``entities``.
    """
    mentions, chunks_by_id = synthesize_mentions(entities)
    candidate_source = GraphCandidateSource(
        graph_store=graph_store,
        embedder=embedder,
        vector_store=vector_store,
        vector_collection=vector_collection,
        entity_labels=entity_labels,
    )
    persisted_neighbors = await fetch_persisted_neighbors(
        [entity.id for entity in entities],
        graph_store=graph_store,
        exclude_relation_types=SYSTEM_RELATION_TYPES,
    )
    neighbors_by_index = {
        index: persisted_neighbors.get(entity.id, [])
        for index, entity in enumerate(entities)
    }
    candidate_indices, similarity_by_pair = await persisted_candidate_indices(
        mentions, entities, source=candidate_source
    )
    resolver = _build_resolver(
        chunks_by_id,
        candidate_indices,
        embedder=embedder,
        tracer=tracer,
        max_llm_pairs=max_llm_pairs,
    )
    return await resolver.resolve(
        mentions,
        neighbors_by_index=neighbors_by_index,
        similarity_by_pair=similarity_by_pair,
    )


async def resolve_among(
    entities: list[Entity],
    *,
    embedder: Embedder,
    tracer: Tracer | None,
    max_llm_pairs: int,
) -> ResolutionResult:
    """Resolve a fixed set of persisted entities by comparing same-label pairs.

    Args:
        entities: The persisted entities to compare. Nothing outside this
            set is read or compared.
        embedder: Embeds entity names for fuzzy review.
        tracer: Traces the resolver.
        max_llm_pairs: The most ambiguous pairs per label sent to the LLM.

    Returns:
        The resolver result, indexed like ``entities``.
    """
    mentions, chunks_by_id = synthesize_mentions(entities)
    candidates_by_index = {
        index: [
            other
            for other, peer in enumerate(mentions)
            if other != index and peer.label == mention.label
        ]
        for index, mention in enumerate(mentions)
    }
    resolver = _build_resolver(
        chunks_by_id,
        {index: peers for index, peers in candidates_by_index.items() if peers},
        embedder=embedder,
        tracer=tracer,
        max_llm_pairs=max_llm_pairs,
    )
    return await resolver.resolve(mentions)


def _build_resolver(
    chunks_by_id: dict[UUID, Chunk],
    candidates_by_index: dict[int, list[int]],
    *,
    embedder: Embedder,
    tracer: Tracer | None,
    max_llm_pairs: int,
) -> Resolver:
    """Build the zone-routed resolver: ExactMatch, FuzzyMatch, then LLMVerify."""
    comparators: list[Comparator] = [
        ExactMatch(),
        FuzzyMatch(),
        LLMVerify(chunks_by_id=chunks_by_id, tracer=tracer),
    ]
    return Resolver(
        comparators=comparators,
        candidate_source=PersistedCandidateSource(candidates_by_index),
        embedder=embedder,
        tracer=tracer,
        max_llm_pairs=max_llm_pairs,
    )
