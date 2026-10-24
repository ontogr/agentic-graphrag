"""Find themes: entity communities with the passages that mention their members.

A theme comes from the last community detection run, so its membership can be
stale. Membership that has since become invisible is filtered by the query, so
no hidden or out-of-scope passage can appear; documents added after the last
run are absent until the next run. Only passages and member names are returned,
never community report text, because a community node carries no document
scope.
"""

import logging
from collections.abc import Iterable, Mapping
from typing import Any

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.community import COMMUNITY_LABEL
from agrag.common.data_models.entity_search import SupportingPassage
from agrag.common.data_models.evidence import (
    EvidenceSearchLeg,
    EvidenceSearchStatus,
    IndexState,
    LegFailure,
)
from agrag.common.data_models.index_record import INDEX_STATE_ONLINE
from agrag.common.data_models.theme_search import ThemeHit, ThemeResult
from agrag.common.data_models.vector_record import VectorKind
from agrag.cypher.community_read import community_candidates_query, theme_passages_query
from agrag.cypher.schema import vector_index_name
from agrag.embedding.base import Embedder
from agrag.evidence._shared import (
    EMBEDDING_MISMATCH_MESSAGE,
    chunk_location,
    chunk_reference,
    embedding_matches,
    run_with_timeout,
    scope_node_ids,
    stored_chunk,
    stores_ready,
)
from agrag.evidence.contract import DEFAULT_SUPPORT_LIMIT, DEFAULT_THEME_LIMIT
from agrag.evidence.ids import encode_evidence_id
from agrag.graphdb.base import GraphStore
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


_LOGGER = logging.getLogger(__name__)
_FAILED_MESSAGE = "theme search failed"
_EMBEDDING_PROPERTY = "embedding"
_MAX_ENTITIES = 5


async def search_themes(
    store: GraphStore,
    embedder: Embedder,
    query: str,
    *,
    scope: frozenset[str],
    limit: int = DEFAULT_THEME_LIMIT,
    support_limit: int = DEFAULT_SUPPORT_LIMIT,
    vector_store: VectorStore | None = None,
    settings: RetrievalSettings | None = None,
    timeout: float | None = None,
) -> ThemeResult:
    """Find up to ``limit`` themes whose member passages match a query.

    The query is embedded and searched against the community report embeddings
    of the last detection run, so a theme matches by meaning only. Each theme is
    returned with the visible in-scope passages that mention its member
    entities, and a community with no such passage is dropped. Communities come
    from the last ``detect_communities`` run: membership that has since become
    hidden or out of scope is filtered out, so no such passage can appear, and
    documents ingested after that run are absent until the next run.

    Args:
        store: The graph store to search.
        embedder: Embeds the query for the community vector search.
        query: The query text.
        scope: Keys of the documents whose passages may be used.
        limit: The most themes to return. Must be positive.
        support_limit: The most passages listed for each theme. Must be
            positive.
        vector_store: Optional external vector store holding the community
            embeddings. Placement is not validated by this function.
        settings: Retrieval configuration. None uses the defaults. Theme search
            reads no rerank or fusion setting; the parameter keeps the call
            shape of the other retrieval tools.
        timeout: Server-side transaction timeout in seconds for each store
            read. None uses the server's default.

    Returns:
        The themes, best first, with the status, truncation flag, index state
        and any failed leg.

    Raises:
        ValueError: ``limit`` or ``support_limit`` is not positive.
    """
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}")
    if support_limit <= 0:
        raise ValueError(f"support_limit must be positive, got {support_limit}")
    if not scope:
        return ThemeResult(status=EvidenceSearchStatus.EMPTY_SCOPE)

    try:
        indexes = await store.list_indexes(timeout=timeout)
    except Exception:
        _LOGGER.exception("Theme index state read failed")
        return ThemeResult(status=EvidenceSearchStatus.FAILED)

    failure = await _semantic_failure(
        embedder,
        indexes=indexes,
        vector_store=vector_store,
        timeout=timeout,
    )
    if failure is not None:
        return ThemeResult(status=EvidenceSearchStatus.FAILED, failures=[failure])

    index_name = vector_index_name(COMMUNITY_LABEL, _EMBEDDING_PROPERTY)
    index_state = IndexState.NOT_READY
    if vector_store is None:
        if any(
            index.name == index_name and index.state == INDEX_STATE_ONLINE
            for index in indexes
        ):
            index_state = IndexState.READY
    else:
        index_state = await stores_ready(
            vector_store, [VectorKind.COMMUNITY], timeout=timeout
        )
    if index_state is IndexState.NOT_READY:
        return ThemeResult(
            status=EvidenceSearchStatus.INDEX_NOT_READY, index_state=index_state
        )

    candidate_count = min(limit * 3, 100)
    try:
        [vector] = await embedder.embed([query])
        candidates, filled = await _community_candidates(
            store,
            vector,
            count=candidate_count,
            vector_store=vector_store,
            timeout=timeout,
        )
        rows = await store.execute_read(
            theme_passages_query(),
            {
                "community_ids": [candidate.theme_id for candidate in candidates],
                "scope_ids": sorted(scope_node_ids(scope)),
                "support_limit": support_limit,
            },
            timeout=timeout,
        )
    except Exception:
        _LOGGER.exception("Theme search read failed")
        return ThemeResult(
            status=EvidenceSearchStatus.FAILED,
            index_state=index_state,
            failures=[
                LegFailure(leg=EvidenceSearchLeg.SEMANTIC, message=_FAILED_MESSAGE)
            ],
        )

    themes = _combine(candidates, rows, limit=limit)
    truncated = filled and len(themes) < limit
    return ThemeResult(
        status=EvidenceSearchStatus.OK if themes else EvidenceSearchStatus.NO_MATCH,
        themes=themes,
        truncated=truncated,
        index_state=index_state,
    )


