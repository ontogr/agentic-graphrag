"""Find visible passages by full-text search, vector search, or both.

A passage is a chunk. Only current text is visible: a chunk needs an open
``HAS_PART`` edge, must not be written by an in-flight job, and must belong to a
document in the caller's scope. Those rules are part of each search query, so
out-of-scope and superseded chunks never take a result slot.
"""

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.evidence import (
    EvidenceSearchHit,
    EvidenceSearchLeg,
    EvidenceSearchMode,
    EvidenceSearchResult,
    EvidenceSearchStatus,
    IndexState,
    LegFailure,
)
from agrag.cypher.evidence import (
    lexical_candidates_query,
    semantic_candidates_query,
)
from agrag.cypher.schema import fulltext_index_name, vector_index_name
from agrag.embedding.base import Embedder
from agrag.evidence._shared import (
    IndexSpec,
    chunk_from_row,
    chunk_location,
    chunk_reference,
    indexes_ready,
    lucene_terms,
    scope_node_ids,
)
from agrag.evidence.ids import encode_evidence_id
from agrag.graphdb.base import GraphStore


# Constant of reciprocal rank fusion. The value 60 is the one from the original
# RRF paper, and it damps the effect of the top ranks.
_LOGGER = logging.getLogger(__name__)
_LEG_FAILED_MESSAGE = "search leg failed"
RRF_CONSTANT = 60
_SNIPPET_CHARS = 240
_CANDIDATE_MULTIPLIER = 4
_MAX_CANDIDATES = 1000
_FULLTEXT_TYPE = "FULLTEXT"
_VECTOR_TYPE = "VECTOR"
_FULLTEXT_PROPERTIES = ["text"]
_EMBEDDING_PROPERTY = "embedding"


@dataclass(frozen=True)
class _Visible:
    """One visible chunk as one search leg returned it."""

    evidence_id: str
    chunk: Chunk
    document_key: str
    title: str
    score: float


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], *, constant: int = RRF_CONSTANT
) -> dict[str, float]:
    """Fuse ranked id lists into one score per id.

    Each list adds ``1 / (constant + rank)`` to the score of every id it contains,
    with ranks starting at 1. An id that several lists rank highly scores highest.

    Args:
        rankings: Lists of ids, best first. An id should appear once per list.
        constant: The damping constant of the formula.

    Returns:
        The fused score of each id that appears in any list.
    """
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] += 1.0 / (constant + rank)
    return dict(scores)


async def search_evidence(
    store: GraphStore,
    embedder: Embedder,
    query: str,
    *,
    mode: EvidenceSearchMode,
    limit: int,
    scope: frozenset[str],
    timeout: float | None = None,
) -> EvidenceSearchResult:
    """Find up to ``limit`` visible passages that match a query.

    The lexical leg matches the words of the query against chunk text. The
    semantic leg embeds the query and searches the chunk embeddings. The hybrid
    mode runs both and fuses them. Search returns status ``index_not_ready``
    when a needed index is missing or not ONLINE. It returns ``empty_scope``
    without searching when ``scope`` is empty.

    Args:
        store: The graph store to search.
        embedder: Embeds the query for the semantic leg. The lexical leg does not
            use it.
        query: The query text. Lucene syntax is not applied: each word is
            searched as a plain term.
        mode: Which legs to run.
        limit: The most hits to return. Must be positive.
        scope: Keys of the documents that may be searched.
        timeout: Server-side transaction timeout in seconds for each store read.
            None uses the server's default.

    Returns:
        The hits, best first, with the status, truncation flag, index state and
        any failed legs.

    Raises:
        ValueError: ``limit`` is not positive.
    """
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}")
    if not scope:
        return EvidenceSearchResult(status=EvidenceSearchStatus.EMPTY_SCOPE)

    legs = (
        [EvidenceSearchLeg.LEXICAL, EvidenceSearchLeg.SEMANTIC]
        if mode is EvidenceSearchMode.HYBRID
        else [EvidenceSearchLeg(mode.value)]
    )
    try:
        index_state = await indexes_ready(store, _index_specs(legs), timeout=timeout)
    except Exception:
        _LOGGER.exception("Evidence index state read failed")
        return EvidenceSearchResult(status=EvidenceSearchStatus.FAILED)
    if index_state is IndexState.NOT_READY:
        return EvidenceSearchResult(
            status=EvidenceSearchStatus.INDEX_NOT_READY, index_state=index_state
        )

    scope_ids = sorted(scope_node_ids(scope))
    rankings: dict[EvidenceSearchLeg, list[_Visible]] = {}
    failures: list[LegFailure] = []
    truncated = False
    for leg in legs:
        try:
            visible, leg_truncated = await _run_leg(
                store,
                embedder,
                leg,
                query,
                scope_ids=scope_ids,
                limit=limit,
                timeout=timeout,
            )
        except Exception:
            _LOGGER.exception("Evidence search leg %s failed", leg.value)
            failures.append(LegFailure(leg=leg, message=_LEG_FAILED_MESSAGE))
            continue
        rankings[leg] = visible
        truncated = truncated or leg_truncated

    hits = _combine(rankings, mode=mode, limit=limit)
    if failures and len(failures) == len(legs):
        status = EvidenceSearchStatus.FAILED
    elif failures:
        status = EvidenceSearchStatus.PARTIAL
    elif hits:
        status = EvidenceSearchStatus.OK
    else:
        status = EvidenceSearchStatus.NO_MATCH
    return EvidenceSearchResult(
        status=status,
        hits=hits,
        truncated=truncated,
        index_state=index_state,
        failures=failures,
    )


