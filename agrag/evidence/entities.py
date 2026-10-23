"""Find entities by name or meaning, and explore typed relations around one entity.

An entity is returned only with the passages that mention it, and only when at
least one of those passages is in the caller's scope. Each passage is an evidence
id. An entity whose passages are all superseded is returned as unsupported, with
no passages. Exploration follows entity-to-entity relations with bounded depth,
size and edge count. A relation with a visible passage is an assertion, and a
connection with no passage is a path.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.community import COMMUNITY_LABEL
from agrag.common.data_models.entity_search import (
    EdgeKind,
    EntityHit,
    EntityKind,
    EntityResult,
    ExplorationBound,
    ExplorationEdge,
    ExplorationNode,
    ExplorationResult,
    ExplorationStatus,
    SupportingPassage,
)
from agrag.common.data_models.evidence import (
    EvidenceSearchLeg,
    EvidenceSearchMode,
    EvidenceSearchStatus,
    IndexState,
    LegFailure,
)
from agrag.common.data_models.graph_schema import RESERVED_RELATION_TYPES
from agrag.common.data_models.index_record import IndexInfo
from agrag.common.data_models.resolved_entity import RESOLVED_ENTITY_LABEL
from agrag.common.data_models.vector_record import VectorKind
from agrag.cypher.evidence import (
    entity_candidates_from_rows_query,
    entity_candidates_query,
    entity_mentions_query,
    explore_edges_query,
)
from agrag.cypher.schema import vector_index_name
from agrag.embedding.base import Embedder
from agrag.evidence._shared import (
    EMBEDDING_MISMATCH_MESSAGE,
    IndexSpec,
    chunk_location,
    chunk_reference,
    embedding_matches,
    indexes_ready,
    lucene_terms,
    run_with_timeout,
    scope_node_ids,
    stored_chunk,
    stores_ready,
)
from agrag.evidence.contract import (
    DEFAULT_MAX_EDGES,
    DEFAULT_MAX_NODES,
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_SUPPORT_LIMIT,
    MAX_DEPTH,
    MAX_EXPLORE_BOUND,
)
from agrag.evidence.ids import encode_evidence_id
from agrag.evidence.search import reciprocal_rank_fusion
from agrag.graphdb.base import GraphStore
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


_LOGGER = logging.getLogger(__name__)
_LEG_FAILED_MESSAGE = "search leg failed"
_STORE_ERROR_MESSAGE = "entity store error"
_NAME_PROPERTY = "name"
_EMBEDDING_PROPERTY = "embedding"
_FULLTEXT_TYPE = "FULLTEXT"
_VECTOR_TYPE = "VECTOR"
_MAX_CANDIDATES = 1000
_NON_ENTITY_LABELS = frozenset({CHUNK_LABEL, COMMUNITY_LABEL, RESOLVED_ENTITY_LABEL})
_INTERNAL_PROPERTIES = frozenset(
    {
        "id",
        "name",
        "merge_key",
        "merge_count",
        "source_chunk_ids",
        "created_at",
        "embedding",
    }
)
_EDGE_SUPPORT_LIMIT = 3
_EXPLORE_ROW_LIMIT = 1000


@dataclass(frozen=True)
class _Visible:
    """An entity with the passages in scope that mention it.

    Attributes:
        name: The entity name.
        properties: The schema properties of the entity.
        supports: Visible passages that mention the entity, in the order returned.
    """

    name: str
    properties: dict[str, object]
    supports: list[SupportingPassage] = field(default_factory=list)

    @property
    def kind(self) -> EntityKind:
        """Return SUPPORTED when a visible passage mentions the entity."""
        return EntityKind.SUPPORTED if self.supports else EntityKind.UNSUPPORTED


@dataclass(frozen=True)
class _Candidate:
    """One entity candidate from a search leg, with the label whose index found it."""

    entity_id: str
    score: float
    label: str


@dataclass(frozen=True)
class _Ranked:
    """The candidates of one leg, best first, and whether a search hit its ceiling."""

    candidates: list[_Candidate]
    ceiling: bool


async def entity_search(
    store: GraphStore,
    embedder: Embedder,
    query: str,
    *,
    scope: frozenset[str],
    labels: Sequence[str] | None = None,
    mode: EvidenceSearchMode = EvidenceSearchMode.HYBRID,
    limit: int = DEFAULT_SEARCH_LIMIT,
    support_limit: int = DEFAULT_SUPPORT_LIMIT,
    vector_store: VectorStore | None = None,
    settings: RetrievalSettings | None = None,
    timeout: float | None = None,
) -> EntityResult:
    """Find up to ``limit`` entities that match a query by name or by meaning.

    The lexical leg matches the words of the query against the ``name`` of each
    entity. The semantic leg embeds the query and searches the ``embedding`` of
    each entity. The hybrid mode runs both and fuses the rankings with reciprocal
    rank fusion, or delegates fusion to an external store. A missing or offline
    index or vector collection gives ``index_not_ready``.

    An entity is returned only when a passage in ``scope`` mentions it. Its
    ``support`` lists up to ``support_limit`` visible passages, as evidence ids.
    An entity with passages in scope and no visible passage is returned with kind
    ``unsupported`` and an empty support list.

    Args:
        store: The graph store to search.
        embedder: Embeds the query for the semantic leg. The lexical leg does not
            use it.
        query: The query text. Lucene syntax is not applied: each word is searched
            as a plain term.
        scope: Keys of the documents whose passages may be used.
        labels: The entity labels to search. None discovers labels from graph
            indexes for native search, or entity name indexes for external search.
        mode: Which legs to run.
        limit: The most entities to return. Must be positive.
        support_limit: The most supporting passages listed for each entity. Must
            be positive.
        vector_store: Optional external vector store. Placement is not validated
            by this function.
        settings: Fusion configuration. None uses the defaults.
        timeout: Server-side transaction timeout in seconds for each store read.
            None uses the server's default.

    Returns:
        The entities, best first, with the status and the index state.

    Raises:
        ValueError: ``limit`` or ``support_limit`` is not positive.
    """
    retrieval = settings or RetrievalSettings()
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}")
    if support_limit <= 0:
        raise ValueError(f"support_limit must be positive, got {support_limit}")
    if not scope:
        return EntityResult(status=EvidenceSearchStatus.EMPTY_SCOPE)

    try:
        indexes = await store.list_indexes(timeout=timeout)
    except Exception:
        _LOGGER.exception("Entity label discovery failed")
        return EntityResult(status=EvidenceSearchStatus.FAILED)
    entity_labels = _entity_labels(indexes, labels, vector_store=vector_store)
    if not entity_labels:
        return EntityResult(status=EvidenceSearchStatus.NO_MATCH)

    legs = _search_legs(mode, vector_store)
    legs, guard_failure, index_state, error = await _semantic_fallback(
        store,
        embedder,
        entity_labels,
        legs,
        mode=mode,
        indexes=indexes,
        vector_store=vector_store,
        timeout=timeout,
    )
    if error is not None:
        return error

    candidate_cap = (
        min(_MAX_CANDIDATES, vector_store.max_results)
        if vector_store is not None and EvidenceSearchLeg.SEMANTIC in legs
        else _MAX_CANDIDATES
    )
    outcome = await _leg_outcome(
        store,
        embedder,
        legs,
        query,
        entity_labels,
        mode=mode,
        vector_store=vector_store,
        retrieval=retrieval,
        limit=limit,
        candidate_cap=candidate_cap,
        scope=scope,
        support_limit=support_limit,
        timeout=timeout,
    )
    if outcome.store_failed:
        return EntityResult(
            status=EvidenceSearchStatus.FAILED,
            index_state=index_state,
            failures=[
                LegFailure(leg=leg, message=_STORE_ERROR_MESSAGE) for leg in legs
            ],
        )

    hits = _combine(
        outcome.rankings,
        outcome.visible,
        mode=mode,
        limit=limit,
        constant=retrieval.rrf_k,
    )
    truncated = any(ranked.ceiling for ranked in outcome.rankings.values())
    return EntityResult(
        status=_result_status(
            outcome.leg_failures, len(legs), guard_failure, bool(hits)
        ),
        hits=hits,
        truncated=truncated and len(hits) < limit,
        index_state=index_state,
        failures=([guard_failure] if guard_failure else []) + outcome.leg_failures,
    )


@dataclass(frozen=True)
class _LegOutcome:
    """What one entity search collected from its legs.

    Attributes:
        rankings: The candidates of each completed leg.
        leg_failures: The legs that failed.
        visible: The candidates that have a passage in scope, with their support.
        store_failed: True when the support read failed, so the search failed
            no matter what the legs returned.
    """

    rankings: dict[EvidenceSearchLeg, _Ranked]
    leg_failures: list[LegFailure]
    visible: dict[str, _Visible]
    store_failed: bool


async def _leg_outcome(
    store: GraphStore,
    embedder: Embedder,
    legs: Sequence[EvidenceSearchLeg],
    query: str,
    labels: Sequence[str],
    *,
    mode: EvidenceSearchMode,
    vector_store: VectorStore | None,
    retrieval: RetrievalSettings,
    limit: int,
    candidate_cap: int,
    scope: frozenset[str],
    support_limit: int,
    timeout: float | None,
) -> _LegOutcome:
    """Run the legs together and load the visible support of their candidates.

    With an external store, the candidate count grows once, to the ceiling,
    when the first read filled up without enough visible entities. The support
    read failure marks the outcome instead of raising.
    """
    candidate_count = min(limit * 2, candidate_cap)
    while True:
        results = await asyncio.gather(
            *(
                _leg_candidates(
                    store,
                    embedder,
                    leg=leg,
                    query=query,
                    labels=labels,
                    count=candidate_count,
                    vector_store=vector_store,
                    hybrid=mode is EvidenceSearchMode.HYBRID,
                    alpha=retrieval.hybrid_alpha,
                    timeout=timeout,
                )
                for leg in legs
            ),
            return_exceptions=True,
        )
        rankings: dict[EvidenceSearchLeg, _Ranked] = {}
        leg_failures: list[LegFailure] = []
        for leg, result in zip(legs, results, strict=True):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, BaseException):
                _LOGGER.error("Entity search leg %s failed: %r", leg.value, result)
                leg_failures.append(LegFailure(leg=leg, message=_LEG_FAILED_MESSAGE))
                continue
            rankings[leg] = result

        candidate_ids = {
            candidate.entity_id
            for ranked in rankings.values()
            for candidate in ranked.candidates
        }
        try:
            visible = await _load_visible(
                store, candidate_ids, scope, support_limit, timeout=timeout
            )
        except Exception:
            _LOGGER.exception("Entity support query failed")
            return _LegOutcome(
                rankings=rankings,
                leg_failures=leg_failures,
                visible={},
                store_failed=True,
            )

        external_ranking = rankings.get(EvidenceSearchLeg.SEMANTIC)
        visible_count = (
            sum(
                candidate.entity_id in visible
                for candidate in external_ranking.candidates
            )
            if external_ranking is not None
            else 0
        )
        if (
            vector_store is None
            or external_ranking is None
            or not external_ranking.ceiling
            or visible_count >= limit
            or candidate_count >= candidate_cap
        ):
            return _LegOutcome(
                rankings=rankings,
                leg_failures=leg_failures,
                visible=visible,
                store_failed=False,
            )
        candidate_count = candidate_cap


async def _semantic_guard_failure(
    embedder: Embedder,
    *,
    legs: Sequence[EvidenceSearchLeg],
    indexes: Sequence[IndexInfo],
    index_name: str,
    vector_store: VectorStore | None,
    timeout: float | None,
) -> LegFailure | None:
    """Return the semantic failure recorded by the dimension guard, or None.

    A dimension mismatch and an unreadable embedder both withdraw the semantic
    leg; only the mismatch carries the mismatch message.
    """
    if EvidenceSearchLeg.SEMANTIC not in legs:
        return None
    try:
        matched = await embedding_matches(
            embedder,
            indexes=indexes,
            index_name=index_name,
            vector_store=vector_store,
            kind=VectorKind.ENTITY,
            timeout=timeout,
        )
    except Exception:
        _LOGGER.exception("The query embedder could not report its dimensions")
        return LegFailure(leg=EvidenceSearchLeg.SEMANTIC, message=_LEG_FAILED_MESSAGE)
    if not matched:
        return LegFailure(
            leg=EvidenceSearchLeg.SEMANTIC, message=EMBEDDING_MISMATCH_MESSAGE
        )
    return None


async def _semantic_fallback(
    store: GraphStore,
    embedder: Embedder,
    labels: Sequence[str],
    legs: list[EvidenceSearchLeg],
    *,
    mode: EvidenceSearchMode,
    indexes: Sequence[IndexInfo],
    vector_store: VectorStore | None,
    timeout: float | None,
) -> tuple[list[EvidenceSearchLeg], LegFailure | None, IndexState, EntityResult | None]:
    """Apply the dimension guard, then check index readiness.

    On a guard failure the hybrid search falls back to the graph lexical leg,
    and semantic search fails. The returned legs are the ones to run.

    Returns:
        The legs to run, the guard failure if any, the index state, and the
        error result that answers instead of a search, or None.
    """
    guard_failure = await _semantic_guard_failure(
        embedder,
        legs=legs,
        indexes=indexes,
        index_name=vector_index_name(labels[0], _EMBEDDING_PROPERTY),
        vector_store=vector_store,
        timeout=timeout,
    )
    if guard_failure is not None:
        if mode is not EvidenceSearchMode.HYBRID:
            return (
                legs,
                guard_failure,
                IndexState.READY,
                EntityResult(
                    status=EvidenceSearchStatus.FAILED, failures=[guard_failure]
                ),
            )
        legs = [EvidenceSearchLeg.LEXICAL]
    index_state, error = await _readiness(
        store,
        labels,
        legs,
        vector_store=vector_store,
        indexes=indexes,
        timeout=timeout,
    )
    return legs, guard_failure, index_state, error


async def _readiness(
    store: GraphStore,
    labels: Sequence[str],
    legs: Sequence[EvidenceSearchLeg],
    *,
    vector_store: VectorStore | None,
    indexes: Sequence[IndexInfo],
    timeout: float | None,
) -> tuple[IndexState, EntityResult | None]:
    """Return the index state, or the error result of an unreadable store.

    The result is None when the needed indexes and collections were checked.
    """
    try:
        index_state = await indexes_ready(
            store,
            _index_specs(labels, legs, vector_store=vector_store),
            timeout=timeout,
            indexes=indexes,
        )
        store_state = await stores_ready(
            vector_store,
            [VectorKind.ENTITY]
            if vector_store is not None and EvidenceSearchLeg.SEMANTIC in legs
            else [],
            timeout=timeout,
        )
        if store_state is IndexState.NOT_READY:
            index_state = IndexState.NOT_READY
    except Exception:
        _LOGGER.exception("Entity index state read failed")
        return IndexState.READY, EntityResult(status=EvidenceSearchStatus.FAILED)
    if index_state is IndexState.NOT_READY:
        return index_state, EntityResult(
            status=EvidenceSearchStatus.INDEX_NOT_READY, index_state=index_state
        )
    return index_state, None


def _search_legs(
    mode: EvidenceSearchMode, vector_store: VectorStore | None
) -> list[EvidenceSearchLeg]:
    """Return the search legs supported by the selected backend."""
    if vector_store is not None and mode is EvidenceSearchMode.HYBRID:
        return [EvidenceSearchLeg.SEMANTIC]
    if mode is EvidenceSearchMode.HYBRID:
        return [EvidenceSearchLeg.LEXICAL, EvidenceSearchLeg.SEMANTIC]
    return [EvidenceSearchLeg(mode.value)]


def _result_status(
    leg_failures: Sequence[LegFailure],
    leg_count: int,
    guard_failure: LegFailure | None,
    has_hits: bool,
) -> EvidenceSearchStatus:
    """Return the aggregate search status from its completed legs.

    A withdrawn semantic leg makes a completed search partial even without a
    failed leg.
    """
    if leg_failures and len(leg_failures) == leg_count:
        return EvidenceSearchStatus.FAILED
    if leg_failures or guard_failure is not None:
        return EvidenceSearchStatus.PARTIAL
    if has_hits:
        return EvidenceSearchStatus.OK
    return EvidenceSearchStatus.NO_MATCH


async def explore_relationships(
    store: GraphStore,
    entity_id: str,
    *,
    scope: frozenset[str],
    relation_types: Sequence[str] | None = None,
    depth: int = 1,
    max_nodes: int = DEFAULT_MAX_NODES,
    max_edges: int = DEFAULT_MAX_EDGES,
    timeout: float | None = None,
) -> ExplorationResult:
    """Explore the entity relations around one entity, within bounds.

    The walk follows relations that join two entities. With ``relation_types``
    only those types are followed. Without it, every schema relation type is
    followed, and graph-owned types such as ``HAS_PART`` and ``MENTIONED_IN`` are
    never followed. An entity can be reached only through a passage in scope, the
    same rule as in ``entity_search``.

    A relation with a visible passage in scope is an assertion, and its passages
    are listed in the edge. A relation without any passage is a path. A relation
    whose passages are all superseded or out of scope is dropped.

    The walk stops at the bound it hits first in each step, and ``truncated_by``
    names every bound that cut the walk. ``depth`` reports the bound when an
    entity at the last depth has a connection to an entity that was not reached.

    Args:
        store: The graph store to read.
        entity_id: The id of the start entity, as a canonical UUID string.
        scope: Keys of the documents whose passages may be used.
        relation_types: The relation types to follow. None follows every schema
            relation type.
        depth: How many relations to follow from the start entity. 1 or 2.
        max_nodes: The most entities to return, not counting the start. Between 1
            and 200.
        max_edges: The most edges to return. Between 1 and 200.
        timeout: Server-side transaction timeout in seconds for each store read.
            None uses the server's default.

    Returns:
        The nodes, edges and bounds. An unavailable or malformed start gives no
        nodes or edges.

    Raises:
        ValueError: ``depth``, ``max_nodes`` or ``max_edges`` is outside its range.
    """
    if not 1 <= depth <= MAX_DEPTH:
        raise ValueError(f"depth must be 1 or 2, got {depth}")
    if not 1 <= max_nodes <= MAX_EXPLORE_BOUND:
        raise ValueError(f"max_nodes must be 1 to {MAX_EXPLORE_BOUND}, got {max_nodes}")
    if not 1 <= max_edges <= MAX_EXPLORE_BOUND:
        raise ValueError(f"max_edges must be 1 to {MAX_EXPLORE_BOUND}, got {max_edges}")
    if not _is_canonical_uuid(entity_id):
        return ExplorationResult(
            status=ExplorationStatus.MALFORMED, detail="not an entity id"
        )
    if not scope:
        return ExplorationResult(status=ExplorationStatus.UNAVAILABLE)

    try:
        visible = await _load_visible(store, {entity_id}, scope, 1, timeout=timeout)
    except Exception:
        _LOGGER.exception("Entity support query failed for an exploration")
        return ExplorationResult(
            status=ExplorationStatus.FAILED, detail=_STORE_ERROR_MESSAGE
        )
    if entity_id not in visible:
        return ExplorationResult(status=ExplorationStatus.UNAVAILABLE)

    try:
        nodes, edges, bounds = await _walk(
            store,
            entity_id,
            scope=scope,
            relation_types=relation_types,
            depth=depth,
            max_nodes=max_nodes,
            max_edges=max_edges,
            timeout=timeout,
        )
    except Exception:
        _LOGGER.exception("Exploration walk failed for an entity")
        return ExplorationResult(
            status=ExplorationStatus.FAILED, detail=_STORE_ERROR_MESSAGE
        )
    return ExplorationResult(
        status=ExplorationStatus.OK,
        nodes=nodes,
        edges=edges,
        truncated=bool(bounds),
        truncated_by=bounds,
    )


def _is_canonical_uuid(value: str) -> bool:
    """Return True when the value is a lowercase hyphenated UUID string."""
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _entity_labels(
    indexes: Sequence[IndexInfo],
    labels: Sequence[str] | None,
    *,
    vector_store: VectorStore | None,
) -> list[str]:
    """Return labels to search, using the available graph index kind."""
    if labels is not None:
        return sorted(set(labels))
    index_type = "FULLTEXT" if vector_store is not None else _VECTOR_TYPE
    index_property = _NAME_PROPERTY if vector_store is not None else _EMBEDDING_PROPERTY
    found = {
        label
        for index in indexes
        if index.type == index_type and index.properties == [index_property]
        for label in index.labels
    }
    return sorted(found - _NON_ENTITY_LABELS)


def _index_specs(
    labels: Iterable[str],
    legs: Sequence[EvidenceSearchLeg],
    *,
    vector_store: VectorStore | None = None,
) -> list[IndexSpec]:
    """Return the index each leg of each label searches, with its expected shape."""
    specs: list[IndexSpec] = []
    for label in labels:
        if EvidenceSearchLeg.LEXICAL in legs:
            specs.append(
                IndexSpec(
                    index_type=_FULLTEXT_TYPE,
                    label=label,
                    prop=_NAME_PROPERTY,
                )
            )
        if EvidenceSearchLeg.SEMANTIC in legs and vector_store is None:
            specs.append(
                IndexSpec(
                    index_type=_VECTOR_TYPE,
                    label=label,
                    prop=_EMBEDDING_PROPERTY,
                )
            )
    return specs


async def _leg_candidates(
    store: GraphStore,
    embedder: Embedder,
    *,
    leg: EvidenceSearchLeg,
    query: str,
    labels: Sequence[str],
    count: int,
    vector_store: VectorStore | None,
    hybrid: bool,
    alpha: float,
    timeout: float | None,
) -> _Ranked:
    """Return the candidates of one leg over every label, best first, once each.

    The per-label queries run together. One failing label fails the leg.
    """
    terms = ""
    vector: list[float] = []
    if leg is EvidenceSearchLeg.LEXICAL:
        terms = lucene_terms(query)
        if not terms:
            return _Ranked(candidates=[], ceiling=False)
    else:
        [embedded] = await embedder.embed([query])
        vector = list(embedded)

    if leg is EvidenceSearchLeg.SEMANTIC and vector_store is not None:
        if hybrid:
            store_hits = await run_with_timeout(
                lambda: vector_store.hybrid_search(
                    VectorKind.ENTITY,
                    vector,
                    query,
                    limit=count,
                    alpha=alpha,
                    labels=labels,
                ),
                timeout,
            )
        else:
            store_hits = await run_with_timeout(
                lambda: vector_store.search(
                    VectorKind.ENTITY, vector, limit=count, labels=labels
                ),
                timeout,
            )
        rows = (
            await store.execute_read(
                entity_candidates_from_rows_query(),
                {
                    "rows": [
                        {"id": str(hit.id), "score": hit.score} for hit in store_hits
                    ],
                    "labels": list(labels),
                },
                timeout=timeout,
            )
            if store_hits
            else []
        )
        found = [
            _Candidate(str(row["entity_id"]), float(row["score"]), str(row["label"]))
            for row in rows
        ]
        return _ranked(found, ceiling=len(store_hits) >= count)

    async def read_label(label: str) -> Sequence[Mapping[str, Any]]:
        if leg is EvidenceSearchLeg.LEXICAL:
            call = await store.fulltext_search_call(
                label=label, properties=[_NAME_PROPERTY]
            )
            statement = entity_candidates_query(label, call.text)
            parameters: dict[str, Any] = {
                **call.params,
                "fulltext_terms": terms,
                "k": count,
            }
        else:
            call = await store.vector_search_call(
                label=label, vector_property=_EMBEDDING_PROPERTY
            )
            statement = entity_candidates_query(label, call.text)
            parameters = {**call.params, "vector": vector, "k": count}
        return await store.execute_read(statement, parameters, timeout=timeout)

    label_results = await asyncio.gather(
        *(read_label(label) for label in labels), return_exceptions=True
    )
    found = []
    ceiling = False
    for label, result in zip(labels, label_results, strict=True):
        if isinstance(result, BaseException):
            raise result
        ceiling = ceiling or len(result) >= count
        found.extend(
            _Candidate(str(row["entity_id"]), float(row["score"]), label)
            for row in result
        )
    return _ranked(found, ceiling=ceiling)


def _ranked(candidates: list[_Candidate], *, ceiling: bool) -> _Ranked:
    """Order the candidates best first and keep the first entry of each id."""
    candidates.sort(key=lambda candidate: (-candidate.score, candidate.entity_id))
    first_seen: dict[str, _Candidate] = {}
    for candidate in candidates:
        first_seen.setdefault(candidate.entity_id, candidate)
    return _Ranked(candidates=list(first_seen.values()), ceiling=ceiling)


async def _load_visible(
    store: GraphStore,
    entity_ids: Iterable[str],
    scope: frozenset[str],
    support_limit: int,
    timeout: float | None = None,
) -> dict[str, _Visible]:
    """Return the entities that have a passage in scope, with their visible support.

    An entity with no passage in scope is left out. Its passages are in other
    documents, or it has no mention at all.
    """
    ids = sorted(set(entity_ids))
    if not ids:
        return {}
    rows = await store.execute_read(
        entity_mentions_query(),
        {
            "entity_ids": ids,
            "scope_ids": sorted(scope_node_ids(scope)),
            "support_limit": support_limit,
        },
        timeout=timeout,
    )
    visible: dict[str, _Visible] = {}
    for row in rows:
        entity_id = str(row["entity_id"])
        entry = visible.get(entity_id)
        if entry is None:
            entry = _Visible(
                name=str(row["entity"].get("name", "")),
                properties=_properties(row["entity"]),
            )
            visible[entity_id] = entry
        if row["visible"]:
            stored = stored_chunk(row)
            entry.supports.append(_passage(stored.chunk, stored.document_key))
    return visible


def _properties(entity: Mapping[str, Any]) -> dict[str, object]:
    """Return the schema properties of an entity map, without internal fields."""
    return {
        key: value
        for key, value in entity.items()
        if key not in _INTERNAL_PROPERTIES and value is not None
    }


def _passage(chunk: Chunk, document_key: str) -> SupportingPassage:
    """Build the public support entry for a visible chunk."""
    return SupportingPassage(
        evidence_id=encode_evidence_id(chunk_reference(chunk)),
        document_key=document_key,
        location=chunk_location(chunk),
    )


def _combine(
    rankings: Mapping[EvidenceSearchLeg, _Ranked],
    visible: Mapping[str, _Visible],
    *,
    mode: EvidenceSearchMode,
    limit: int,
    constant: int,
) -> list[EntityHit]:
    """Fuse the legs over the visible entities, and build the best hits."""
    kept: dict[EvidenceSearchLeg, list[_Candidate]] = {
        leg: [
            candidate
            for candidate in ranked.candidates
            if candidate.entity_id in visible
        ]
        for leg, ranked in rankings.items()
    }
    legs_by_id: dict[str, list[EvidenceSearchLeg]] = defaultdict(list)
    label_by_id: dict[str, str] = {}
    raw_score: dict[str, float] = {}
    for leg in EvidenceSearchLeg:
        for candidate in kept.get(leg, []):
            legs_by_id[candidate.entity_id].append(leg)
            label_by_id.setdefault(candidate.entity_id, candidate.label)
            raw_score.setdefault(candidate.entity_id, candidate.score)

    if mode is EvidenceSearchMode.HYBRID:
        scores = reciprocal_rank_fusion(
            [
                [candidate.entity_id for candidate in kept[leg]]
                for leg in EvidenceSearchLeg
                if leg in kept
            ],
            constant=constant,
        )
    else:
        scores = raw_score
    ordered = sorted(scores, key=lambda entity_id: (-scores[entity_id], entity_id))
    return [
        EntityHit(
            entity_id=entity_id,
            label=label_by_id[entity_id],
            name=visible[entity_id].name,
            properties=visible[entity_id].properties,
            kind=visible[entity_id].kind,
            score=scores[entity_id],
            legs=legs_by_id[entity_id],
            support=visible[entity_id].supports,
        )
        for entity_id in ordered[:limit]
    ]


async def _walk(
    store: GraphStore,
    start: str,
    *,
    scope: frozenset[str],
    relation_types: Sequence[str] | None,
    depth: int,
    max_nodes: int,
    max_edges: int,
    timeout: float | None = None,
) -> tuple[list[ExplorationNode], list[ExplorationEdge], list[ExplorationBound]]:
    """Walk the entity relations breadth first and return the bounded result.

    One extra step after ``depth`` looks for connections from the last entities
    to entities not yet reached. It only sets the depth bound, and it adds nothing.
    """
    scope_ids = sorted(scope_node_ids(scope))
    types = list(relation_types or [])
    system_types = sorted(RESERVED_RELATION_TYPES)
    visited = {start}
    frontier = [start]
    seen_relations: set[str] = set()
    nodes: list[ExplorationNode] = []
    edges: list[ExplorationEdge] = []
    bounds: set[ExplorationBound] = set()
    for level in range(1, depth + 2):
        rows = await store.execute_read(
            explore_edges_query(),
            {
                "node_ids": frontier,
                "relation_types": types,
                "system_types": system_types,
                "scope_ids": scope_ids,
                "support_limit": _EDGE_SUPPORT_LIMIT,
                "row_limit": _EXPLORE_ROW_LIMIT + 1,
            },
            timeout=timeout,
        )
        if len(rows) > _EXPLORE_ROW_LIMIT:
            bounds.add(ExplorationBound.CANDIDATES)
            rows = rows[:_EXPLORE_ROW_LIMIT]
        next_frontier: list[str] = []
        for row in rows:
            relation_id = str(row["relation_id"])
            kind = _edge_kind(row)
            if relation_id in seen_relations or kind is None:
                continue
            seen_relations.add(relation_id)
            other_id = str(row["entity_id"])
            if level > depth:
                if other_id not in visited:
                    bounds.add(ExplorationBound.DEPTH)
                continue
            if other_id not in visited:
                if len(nodes) >= max_nodes:
                    bounds.add(ExplorationBound.NODES)
                    continue
                visited.add(other_id)
                next_frontier.append(other_id)
                nodes.append(
                    ExplorationNode(
                        entity_id=other_id,
                        label=str(row["label"]),
                        name=str(row["name"]),
                        depth=level,
                    )
                )
            if len(edges) >= max_edges:
                bounds.add(ExplorationBound.EDGES)
                return nodes, edges, _ordered(bounds)
            edges.append(_edge(row, kind))
        if level > depth or not next_frontier:
            break
        frontier = next_frontier
    return nodes, edges, _ordered(bounds)


def _ordered(bounds: set[ExplorationBound]) -> list[ExplorationBound]:
    """Return the bounds in a fixed order, so results compare equal."""
    return [bound for bound in ExplorationBound if bound in bounds]


def _edge_kind(row: Mapping[str, Any]) -> EdgeKind | None:
    """Return the kind of a relation row, or None when the relation is dropped.

    A relation with no source passages is a path. A relation with source passages
    is an assertion when one of them is visible in scope. A relation whose source
    passages are all hidden is dropped.
    """
    if row["source_count"] == 0:
        return EdgeKind.PATH
    if row["supports"]:
        return EdgeKind.ASSERTION
    return None


def _edge(row: Mapping[str, Any], kind: EdgeKind) -> ExplorationEdge:
    """Build the public edge for one relation row."""
    evidence = [
        _passage(stored.chunk, stored.document_key)
        for stored in (stored_chunk(support) for support in row["supports"])
    ]
    return ExplorationEdge(
        source_id=str(row["source_id"]),
        target_id=str(row["target_id"]),
        relation_type=str(row["relation_type"]),
        kind=kind,
        evidence=evidence if kind is EdgeKind.ASSERTION else [],
    )