async def _semantic_failure(
    embedder: Embedder,
    *,
    indexes: list[Any],
    vector_store: VectorStore | None,
    timeout: float | None,
) -> LegFailure | None:
    """Return the failure recorded by the dimension guard, or None."""
    try:
        matched = await embedding_matches(
            embedder,
            indexes=indexes,
            index_name=vector_index_name(COMMUNITY_LABEL, _EMBEDDING_PROPERTY),
            vector_store=vector_store,
            kind=VectorKind.COMMUNITY,
            timeout=timeout,
        )
    except Exception:
        _LOGGER.exception("The query embedder could not report its dimensions")
        return LegFailure(leg=EvidenceSearchLeg.SEMANTIC, message=_FAILED_MESSAGE)
    if not matched:
        return LegFailure(
            leg=EvidenceSearchLeg.SEMANTIC, message=EMBEDDING_MISMATCH_MESSAGE
        )
    return None


async def _community_candidates(
    store: GraphStore,
    vector: list[float],
    *,
    count: int,
    vector_store: VectorStore | None,
    timeout: float | None,
) -> tuple[list[ThemeHit], bool]:
    """Return the community candidates, best first, and whether the read filled up.

    Graph-native search reads the Community vector index. External search reads
    the external collection and returns the hit ids as they are; the passage
    query re-checks that each community is committed.
    """
    if vector_store is not None:
        hits = await run_with_timeout(
            lambda: vector_store.search(VectorKind.COMMUNITY, vector, limit=count),
            timeout,
        )
        seen: set[str] = set()
        candidates: list[ThemeHit] = []
        for hit in hits:
            theme_id = str(hit.id)
            if theme_id in seen:
                continue
            seen.add(theme_id)
            candidates.append(ThemeHit(theme_id=theme_id, score=hit.score))
        return candidates, len(hits) >= count
    call = await store.vector_search_call(
        label=COMMUNITY_LABEL, vector_property=_EMBEDDING_PROPERTY
    )
    rows = await store.execute_read(
        community_candidates_query(call.text),
        {**call.params, "vector": vector, "k": count},
        timeout=timeout,
    )
    candidates = [
        ThemeHit(theme_id=str(row["community_id"]), score=float(row["score"]))
        for row in rows
    ]
    return candidates, len(rows) >= count


def _combine(
    candidates: Iterable[ThemeHit],
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[ThemeHit]:
    """Attach the visible passages to the candidates that have any, best first.

    Rows of one community are kept in the query order, which ranks the chunks
    by member count and then by chunk position. Community ids absent from the
    rows have no visible passage and are dropped. The candidate score survives,
    because the score orders themes and the passages do not rank them.
    """
    passages_by_theme: dict[str, list[SupportingPassage]] = {}
    names_by_theme: dict[str, list[str]] = {}
    for row in rows:
        theme_id = str(row["community_id"])
        stored = stored_chunk(row)
        entry = passages_by_theme.setdefault(theme_id, [])
        entry.append(_passage(stored.chunk, stored.document_key))
        names = names_by_theme.setdefault(theme_id, [])
        for name in row.get("member_names") or []:
            if name is not None and name not in names:
                names.append(name)

    hits: list[ThemeHit] = []
    for candidate in candidates:
        if candidate.theme_id not in passages_by_theme:
            continue
        hits.append(
            ThemeHit(
                theme_id=candidate.theme_id,
                score=candidate.score,
                entities=names_by_theme[candidate.theme_id][:_MAX_ENTITIES],
                passages=passages_by_theme[candidate.theme_id],
            )
        )
        if len(hits) == limit:
            break
    return hits


def _passage(chunk: Chunk, document_key: str) -> SupportingPassage:
    """Build the public passage entry for a visible chunk."""
    return SupportingPassage(
        evidence_id=encode_evidence_id(chunk_reference(chunk)),
        document_key=document_key,
        location=chunk_location(chunk),
    )
