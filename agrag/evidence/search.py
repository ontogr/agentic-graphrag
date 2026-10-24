"""Find visible passages by full-text search, vector search, or both.

A passage is a chunk. Only current text is visible: a chunk needs an open
``HAS_PART`` edge, must not be written by an in-flight job, and must belong to a
document in the caller's scope. Those rules are part of each search query, so
out-of-scope and superseded chunks never take a result slot.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
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
from agrag.common.data_models.index_record import IndexInfo
from agrag.common.data_models.vector_record import VectorHit, VectorKind
from agrag.cypher.evidence import (
    lexical_candidates_query,
    semantic_candidates_from_rows_query,
    semantic_candidates_query,
)
from agrag.cypher.schema import vector_index_name
from agrag.embedding.base import Embedder
from agrag.evidence._shared import (
    EMBEDDING_MISMATCH_MESSAGE,
    IndexSpec,
    chunk_from_row,
    chunk_location,
    chunk_reference,
    embedding_matches,
    indexes_ready,
    lucene_terms,
    run_with_timeout,
    scope_node_ids,
    stores_ready,
)
from agrag.evidence.contract import DEFAULT_SEARCH_LIMIT
from agrag.evidence.ids import encode_evidence_id
from agrag.evidence.rerank import Reranker
from agrag.graphdb.base import GraphStore
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


_LOGGER = logging.getLogger(__name__)
_LEG_FAILED_MESSAGE = "search leg failed"
_RERANK_FAILED_MESSAGE = "rerank failed"
_SNIPPET_CHARS = 240
_MAX_CANDIDATES = 1000
_FULLTEXT_TYPE = "FULLTEXT"
_VECTOR_TYPE = "VECTOR"
_FULLTEXT_PROPERTIES = ["text"]
_EMBEDDING_PROPERTY = "embedding"

_RowSequence = Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class _Visible:
    """One visible chunk as one search leg returned it."""

    evidence_id: str
    chunk: Chunk
    document_key: str
    title: str
    score: float


@dataclass(frozen=True)
class _Fused:
    """One visible chunk with its fused score and the legs that found it."""

    item: _Visible
    score: float
    legs: list[EvidenceSearchLeg]


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], *, constant: int = 60
) -> dict[str, float]:
    """Fuse ranked id lists into one score per id.

    Each list adds ``1 / (constant + rank)`` to the score of every id it contains,
    with ranks starting at 1. An id that several lists rank highly scores highest.

    Args:
        rankings: Lists of ids, best first. An id should appear once per list.
        constant: The damping constant of the formula. The value 60 is the one
            from the original RRF paper, and it damps the effect of the top
            ranks.

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
    mode: EvidenceSearchMode = EvidenceSearchMode.HYBRID,
    limit: int = DEFAULT_SEARCH_LIMIT,
    scope: frozenset[str],
    vector_store: VectorStore | None = None,
    reranker: Reranker | None = None,
    settings: RetrievalSettings | None = None,
    timeout: float | None = None,
) -> EvidenceSearchResult:
    """Find up to ``limit`` visible passages that match a query.

    The lexical leg matches the words of the query against chunk text. The
    semantic leg embeds the query and searches the chunk embeddings. The hybrid
    mode runs both and fuses them, or delegates fusion to an external store.
    Hybrid mode with a reranker reorders the top fused hits with the
    cross-encoder, and lexical and semantic modes never rerank. Search returns
    status ``index_not_ready`` when a needed index or external collection is
    missing. It returns ``empty_scope`` without searching when ``scope`` is
    empty.

    Args:
        store: The graph store to search.
        embedder: Embeds the query for the semantic leg. The lexical leg does not
            use it.
        query: The query text. Lucene syntax is not applied: each word is
            searched as a plain term.
        mode: Which legs to run.
        limit: The most hits to return. Must be positive.
        scope: Keys of the documents that may be searched.
        vector_store: Optional external vector store. Placement is not validated
            by this function.
        reranker: Scores passage texts against the query to reorder the top
            fused hits of hybrid mode. None runs hybrid search without rerank.
        settings: Fusion and rerank configuration. None uses the defaults.
        timeout: Server-side transaction timeout in seconds for each store read.
            None uses the server's default.

    Returns:
        The hits, best first, with the status, truncation flag, index state and
        any failed legs. A failed rerank stage is recorded in the failures and
        leaves the status and the fused order unchanged.

    Raises:
        ValueError: ``limit`` is not positive.
    """
    retrieval = settings or RetrievalSettings()
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}")
    if not scope:
        return EvidenceSearchResult(status=EvidenceSearchStatus.EMPTY_SCOPE)

    try:
        indexes = await store.list_indexes(timeout=timeout)
    except Exception:
        _LOGGER.exception("Evidence index state read failed")
        return EvidenceSearchResult(status=EvidenceSearchStatus.FAILED)

    semantic_failure = await _semantic_guard_failure(
        embedder,
        mode=mode,
        indexes=indexes,
        vector_store=vector_store,
        timeout=timeout,
    )
    legs = _search_legs(mode, vector_store)
    if semantic_failure is not None:
        if mode is EvidenceSearchMode.HYBRID:
            legs = [EvidenceSearchLeg.LEXICAL]
        else:
            return EvidenceSearchResult(
                status=EvidenceSearchStatus.FAILED, failures=[semantic_failure]
            )

    index_state, error = await _readiness(
        store, legs, vector_store=vector_store, indexes=indexes, timeout=timeout
    )
    if error is not None:
        return error

    wanted = (
        max(limit, retrieval.rerank_candidates)
        if mode is EvidenceSearchMode.HYBRID and reranker is not None
        else limit
    )
    rankings, leg_failures, truncated = await _gather_legs(
        store,
        embedder,
        legs,
        query,
        mode=mode,
        scope_ids=sorted(scope_node_ids(scope)),
        wanted=wanted,
        vector_store=vector_store,
        alpha=retrieval.hybrid_alpha,
        timeout=timeout,
    )
    failures: list[LegFailure] = []
    if semantic_failure is not None:
        failures.append(semantic_failure)
    failures.extend(leg_failures)

    fused = _combine(rankings, mode=mode, wanted=wanted)
    status = _result_status(leg_failures, len(legs), semantic_failure, fused)

    reranked = False
    if mode is EvidenceSearchMode.HYBRID and reranker is not None and len(fused) >= 2:
        fused, reranked = await _rerank(fused, query, reranker, retrieval, failures)

    return EvidenceSearchResult(
        status=status,
        hits=[_hit(entry) for entry in fused[:limit]],
        truncated=truncated,
        index_state=index_state,
        failures=failures,
        reranked=reranked,
    )


