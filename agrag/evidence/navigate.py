"""Navigate from one evidence passage to its neighbors, within scope and bounds.

A navigation call starts from an evidence id and follows one relation to other
passages of the same document version. Structure edges and reading order decide
the neighbors. Every returned passage belongs to a document in the caller's
scope, and it is read in the version the starting id names, so a superseded id
keeps its own neighbors.
"""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from agrag.common.data_models.evidence import (
    CONTENT_HASH_PREFIX_LENGTH,
    EvidenceKind,
    EvidenceReference,
    VersionStatus,
)
from agrag.common.data_models.navigation import (
    NavigationItem,
    NavigationRelation,
    NavigationResult,
    NavigationStatus,
    TruncationReason,
)
from agrag.cypher.evidence import (
    evidence_chunk_at_offset_query,
    evidence_chunks_query,
    navigation_chunks_query,
    navigation_sections_query,
    table_neighbor_query,
)
from agrag.evidence._shared import (
    StoredChunk,
    choose_chunk_set,
    chunk_location,
    chunk_reference,
    scope_node_ids,
    stored_chunk,
    text_range,
)
from agrag.evidence.ids import (
    MalformedEvidenceIdError,
    decode_evidence_id,
    encode_evidence_id,
)
from agrag.graphdb.base import GraphStore


_LOGGER = logging.getLogger(__name__)
_STORE_ERROR_MESSAGE = "navigation store error"
MAX_LIMIT = 50
MAX_CHARS = 20_000


@dataclass(frozen=True)
class _Passage:
    """A neighbor passage and the headings above it."""

    stored: StoredChunk
    heading_path: list[str]


async def navigate_document_tree(
    store: GraphStore,
    evidence_id: str,
    relation: NavigationRelation,
    *,
    scope: frozenset[str],
    limit: int,
    max_chars: int,
) -> NavigationResult:
    """Return the passages that one relation reaches from an evidence id.

    A span id starts from the chunk of its version that covers the first
    character of the span. A chunk id starts from that chunk. Neighbors are read
    in the version of the starting chunk, whether or not that version is current.
    An id that names no evidence in scope, and a missing id, both give
    ``unavailable``.

    ``parent`` returns one item for each section that holds the starting passage,
    and ``multi_section`` is True when there is more than one. ``siblings``
    returns the other sections under the same parent section. ``table_context``
    returns the row passages before and after a table passage, with the passage
    itself. Every table passage repeats the header rows, so no row is returned
    without its header.

    The text of the items is cut to ``max_chars`` in total, in the order of the
    items. An item cut by the budget is marked ``text_truncated``. An item beyond
    ``limit`` is dropped. Either bound sets ``truncated`` and the reason.

    Args:
        store: The graph store to read.
        evidence_id: The evidence id of the starting passage.
        relation: The relation to follow.
        scope: Keys of the documents the caller may read. An empty scope makes
            every id unavailable.
        limit: The most items to return. Must be between 1 and 50.
        max_chars: The most characters of item text to return. Must be between 1
            and 20000.

    Returns:
        The items, the status and the truncation information.

    Raises:
        ValueError: ``limit`` or ``max_chars`` is outside its range.
    """
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}, got {limit}")
    if not 1 <= max_chars <= MAX_CHARS:
        raise ValueError(
            f"max_chars must be between 1 and {MAX_CHARS}, got {max_chars}"
        )
    try:
        reference = decode_evidence_id(evidence_id)
    except MalformedEvidenceIdError as exc:
        return NavigationResult(status=NavigationStatus.MALFORMED, detail=str(exc))
    if str(reference.document_node_id) not in scope_node_ids(scope):
        return _unavailable()

    is_chunk = reference.kind is EvidenceKind.CHUNK
    rows = await _read_rows(
        store,
        evidence_chunks_query(by_chunk_id=True)
        if is_chunk
        else evidence_chunk_at_offset_query(),
        _anchor_parameters(reference),
        reference.document_node_id,
    )
    if rows is None:
        return NavigationResult(
            status=NavigationStatus.FAILED, detail=_STORE_ERROR_MESSAGE
        )
    anchor = (
        _anchor(reference, [stored_chunk(row) for row in rows])
        if is_chunk
        else stored_chunk(rows[0])
        if rows
        else None
    )
    if anchor is None:
        return _unavailable()

    passages = await _passages(store, relation, anchor, limit)
    if passages is None:
        return NavigationResult(
            status=NavigationStatus.FAILED, detail=_STORE_ERROR_MESSAGE
        )
    overflow = len(passages) > limit
    items = [
        _item(passage.stored, passage.heading_path) for passage in passages[:limit]
    ]
    selected, cut = _within_budget(items, max_chars)
    truncation_reason = None
    if cut:
        truncation_reason = TruncationReason.CHARS
    elif overflow:
        truncation_reason = TruncationReason.LIMIT
    return NavigationResult(
        status=NavigationStatus.OK if selected else NavigationStatus.NO_MATCH,
        items=selected,
        truncated=truncation_reason is not None,
        truncation_reason=truncation_reason,
        version_status=_version_status(anchor),
        multi_section=len(anchor.chunk.section_ids) > 1,
    )


