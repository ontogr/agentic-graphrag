"""Fetch the exact text behind evidence ids, limited to the caller's scope."""

import logging
from collections.abc import Sequence
from typing import Any

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.evidence import (
    EvidenceKind,
    EvidenceReference,
    FetchOutcome,
    FetchStatus,
    VersionStatus,
)
from agrag.cypher.evidence import evidence_chunks_query
from agrag.evidence._shared import (
    StoredChunk,
    choose_chunk_set,
    scope_node_ids,
    stored_chunk,
    text_range,
)
from agrag.evidence.ids import MalformedEvidenceIdError, decode_evidence_id
from agrag.graphdb.base import GraphStore


_LOGGER = logging.getLogger(__name__)
_STORE_ERROR_MESSAGE = "evidence store error"


async def fetch(
    store: GraphStore,
    evidence_ids: Sequence[str],
    *,
    scope: frozenset[str],
    max_chars: int,
) -> list[FetchOutcome]:
    """Return the text of each evidence id, in the order given.

    A span id returns the text of its range. Fetch reads the chunks of one chunk
    set for the content hash in the id, so the range is never assembled from two
    sets. A range that no chunk covers is cut to the covered part, which is marked
    ``partial``. Text is never padded. An id that names no readable evidence gives
    ``unavailable``. A missing id and an id outside the scope give the same
    outcome. A chunk reference returns the stored text of that chunk.

    The status of a version is ``current`` when the id's content hash matches the
    document's current content hash, and ``superseded`` otherwise. Superseded text
    is still returned.

    Args:
        store: The graph store to read.
        evidence_ids: Evidence ids to fetch.
        scope: Keys of the documents the caller may read. An empty scope makes
            every id unavailable.
        max_chars: The most characters returned for each id. Must be positive.
            Longer text is cut and marked ``truncated``.

    Returns:
        One outcome for each id, in the same order.

    Raises:
        ValueError: ``max_chars`` is not positive.
    """
    if max_chars <= 0:
        raise ValueError(f"max_chars must be positive, got {max_chars}")
    allowed = scope_node_ids(scope)
    return [
        await _fetch_one(store, evidence_id, allowed, max_chars)
        for evidence_id in evidence_ids
    ]


async def _fetch_one(
    store: GraphStore,
    evidence_id: str,
    allowed: frozenset[str],
    max_chars: int,
) -> FetchOutcome:
    """Fetch one evidence id."""
    try:
        reference = decode_evidence_id(evidence_id)
    except MalformedEvidenceIdError as exc:
        return FetchOutcome(
            evidence_id=evidence_id, status=FetchStatus.MALFORMED, detail=str(exc)
        )
    if str(reference.document_node_id) not in allowed:
        return _unavailable(evidence_id)

    by_chunk = reference.kind is EvidenceKind.CHUNK
    parameters: dict[str, Any] = {
        "document_id": str(reference.document_node_id),
        "content_hash_prefix": reference.content_hash_prefix,
    }
    if reference.chunk_id is not None:
        parameters["chunk_id"] = str(reference.chunk_id)
    try:
        rows = await store.execute_read(
            evidence_chunks_query(by_chunk_id=by_chunk), parameters
        )
    except Exception:
        _LOGGER.exception(
            "Evidence fetch failed for an id of document %s", reference.document_node_id
        )
        return FetchOutcome(
            evidence_id=evidence_id,
            status=FetchStatus.FAILED,
            detail=_STORE_ERROR_MESSAGE,
        )
    stored = [stored_chunk(row) for row in rows]
    if not stored:
        return _unavailable(evidence_id)
    if by_chunk:
        return _chunk_outcome(evidence_id, reference, stored[0], max_chars)
    return _span_outcome(evidence_id, reference, stored, max_chars)


def _unavailable(evidence_id: str) -> FetchOutcome:
    """Return the outcome shared by missing ids and ids outside the scope."""
    return FetchOutcome(evidence_id=evidence_id, status=FetchStatus.UNAVAILABLE)


def _version_status(stored: StoredChunk, content_hash: str) -> VersionStatus:
    """Return whether a version's full content hash is the document's current one."""
    if stored.current_content_hash == content_hash:
        return VersionStatus.CURRENT
    return VersionStatus.SUPERSEDED


def _limited(text: str, max_chars: int) -> tuple[str, bool]:
    """Return the text cut to max_chars, and whether it was cut."""
    if len(text) > max_chars:
        return text[:max_chars], True
    return text, False


def _chunk_outcome(
    evidence_id: str,
    reference: EvidenceReference,
    stored: StoredChunk,
    max_chars: int,
) -> FetchOutcome:
    """Return the outcome of a chunk reference."""
    text, cut = _limited(stored.chunk.text, max_chars)
    bounds = text_range(stored.chunk)
    covered = None if bounds is None else (bounds[0], bounds[0] + len(text))
    return FetchOutcome(
        evidence_id=evidence_id,
        status=FetchStatus.TRUNCATED if cut else FetchStatus.OK,
        text=text,
        reference=reference,
        document_key=stored.document_key,
        content_hash=stored.chunk.content_hash,
        status_of_version=_version_status(stored, stored.chunk.content_hash),
        covered_range=covered,
    )


def _span_outcome(
    evidence_id: str,
    reference: EvidenceReference,
    stored: list[StoredChunk],
    max_chars: int,
) -> FetchOutcome:
    """Return the outcome of a span reference, joined from one chunk set."""
    # A 16-character prefix can match two versions. Their chunks cannot be joined
    # safely, so the id is treated as naming nothing readable.
    if len({row.chunk.content_hash for row in stored}) > 1:
        return _unavailable(evidence_id)
    chunk_set = choose_chunk_set(
        [row for row in stored if text_range(row.chunk) is not None]
    )
    if chunk_set is None:
        return _unavailable(evidence_id)
    start = reference.char_start
    end = reference.char_end
    if start is None or end is None:
        raise ValueError("a span reference needs char_start and char_end")

    parts: list[str] = []
    covered_start: int | None = None
    cursor = start
    for row in sorted(chunk_set, key=lambda row: _bounds(row.chunk)[0]):
        if cursor >= end:
            break
        chunk_start, chunk_end = _bounds(row.chunk)
        if chunk_end <= cursor or chunk_start >= end:
            continue
        if covered_start is None:
            # Text before the first covered chunk is skipped, never padded.
            cursor = max(cursor, chunk_start)
            covered_start = cursor
        elif chunk_start > cursor:
            # A gap ends the covered part.
            break
        stop = min(end, chunk_end)
        parts.append(row.chunk.text[cursor - chunk_start : stop - chunk_start])
        cursor = stop

    if covered_start is None:
        return _unavailable(evidence_id)
    text, cut = _limited("".join(parts), max_chars)
    partial = (covered_start, cursor) != (start, end)
    first = chunk_set[0]
    if cut:
        status = FetchStatus.TRUNCATED
    elif partial:
        status = FetchStatus.PARTIAL
    else:
        status = FetchStatus.OK
    return FetchOutcome(
        evidence_id=evidence_id,
        status=status,
        text=text,
        reference=reference,
        document_key=first.document_key,
        content_hash=first.chunk.content_hash,
        status_of_version=_version_status(first, first.chunk.content_hash),
        covered_range=(covered_start, covered_start + len(text)),
        partial=partial,
    )


def _bounds(chunk: Chunk) -> tuple[int, int]:
    """Return the offsets of a chunk whose text is exactly its text range."""
    bounds = text_range(chunk)
    if bounds is None:
        raise ValueError("only chunks with an exact text range have offsets")
    return bounds