def _search_legs(
    mode: EvidenceSearchMode, vector_store: VectorStore | None
) -> list[EvidenceSearchLeg]:
    """Return the search legs the mode and backend support."""
    if mode is not EvidenceSearchMode.HYBRID:
        return [EvidenceSearchLeg(mode.value)]
    if vector_store is not None:
        return [EvidenceSearchLeg.SEMANTIC]
    return [EvidenceSearchLeg.LEXICAL, EvidenceSearchLeg.SEMANTIC]


async def _readiness(
    store: GraphStore,
    legs: Sequence[EvidenceSearchLeg],
    *,
    vector_store: VectorStore | None,
    indexes: Sequence[IndexInfo],
    timeout: float | None,
) -> tuple[IndexState, EvidenceSearchResult | None]:
    """Return the index state, or the error result of an unreadable store.

    The result is None when the needed indexes and collections were checked.
    """
    try:
        index_state = await indexes_ready(
            store,
            _index_specs(legs, vector_store=vector_store),
            timeout=timeout,
            indexes=indexes,
        )
        store_state = await stores_ready(
            vector_store,
            [VectorKind.CHUNK]
            if vector_store is not None and EvidenceSearchLeg.SEMANTIC in legs
            else [],
            timeout=timeout,
        )
        if store_state is IndexState.NOT_READY:
            index_state = IndexState.NOT_READY
    except Exception:
        _LOGGER.exception("Evidence index state read failed")
        return IndexState.READY, EvidenceSearchResult(
            status=EvidenceSearchStatus.FAILED
        )
    if index_state is IndexState.NOT_READY:
        return index_state, EvidenceSearchResult(
            status=EvidenceSearchStatus.INDEX_NOT_READY, index_state=index_state
        )
    return index_state, None


async def _gather_legs(
    store: GraphStore,
    embedder: Embedder,
    legs: Sequence[EvidenceSearchLeg],
    query: str,
    *,
    mode: EvidenceSearchMode,
    scope_ids: list[str],
    wanted: int,
    vector_store: VectorStore | None,
    alpha: float,
    timeout: float | None,
) -> tuple[dict[EvidenceSearchLeg, list[_Visible]], list[LegFailure], bool]:
    """Run the legs together and collect their rankings, failures and truncation."""
    results = await asyncio.gather(
        *(
            _run_leg(
                store,
                embedder,
                leg,
                query,
                mode=mode,
                scope_ids=scope_ids,
                wanted=wanted,
                vector_store=vector_store,
                alpha=alpha,
                timeout=timeout,
            )
            for leg in legs
        ),
        return_exceptions=True,
    )
    rankings: dict[EvidenceSearchLeg, list[_Visible]] = {}
    leg_failures: list[LegFailure] = []
    truncated = False
    for leg, result in zip(legs, results, strict=True):
        if isinstance(result, asyncio.CancelledError):
            raise result
        if isinstance(result, BaseException):
            _LOGGER.error("Evidence search leg %s failed: %r", leg.value, result)
            leg_failures.append(LegFailure(leg=leg, message=_LEG_FAILED_MESSAGE))
            continue
        visible, leg_truncated = result
        rankings[leg] = visible
        truncated = truncated or leg_truncated
    return rankings, leg_failures, truncated