def _unavailable() -> NavigationResult:
    """Return the result shared by missing ids and ids outside the scope."""
    return NavigationResult(status=NavigationStatus.UNAVAILABLE)


def _anchor_parameters(reference: EvidenceReference) -> dict[str, Any]:
    """Return the parameters of the query that loads the starting chunk rows."""
    parameters: dict[str, Any] = {
        "document_id": str(reference.document_node_id),
        "content_hash_prefix": reference.content_hash_prefix,
    }
    if reference.chunk_id is not None:
        parameters["chunk_id"] = str(reference.chunk_id)
    if reference.char_start is not None:
        parameters["char_start"] = reference.char_start
    return parameters


async def _read_rows(
    store: GraphStore,
    statement: str,
    parameters: dict[str, Any],
    document_node_id: UUID,
) -> list[dict[str, Any]] | None:
    """Run one read, or return None and log the failure."""
    try:
        return await store.execute_read(statement, parameters)
    except Exception:
        _LOGGER.exception(
            "Navigation read failed for an id of document %s", document_node_id
        )
        return None


def _anchor(
    reference: EvidenceReference, rows: list[StoredChunk]
) -> StoredChunk | None:
    """Return the chunk that a reference starts from, or None when none is found.

    A chunk reference starts from its own chunk. A span starts from the text chunk
    of one chunk set that covers the first character of the span. A set with an
    open edge is preferred, as in fetch.
    """
    if reference.kind is EvidenceKind.CHUNK:
        chunk_set = choose_chunk_set(rows)
        return chunk_set[0] if chunk_set else None
    start = reference.char_start
    if start is None:
        raise ValueError("a span reference needs char_start")
    chunk_set = choose_chunk_set(
        [row for row in rows if text_range(row.chunk) is not None]
    )
    if chunk_set is None:
        return None
    for row in chunk_set:
        bounds = text_range(row.chunk)
        if bounds is not None and bounds[0] <= start < bounds[1]:
            return row
    return None


def _version_status(anchor: StoredChunk) -> VersionStatus:
    """Return whether the version of the starting chunk is the current one."""
    if (
        anchor.current_content_hash is not None
        and anchor.current_content_hash[:CONTENT_HASH_PREFIX_LENGTH]
        == anchor.chunk.content_hash[:CONTENT_HASH_PREFIX_LENGTH]
    ):
        return VersionStatus.CURRENT
    return VersionStatus.SUPERSEDED


