"""Find entities by name or meaning, and explore typed relations around one entity.

An entity is returned only with the passages that mention it, and only when at
least one of those passages is in the caller's scope. Each passage is an evidence
id. An entity whose passages are all superseded is returned as unsupported, with
no passages. Exploration follows entity-to-entity relations with bounded depth,
size and edge count. A relation with a visible passage is an assertion, and a
connection with no passage is a path.
"""

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
from agrag.common.data_models.resolved_entity import RESOLVED_ENTITY_LABEL
from agrag.cypher.evidence import (
    entity_candidates_query,
    entity_labels_query,
    entity_mentions_query,
    explore_edges_query,
)
from agrag.cypher.schema import fulltext_index_name, vector_index_name
from agrag.embedding.base import Embedder
from agrag.evidence._shared import (
    IndexSpec,
    chunk_location,
    chunk_reference,
    indexes_ready,
    lucene_terms,
    scope_node_ids,
    stored_chunk,
)
from agrag.evidence.ids import encode_evidence_id
from agrag.evidence.search import RRF_CONSTANT, reciprocal_rank_fusion
from agrag.graphdb.base import GraphStore


_LOGGER = logging.getLogger(__name__)
_LEG_FAILED_MESSAGE = "search leg failed"
_STORE_ERROR_MESSAGE = "entity store error"
_NAME_PROPERTY = "name"
_EMBEDDING_PROPERTY = "embedding"
_FULLTEXT_TYPE = "FULLTEXT"
_VECTOR_TYPE = "VECTOR"
_CANDIDATE_MULTIPLIER = 4
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
_MAX_DEPTH = 2
_MAX_EXPLORE_BOUND = 200
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
    limit: int,
    mode: EvidenceSearchMode = EvidenceSearchMode.HYBRID,
    support_limit: int = 3,
) -> EntityResult:
    """Find up to ``limit`` entities that match a query by name or by meaning.

    The lexical leg matches the words of the query against the ``name`` of each
    entity. The semantic leg embeds the query and searches the ``embedding`` of
    each entity. The hybrid mode runs both and fuses the rankings with reciprocal
    rank fusion. Each label needs a full-text index on ``name`` and a vector index
    on ``embedding``. A missing or offline index gives ``index_not_ready``.

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
        labels: The entity labels to search. None searches every entity label that
            has a vector index, which is every label the graph schema declares.
        limit: The most entities to return. Must be positive.
        mode: Which legs to run.
        support_limit: The most supporting passages listed for each entity. Must
            be positive.

    Returns:
        The entities, best first, with the status and the index state.

    Raises:
        ValueError: ``limit`` or ``support_limit`` is not positive.
    """
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}")
    if support_limit <= 0:
        raise ValueError(f"support_limit must be positive, got {support_limit}")
    if not scope:
        return EntityResult(status=EvidenceSearchStatus.EMPTY_SCOPE)

    entity_labels = await _entity_labels(store, labels)
    if not entity_labels:
        return EntityResult(status=EvidenceSearchStatus.NO_MATCH)
    legs = (
        [EvidenceSearchLeg.LEXICAL, EvidenceSearchLeg.SEMANTIC]
        if mode is EvidenceSearchMode.HYBRID
        else [EvidenceSearchLeg(mode.value)]
    )
    index_state = await indexes_ready(store, _index_specs(entity_labels, legs))
    if index_state is IndexState.NOT_READY:
        return EntityResult(
            status=EvidenceSearchStatus.INDEX_NOT_READY, index_state=index_state
        )

    candidate_count = min(limit * _CANDIDATE_MULTIPLIER, _MAX_CANDIDATES)
    rankings: dict[EvidenceSearchLeg, _Ranked] = {}
    failures: list[LegFailure] = []
    for leg in legs:
        try:
            rankings[leg] = await _leg_candidates(
                store,
                embedder,
                leg=leg,
                query=query,
                labels=entity_labels,
                count=candidate_count,
            )
        except Exception:
            _LOGGER.exception("Entity search leg %s failed", leg.value)
            failures.append(LegFailure(leg=leg, message=_LEG_FAILED_MESSAGE))

    candidate_ids = {
        candidate.entity_id
        for ranked in rankings.values()
        for candidate in ranked.candidates
    }
    try:
        visible = await _load_visible(store, candidate_ids, scope, support_limit)
    except Exception:
        _LOGGER.exception("Entity support query failed")
        return EntityResult(
            status=EvidenceSearchStatus.FAILED,
            index_state=index_state,
            failures=[
                LegFailure(leg=leg, message=_STORE_ERROR_MESSAGE) for leg in legs
            ],
        )

    hits = _combine(rankings, visible, mode=mode, limit=limit)
    truncated = any(ranked.ceiling for ranked in rankings.values())
    if failures and len(failures) == len(legs):
        status = EvidenceSearchStatus.FAILED
    elif failures:
        status = EvidenceSearchStatus.PARTIAL
    elif hits:
        status = EvidenceSearchStatus.OK
    else:
        status = EvidenceSearchStatus.NO_MATCH
    return EntityResult(
        status=status,
        hits=hits,
        truncated=truncated and len(hits) < limit,
        index_state=index_state,
        failures=failures,
    )