def _result_status(
    leg_failures: Sequence[LegFailure],
    leg_count: int,
    semantic_failure: LegFailure | None,
    fused: Sequence[_Fused],
) -> EvidenceSearchStatus:
    """Return the aggregate status from the completed legs.

    A withdrawn semantic leg makes a completed search partial even without a
    failed leg.
    """
    if leg_failures and len(leg_failures) == leg_count:
        return EvidenceSearchStatus.FAILED
    if leg_failures or semantic_failure is not None:
        return EvidenceSearchStatus.PARTIAL
    if fused:
        return EvidenceSearchStatus.OK
    return EvidenceSearchStatus.NO_MATCH


async def _rerank(
    fused: list[_Fused],
    query: str,
    reranker: Reranker,
    retrieval: RetrievalSettings,
    failures: list[LegFailure],
) -> tuple[list[_Fused], bool]:
    """Reorder the top fused hits with the reranker.

    On any reranker failure the fused order and scores stand, the failure is
    recorded, and the status is left alone.

    Returns:
        The hits in their final order and whether the reranker rescored them.
    """
    top = fused[: min(len(fused), retrieval.rerank_candidates)]
    try:
        async with asyncio.timeout(retrieval.rerank_timeout_seconds):
            scores = await reranker(query, [entry.item.chunk.text for entry in top])
    except asyncio.CancelledError:
        raise
    except Exception:
        _LOGGER.exception("Evidence rerank stage failed")
        failures.append(
            LegFailure(leg=EvidenceSearchLeg.RERANK, message=_RERANK_FAILED_MESSAGE)
        )
        return fused, False
    rescored = [
        replace(entry, score=float(score))
        for entry, score in zip(top, scores, strict=True)
    ]
    rescored.sort(key=lambda entry: (-entry.score, entry.item.evidence_id))
    return [*rescored, *fused[len(top) :]], True