async def _passages(
    store: GraphStore,
    relation: NavigationRelation,
    anchor: StoredChunk,
    limit: int,
) -> list[_Passage] | None:
    """Return the neighbor passages of a relation, one more than limit at most.

    A query that fails gives None.
    """
    if relation is NavigationRelation.TABLE_CONTEXT:
        return await _table_context(store, anchor, limit)
    if relation in (NavigationRelation.PARENT, NavigationRelation.SIBLINGS):
        return await _sections(store, relation, anchor, limit)
    rows = await _read_rows(
        store,
        navigation_chunks_query(relation),
        _neighbor_parameters(anchor, limit),
        anchor.chunk.document_id,
    )
    if rows is None:
        return None
    passages: list[_Passage] = []
    for row in rows:
        stored = stored_chunk(row)
        passages.append(_Passage(stored, list(stored.chunk.heading_path)))
    return passages


async def _table_context(
    store: GraphStore, anchor: StoredChunk, limit: int
) -> list[_Passage] | None:
    """Return the row passages before and after a table passage, with itself.

    A passage that is not a table has no table context, and the result is empty.
    """
    if anchor.chunk.content_kind != "table":
        return []
    parameters = _neighbor_parameters(anchor, limit)
    parameters["position"] = anchor.chunk.index
    before_rows = await _read_rows(
        store,
        table_neighbor_query(previous=True),
        parameters,
        anchor.chunk.document_id,
    )
    after_rows = await _read_rows(
        store,
        table_neighbor_query(previous=False),
        parameters,
        anchor.chunk.document_id,
    )
    if before_rows is None or after_rows is None:
        return None
    window = [
        *[stored_chunk(row) for row in before_rows],
        anchor,
        *[stored_chunk(row) for row in after_rows],
    ]
    return [_Passage(row, list(row.chunk.heading_path)) for row in window]


async def _sections(
    store: GraphStore,
    relation: NavigationRelation,
    anchor: StoredChunk,
    limit: int,
) -> list[_Passage] | None:
    """Return the sections of a parent or sibling relation with their first passage."""
    parameters = {
        "section_ids": [str(section_id) for section_id in anchor.chunk.section_ids],
        "document_id": str(anchor.chunk.document_id),
        "version_id": anchor.version_id,
        "fetch": limit + 1,
    }
    rows = await _read_rows(
        store,
        navigation_sections_query(relation),
        parameters,
        anchor.chunk.document_id,
    )
    if rows is None:
        return None
    passages: list[_Passage] = []
    for row in rows:
        headings = [
            heading for heading in [*row["ancestors"], row["heading"]] if heading
        ]
        passages.append(_Passage(stored_chunk(row), headings))
    return passages


def _neighbor_parameters(anchor: StoredChunk, limit: int) -> dict[str, Any]:
    """Return the parameters of the chunk neighbor queries."""
    return {
        "chunk_id": str(anchor.chunk.id),
        "document_id": str(anchor.chunk.document_id),
        "version_id": anchor.version_id,
        "fetch": limit + 1,
    }


def _item(stored: StoredChunk, heading_path: list[str]) -> NavigationItem:
    """Build the public item for one passage."""
    chunk = stored.chunk
    return NavigationItem(
        evidence_id=encode_evidence_id(chunk_reference(chunk)),
        document_key=stored.document_key,
        heading_path=heading_path,
        kind=chunk.content_kind,
        text=chunk.text,
        location=chunk_location(chunk),
    )


def _within_budget(
    items: list[NavigationItem], max_chars: int
) -> tuple[list[NavigationItem], bool]:
    """Return the items that fit in the character budget, and whether text was cut.

    The first item that does not fit is cut to the remaining budget, and the items
    after it are dropped.
    """
    selected: list[NavigationItem] = []
    remaining = max_chars
    for item in items:
        if len(item.text) <= remaining:
            selected.append(item)
            remaining -= len(item.text)
            continue
        if remaining > 0:
            selected.append(
                item.model_copy(
                    update={"text": item.text[:remaining], "text_truncated": True}
                )
            )
        return selected, True
    return selected, False
