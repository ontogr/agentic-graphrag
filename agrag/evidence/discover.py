"""Find visible passages by full-text search, vector search, or both.

A passage is a chunk. Only current text is visible: a chunk needs an open
``HAS_PART`` edge, must not be written by an in-flight job, and must belong to a
document in the caller's scope. Those rules are part of each search query, so
out-of-scope and superseded chunks never take a result slot.
"""

import logging
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.evidence import (
    DiscoveryHit,
    DiscoveryLeg,
    DiscoveryMode,
    DiscoveryResult,
    DiscoveryStatus,
    EvidenceLocation,
    IndexState,
    LegFailure,
)
from agrag.common.data_models.provenance import PageProvenance
from agrag.cypher.evidence import (
    index_states_query,
    lexical_candidates_query,
    semantic_candidates_query,
)
from agrag.cypher.schema import fulltext_index_name, vector_index_name
from agrag.embedding.base import Embedder
from agrag.evidence._shared import (
    chunk_from_row,
    chunk_reference,
    scope_node_ids,
    text_range,
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
_ONLINE = "ONLINE"
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


async def discover(
    store: GraphStore,
    embedder: Embedder,
    query: str,
    *,
    mode: DiscoveryMode,
    limit: int,
    scope: frozenset[str],
    timeout: float | None = None,
) -> DiscoveryResult:
    """Find up to ``limit`` visible passages that match a query.

    The lexical leg matches the words of the query against chunk text. The
    semantic leg embeds the query and searches the chunk embeddings. The hybrid
    mode runs both and fuses them. Discovery returns status ``index_not_ready``
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
        return DiscoveryResult(status=DiscoveryStatus.EMPTY_SCOPE)

    legs = (
        [DiscoveryLeg.LEXICAL, DiscoveryLeg.SEMANTIC]
        if mode is DiscoveryMode.HYBRID
        else [DiscoveryLeg(mode.value)]
    )
    index_names = _index_names(legs)
    index_state = await _index_state(store, list(index_names.values()), timeout=timeout)
    if index_state is IndexState.NOT_READY:
        return DiscoveryResult(
            status=DiscoveryStatus.INDEX_NOT_READY, index_state=index_state
        )

    scope_ids = sorted(scope_node_ids(scope))
    rankings: dict[DiscoveryLeg, list[_Visible]] = {}
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
        status = DiscoveryStatus.FAILED
    elif failures:
        status = DiscoveryStatus.PARTIAL
    elif hits:
        status = DiscoveryStatus.OK
    else:
        status = DiscoveryStatus.NO_MATCH
    return DiscoveryResult(
        status=status,
        hits=hits,
        truncated=truncated and len(hits) < limit,
        index_state=index_state,
        failures=failures,
    )


def _index_names(legs: Sequence[DiscoveryLeg]) -> dict[DiscoveryLeg, str]:
    """Return the index name each leg searches."""
    names: dict[DiscoveryLeg, str] = {}
    if DiscoveryLeg.LEXICAL in legs:
        names[DiscoveryLeg.LEXICAL] = fulltext_index_name(
            CHUNK_LABEL, _FULLTEXT_PROPERTIES
        )
    if DiscoveryLeg.SEMANTIC in legs:
        names[DiscoveryLeg.SEMANTIC] = vector_index_name(
            CHUNK_LABEL, _EMBEDDING_PROPERTY
        )
    return names


async def _index_state(
    store: GraphStore, names: Sequence[str], *, timeout: float | None
) -> IndexState:
    """Return READY when every named index exists and is ONLINE."""
    rows = await store.execute_read(
        index_states_query(), {"names": list(names)}, timeout=timeout
    )
    states = {row["name"]: row["state"] for row in rows}
    if all(states.get(name) == _ONLINE for name in names):
        return IndexState.READY
    return IndexState.NOT_READY


def _lucene_terms(query: str) -> str:
    """Return the query as plain terms that Lucene cannot read as operators.

    Only word characters survive, so no operator, field name, quote or
    escape reaches the parser. Words are lowercased, so ``AND`` and ``NOT``
    are not operators in any case.
    """
    return " ".join(re.findall(r"\w+", query.lower()))


async def _run_leg(
    store: GraphStore,
    embedder: Embedder,
    leg: DiscoveryLeg,
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
    if leg is DiscoveryLeg.LEXICAL:
        terms = _lucene_terms(query)
        if not terms:
            return [], False
        statement = lexical_candidates_query()
        parameters: dict[str, Any] = {
            "index": fulltext_index_name(CHUNK_LABEL, _FULLTEXT_PROPERTIES),
            "query": terms,
        }
    else:
        [vector] = await embedder.embed([query])
        statement = semantic_candidates_query()
        parameters = {
            "index": vector_index_name(CHUNK_LABEL, _EMBEDDING_PROPERTY),
            "vector": list(vector),
        }

    candidates = limit
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
    rankings: Mapping[DiscoveryLeg, list[_Visible]],
    *,
    mode: DiscoveryMode,
    limit: int,
) -> list[DiscoveryHit]:
    """Merge the legs into hits, one per evidence id, best first."""
    by_id: dict[str, _Visible] = {}
    legs_by_id: dict[str, list[DiscoveryLeg]] = defaultdict(list)
    for leg in DiscoveryLeg:
        for item in rankings.get(leg, []):
            by_id.setdefault(item.evidence_id, item)
            legs_by_id[item.evidence_id].append(leg)

    if mode is DiscoveryMode.HYBRID:
        ranked_ids = [
            [item.evidence_id for item in rankings[leg]]
            for leg in DiscoveryLeg
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


def _hit(item: _Visible, score: float, legs: list[DiscoveryLeg]) -> DiscoveryHit:
    """Build the public hit for one visible chunk."""
    chunk = item.chunk
    bounds = text_range(chunk)
    if bounds is not None:
        location = EvidenceLocation(char_start=bounds[0], char_end=bounds[1])
    elif isinstance(chunk.provenance, PageProvenance):
        location = EvidenceLocation(
            page_numbers=[span.page_no for span in chunk.provenance.page_spans]
        )
    else:
        location = EvidenceLocation()
    return DiscoveryHit(
        evidence_id=item.evidence_id,
        document_key=item.document_key,
        title=item.title,
        content_hash=chunk.content_hash,
        location=location,
        snippet=chunk.text[:_SNIPPET_CHARS],
        score=score,
        legs=legs,
    )