async def explore_relationships(
    store: GraphStore,
    entity_id: str,
    *,
    scope: frozenset[str],
    relation_types: Sequence[str] | None = None,
    depth: int = 1,
    max_nodes: int = 25,
    max_edges: int = 50,
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

    Returns:
        The nodes, edges and bounds. An unavailable or malformed start gives no
        nodes or edges.

    Raises:
        ValueError: ``depth``, ``max_nodes`` or ``max_edges`` is outside its range.
    """
    if not 1 <= depth <= _MAX_DEPTH:
        raise ValueError(f"depth must be 1 or 2, got {depth}")
    if not 1 <= max_nodes <= _MAX_EXPLORE_BOUND:
        raise ValueError(
            f"max_nodes must be 1 to {_MAX_EXPLORE_BOUND}, got {max_nodes}"
        )
    if not 1 <= max_edges <= _MAX_EXPLORE_BOUND:
        raise ValueError(
            f"max_edges must be 1 to {_MAX_EXPLORE_BOUND}, got {max_edges}"
        )
    if not _is_canonical_uuid(entity_id):
        return ExplorationResult(
            status=ExplorationStatus.MALFORMED, detail="not an entity id"
        )
    if not scope:
        return ExplorationResult(status=ExplorationStatus.UNAVAILABLE)

    try:
        visible = await _load_visible(store, {entity_id}, scope, 1)
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


async def _entity_labels(store: GraphStore, labels: Sequence[str] | None) -> list[str]:
    """Return the labels to search, given or discovered from the vector indexes."""
    if labels is not None:
        return sorted(set(labels))
    rows = await store.execute_read(entity_labels_query())
    found = {str(label) for row in rows for label in row["labels"]}
    return sorted(found - _NON_ENTITY_LABELS)


def _index_specs(
    labels: Iterable[str], legs: Sequence[EvidenceSearchLeg]
) -> list[IndexSpec]:
    """Return the index each leg of each label searches, with its expected shape."""
    specs: list[IndexSpec] = []
    for label in labels:
        if EvidenceSearchLeg.LEXICAL in legs:
            specs.append(
                IndexSpec(
                    name=fulltext_index_name(label, [_NAME_PROPERTY]),
                    index_type=_FULLTEXT_TYPE,
                    label=label,
                    prop=_NAME_PROPERTY,
                )
            )
        if EvidenceSearchLeg.SEMANTIC in legs:
            specs.append(
                IndexSpec(
                    name=vector_index_name(label, _EMBEDDING_PROPERTY),
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
) -> _Ranked:
    """Return the candidates of one leg over every label, best first, once each."""
    terms = ""
    vector: list[float] = []
    if leg is EvidenceSearchLeg.LEXICAL:
        terms = lucene_terms(query)
        if not terms:
            return _Ranked(candidates=[], ceiling=False)
    else:
        [embedded] = await embedder.embed([query])
        vector = list(embedded)

    found: list[_Candidate] = []
    ceiling = False
    for label in labels:
        if leg is EvidenceSearchLeg.LEXICAL:
            statement = entity_candidates_query(label, lexical=True)
            parameters: dict[str, Any] = {
                "index": fulltext_index_name(label, [_NAME_PROPERTY]),
                "fulltext_terms": terms,
                "k": count,
            }
        else:
            statement = entity_candidates_query(label, lexical=False)
            parameters = {
                "index": vector_index_name(label, _EMBEDDING_PROPERTY),
                "vector": vector,
                "k": count,
            }
        rows = await store.execute_read(statement, parameters)
        ceiling = ceiling or len(rows) >= count
        found.extend(
            _Candidate(str(row["entity_id"]), float(row["score"]), label)
            for row in rows
        )
    found.sort(key=lambda candidate: (-candidate.score, candidate.entity_id))
    first_seen: dict[str, _Candidate] = {}
    for candidate in found:
        first_seen.setdefault(candidate.entity_id, candidate)
    return _Ranked(candidates=list(first_seen.values()), ceiling=ceiling)


async def _load_visible(
    store: GraphStore,
    entity_ids: Iterable[str],
    scope: frozenset[str],
    support_limit: int,
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
            constant=RRF_CONSTANT,
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