async def _semantic_guard_failure(
    embedder: Embedder,
    *,
    mode: EvidenceSearchMode,
    indexes: Sequence[IndexInfo],
    vector_store: VectorStore | None,
    timeout: float | None,
) -> LegFailure | None:
    """Return the semantic failure recorded by the dimension guard, or None.

    A dimension mismatch and an unreadable embedder both withdraw the semantic
    leg; only the mismatch carries the mismatch message.
    """
    if mode is EvidenceSearchMode.LEXICAL:
        return None
    try:
        matched = await embedding_matches(
            embedder,
            indexes=indexes,
            index_name=vector_index_name(CHUNK_LABEL, _EMBEDDING_PROPERTY),
            vector_store=vector_store,
            kind=VectorKind.CHUNK,
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


def _index_specs(
    legs: Sequence[EvidenceSearchLeg], *, vector_store: VectorStore | None = None
) -> list[IndexSpec]:
    """Return the index each leg searches."""
    specs: list[IndexSpec] = []
    if EvidenceSearchLeg.LEXICAL in legs:
        specs.append(
            IndexSpec(
                index_type=_FULLTEXT_TYPE,
                label=CHUNK_LABEL,
                prop=_FULLTEXT_PROPERTIES[0],
            )
        )
    if EvidenceSearchLeg.SEMANTIC in legs and vector_store is None:
        specs.append(
            IndexSpec(
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
    mode: EvidenceSearchMode,
    scope_ids: list[str],
    wanted: int,
    vector_store: VectorStore | None,
    alpha: float,
    timeout: float | None,
) -> tuple[list[_Visible], bool]:
    """Return the visible hits of one leg and whether the search hit its ceiling.

    The leg reads candidates at most twice: once at twice the wanted count, and
    once more at the ceiling when the first read filled up without enough
    visible chunks.
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

        async def read(count: int) -> _RowSequence:
            return await store.execute_read(
                statement,
                {**parameters, "k": count, "scope_ids": scope_ids},
                timeout=timeout,
            )

        return await _bounded_read(
            read,
            first=min(wanted * 2, _MAX_CANDIDATES),
            ceiling=_MAX_CANDIDATES,
            wanted=wanted,
        )

    [vector] = await embedder.embed([query])
    if vector_store is not None:
        return await _run_external_semantic_leg(
            store,
            vector_store,
            vector,
            query,
            mode=mode,
            scope_ids=scope_ids,
            wanted=wanted,
            alpha=alpha,
            timeout=timeout,
        )
    call = await store.vector_search_call(
        label=CHUNK_LABEL, vector_property=_EMBEDDING_PROPERTY
    )
    statement = semantic_candidates_query(call.text)
    parameters = {**call.params, "vector": list(vector)}

    async def read(count: int) -> _RowSequence:
        return await store.execute_read(
            statement,
            {**parameters, "k": count, "scope_ids": scope_ids},
            timeout=timeout,
        )

    return await _bounded_read(
        read,
        first=min(wanted * 2, _MAX_CANDIDATES),
        ceiling=_MAX_CANDIDATES,
        wanted=wanted,
    )


async def _bounded_read(
    read: Callable[[int], Awaitable[_RowSequence]],
    *,
    first: int,
    ceiling: int,
    wanted: int,
) -> tuple[list[_Visible], bool]:
    """Read graph candidates at most twice until ``wanted`` rows are visible.

    Args:
        read: Runs one candidate read at the given count.
        first: The count of the first read.
        ceiling: The largest count any read may use.
        wanted: The number of visible rows the leg needs.

    Returns:
        The visible rows, best first, and whether the ceiling was reached with
        fewer than ``wanted`` visible rows.
    """
    rows = await read(first)
    visible = _visible_rows(rows)
    if len(visible) >= wanted:
        return visible[:wanted], False
    if _candidate_count(rows) < first:
        return visible, False
    if first >= ceiling:
        return visible, True
    rows = await read(ceiling)
    visible = _visible_rows(rows)
    if len(visible) >= wanted:
        return visible[:wanted], False
    # Truncated only when the ceiling was reached: a smaller candidate set
    # means the index ran out, not that the bound cut the search.
    return visible[:wanted], _candidate_count(rows) >= ceiling


async def _run_external_semantic_leg(
    store: GraphStore,
    vector_store: VectorStore,
    vector: Sequence[float],
    query: str,
    *,
    mode: EvidenceSearchMode,
    scope_ids: list[str],
    wanted: int,
    alpha: float,
    timeout: float | None,
) -> tuple[list[_Visible], bool]:
    """Fetch external vector candidates at most twice, then join them to the graph."""
    ceiling = min(_MAX_CANDIDATES, vector_store.max_results)
    statement = semantic_candidates_from_rows_query()

    async def read(count: int) -> tuple[Sequence[VectorHit], _RowSequence]:
        if mode is EvidenceSearchMode.HYBRID:
            store_hits = await run_with_timeout(
                lambda: vector_store.hybrid_search(
                    VectorKind.CHUNK, vector, query, limit=count, alpha=alpha
                ),
                timeout,
            )
        else:
            store_hits = await run_with_timeout(
                lambda: vector_store.search(VectorKind.CHUNK, vector, limit=count),
                timeout,
            )
        rows = (
            await store.execute_read(
                statement,
                {
                    "rows": [
                        {"id": str(hit.id), "score": hit.score} for hit in store_hits
                    ],
                    "scope_ids": scope_ids,
                },
                timeout=timeout,
            )
            if store_hits
            else []
        )
        return store_hits, rows

    first = min(wanted * 2, ceiling)
    store_hits, rows = await read(first)
    visible = _visible_rows(rows)
    if len(visible) >= wanted:
        return visible[:wanted], False
    if len(store_hits) < first:
        return visible, False
    if first >= ceiling:
        return visible, True
    store_hits, rows = await read(ceiling)
    visible = _visible_rows(rows)
    if len(visible) >= wanted:
        return visible[:wanted], False
    # Truncated only when the store returned a full ceiling of hits; a
    # smaller set means the collection ran out of candidates.
    return visible[:wanted], len(store_hits) >= ceiling


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
    wanted: int,
) -> list[_Fused]:
    """Merge the legs into fused hits, one per evidence id, best first."""
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
        _Fused(
            item=by_id[evidence_id],
            score=scores[evidence_id],
            legs=legs_by_id[evidence_id],
        )
        for evidence_id in ordered[:wanted]
    ]


def _hit(entry: _Fused) -> EvidenceSearchHit:
    """Build the public hit for one fused chunk."""
    chunk = entry.item.chunk
    return EvidenceSearchHit(
        evidence_id=entry.item.evidence_id,
        document_key=entry.item.document_key,
        title=entry.item.title,
        content_hash=chunk.content_hash,
        location=chunk_location(chunk),
        snippet=chunk.text[:_SNIPPET_CHARS],
        score=entry.score,
        legs=entry.legs,
    )