def _index_specs(legs: Sequence[EvidenceSearchLeg]) -> list[IndexSpec]:
    """Return the index each leg searches."""
    specs: list[IndexSpec] = []
    if EvidenceSearchLeg.LEXICAL in legs:
        specs.append(
            IndexSpec(
                name=fulltext_index_name(CHUNK_LABEL, _FULLTEXT_PROPERTIES),
                index_type=_FULLTEXT_TYPE,
                label=CHUNK_LABEL,
                prop=_FULLTEXT_PROPERTIES[0],
            )
        )
    if EvidenceSearchLeg.SEMANTIC in legs:
        specs.append(
            IndexSpec(
                name=vector_index_name(CHUNK_LABEL, _EMBEDDING_PROPERTY),
                index_type=_VECTOR_TYPE,
                label=CHUNK_LABEL,
                prop=_EMBEDDING_PROPERTY,
            )
        )
    return specs


async def _run_leg(
    store: GraphStore,
    embedder: Embedder,
    leg: EvidenceSearchLeg,
    query: str,
    *,
    scope_ids: list[str],
    limit: int,
    timeout: float | None,
) -> tuple[list[_Visible], bool]:
    """Return the visible hits of one leg and whether the search hit its ceiling.

    The candidate count grows until ``limit`` visible chunks are found, the index
    runs out of candidates, or the ceiling is reached.
    """
    if leg is EvidenceSearchLeg.LEXICAL:
        terms = lucene_terms(query)
        if not terms:
            return [], False
        call = await store.fulltext_search_call(
            label=CHUNK_LABEL, properties=_FULLTEXT_PROPERTIES
        )
        statement = lexical_candidates_query(call.text)
        parameters: dict[str, Any] = {**call.params, "fulltext_terms": terms}
    else:
        [vector] = await embedder.embed([query])
        call = await store.vector_search_call(
            label=CHUNK_LABEL, vector_property=_EMBEDDING_PROPERTY
        )
        statement = semantic_candidates_query(call.text)
        parameters = {**call.params, "vector": list(vector)}

    candidates = min(limit, _MAX_CANDIDATES)
    while True:
        rows = await store.execute_read(
            statement,
            {**parameters, "k": candidates, "scope_ids": scope_ids},
            timeout=timeout,
        )
        visible = _visible_rows(rows)
        if len(visible) >= limit:
            return visible[:limit], False
        if _candidate_count(rows) < candidates:
            return visible, False
        if candidates >= _MAX_CANDIDATES:
            return visible, True
        candidates = min(candidates * _CANDIDATE_MULTIPLIER, _MAX_CANDIDATES)


def _candidate_count(rows: Sequence[Mapping[str, Any]]) -> int:
    """Return the number of distinct candidate chunks, visible or not."""
    return len({row["chunk_id"] for row in rows})


def _visible_rows(rows: Sequence[Mapping[str, Any]]) -> list[_Visible]:
    """Return the visible chunks among candidate rows, best first and unique.

    A candidate is visible when the query found its document. Other rows
    have null document fields and are skipped.
    """
    seen: set[str] = set()
    visible: list[_Visible] = []
    for row in rows:
        chunk_id = str(row["chunk_id"])
        if chunk_id in seen or row["document_key"] is None:
            continue
        seen.add(chunk_id)
        chunk = chunk_from_row(row["chunk"])
        visible.append(
            _Visible(
                evidence_id=encode_evidence_id(chunk_reference(chunk)),
                chunk=chunk,
                document_key=row["document_key"],
                title=row["title"] or "",
                score=float(row["score"]),
            )
        )
    return visible


def _combine(
    rankings: Mapping[EvidenceSearchLeg, list[_Visible]],
    *,
    mode: EvidenceSearchMode,
    limit: int,
) -> list[EvidenceSearchHit]:
    """Merge the legs into hits, one per evidence id, best first."""
    by_id: dict[str, _Visible] = {}
    legs_by_id: dict[str, list[EvidenceSearchLeg]] = defaultdict(list)
    for leg in EvidenceSearchLeg:
        for item in rankings.get(leg, []):
            by_id.setdefault(item.evidence_id, item)
            legs_by_id[item.evidence_id].append(leg)

    if mode is EvidenceSearchMode.HYBRID:
        ranked_ids = [
            [item.evidence_id for item in rankings[leg]]
            for leg in EvidenceSearchLeg
            if leg in rankings
        ]
        scores = reciprocal_rank_fusion(ranked_ids)
    else:
        scores = {evidence_id: item.score for evidence_id, item in by_id.items()}

    ordered = sorted(by_id, key=lambda evidence_id: (-scores[evidence_id], evidence_id))
    return [
        _hit(by_id[evidence_id], scores[evidence_id], legs_by_id[evidence_id])
        for evidence_id in ordered[:limit]
    ]


def _hit(
    item: _Visible, score: float, legs: list[EvidenceSearchLeg]
) -> EvidenceSearchHit:
    """Build the public hit for one visible chunk."""
    chunk = item.chunk
    return EvidenceSearchHit(
        evidence_id=item.evidence_id,
        document_key=item.document_key,
        title=item.title,
        content_hash=chunk.content_hash,
        location=chunk_location(chunk),
        snippet=chunk.text[:_SNIPPET_CHARS],
        score=score,
        legs=legs,
    )
