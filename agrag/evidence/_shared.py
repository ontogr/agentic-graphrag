"""Helpers shared by search, fetch, navigation and citation checks."""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.evidence import (
    CONTENT_HASH_PREFIX_LENGTH,
    EvidenceKind,
    EvidenceLocation,
    EvidenceReference,
    IndexState,
)
from agrag.common.data_models.provenance import PageProvenance, TextProvenance
from agrag.cypher.evidence import index_states_query
from agrag.graphdb.base import GraphStore


_ONLINE = "ONLINE"


def scope_node_ids(scope: Iterable[str]) -> frozenset[str]:
    """Return the Document node id string of each document key in scope.

    Args:
        scope: Document keys.

    Returns:
        The node ids as lowercase UUID strings, matching ``Chunk.document_id``.
    """
    return frozenset(str(Document.node_id_for(document_key=key)) for key in scope)


def chunk_from_row(properties: Mapping[str, Any]) -> Chunk:
    """Build a Chunk from the properties of a stored Chunk node.

    Null properties are dropped, because the writer omits empty optional fields.

    Args:
        properties: The node properties, including the ``id`` property.

    Returns:
        The validated chunk.
    """
    data = {key: value for key, value in properties.items() if value is not None}
    return Chunk.from_node(data)


def text_offsets(chunk: Chunk) -> tuple[int, int] | None:
    """Return the stored text offsets of a chunk, or None without text offsets.

    The offsets are the provenance as written. They do not show that the chunk
    text equals the document text at those offsets. Use ``text_range`` for that.

    Args:
        chunk: The chunk.

    Returns:
        ``(char_start, char_end)`` for text provenance, else None.
    """
    if isinstance(chunk.provenance, TextProvenance):
        return chunk.provenance.char_start, chunk.provenance.char_end
    return None


def text_range(chunk: Chunk) -> tuple[int, int] | None:
    """Return the offsets of a chunk whose text is exactly the range it names.

    A chunk under a heading holds the heading line in its text, but its offsets
    cover only the body. Such a chunk has no span: its text cannot be sliced from
    the document by those offsets. The lengths must match, because the document
    text is not stored and the length is the only check that needs no document.

    Args:
        chunk: The chunk.

    Returns:
        ``(char_start, char_end)`` when the chunk text length equals the range
        length, else None.
    """
    bounds = text_offsets(chunk)
    if bounds is None or bounds[1] - bounds[0] != len(chunk.text):
        return None
    return bounds


def chunk_reference(chunk: Chunk) -> EvidenceReference:
    """Return the reference a search hit uses for a chunk.

    A chunk whose text is exactly its text range gives a span over that range. Any
    other chunk, including a chunk under a heading, gives a chunk reference. Both
    forms name the same passage whichever search leg found it, so the hit has one
    evidence id.

    Args:
        chunk: The chunk.

    Returns:
        A span reference for a non-empty text range, else a chunk reference.
    """
    prefix = chunk.content_hash[:CONTENT_HASH_PREFIX_LENGTH]
    bounds = text_range(chunk)
    if bounds is not None and bounds[0] < bounds[1]:
        return EvidenceReference(
            kind=EvidenceKind.SPAN,
            document_node_id=chunk.document_id,
            content_hash_prefix=prefix,
            char_start=bounds[0],
            char_end=bounds[1],
        )
    return EvidenceReference(
        kind=EvidenceKind.CHUNK,
        document_node_id=chunk.document_id,
        content_hash_prefix=prefix,
        chunk_id=chunk.id,
    )


@dataclass(frozen=True)
class StoredChunk:
    """One chunk row of a document version, as the evidence queries return it.

    Attributes:
        chunk: The chunk.
        version_id: The id of the version the chunk belongs to, from its open or
            closed ``HAS_PART`` edge.
        closed_at: The time the ``HAS_PART`` edge closed, or None while it is open.
        document_key: The key of the document.
        title: Stored document title, when projected by the query.
        uri: Stored source URI, when projected by the query.
        current_content_hash: The full content hash of the current version, or None
            after the source has been deleted.
    """

    chunk: Chunk
    version_id: str | None
    closed_at: str | None
    document_key: str
    current_content_hash: str | None
    activation_seq: int | None = None
    title: str | None = None
    uri: str | None = None


def stored_chunk(row: Mapping[str, Any]) -> StoredChunk:
    """Build a stored chunk from one row of an evidence query.

    Args:
        row: A row with the ``chunk``, ``version_id``, ``closed_at``,
            ``document_key`` and ``current_content_hash`` columns.

    Returns:
        The stored chunk.
    """
    return StoredChunk(
        chunk=chunk_from_row(row["chunk"]),
        version_id=row["version_id"],
        closed_at=row["closed_at"],
        document_key=row["document_key"],
        current_content_hash=row["current_content_hash"],
        activation_seq=row.get("activation_seq"),
        title=row.get("title"),
        uri=row.get("uri"),
    )


def chunk_location(chunk: Chunk) -> EvidenceLocation:
    """Return where a chunk sits in its source.

    Args:
        chunk: The chunk.

    Returns:
        The stored offsets of a text chunk, the pages of a page chunk, or an empty
        location for any other chunk.
    """
    bounds = text_offsets(chunk)
    if bounds is not None:
        return EvidenceLocation(char_start=bounds[0], char_end=bounds[1])
    if isinstance(chunk.provenance, PageProvenance):
        return EvidenceLocation(
            page_numbers=[span.page_no for span in chunk.provenance.page_spans]
        )
    return EvidenceLocation()


def choose_chunk_set(rows: Sequence[StoredChunk]) -> list[StoredChunk] | None:
    """Return the rows of one chunk set, preferring a set with an open edge.

    A chunk set is the chunks written by one ``(version_id, chunker_hash)`` pair.
    A set with an open edge wins. Otherwise the set closed most recently wins.

    Args:
        rows: Rows of chunks of one content hash. The caller filters the rows it
            needs.

    Returns:
        The rows of the chosen set, or None when ``rows`` is empty.
    """
    sets: dict[tuple[str | None, str | None], list[StoredChunk]] = defaultdict(list)
    for row in rows:
        sets[(row.version_id, row.chunk.chunker_hash)].append(row)
    if not sets:
        return None

    def recency(members: list[StoredChunk]) -> tuple[bool, str]:
        is_open = any(row.closed_at is None for row in members)
        latest_close = max((row.closed_at or "" for row in members), default="")
        return is_open, latest_close

    return max(sets.values(), key=recency)


def lucene_terms(query: str) -> str:
    """Return the query as plain terms that Lucene cannot read as operators.

    Only word characters survive, so no operator, field name, quote or escape
    reaches the parser. Words are lowercased, so ``AND`` and ``NOT`` are not
    operators in any case.

    Args:
        query: The query text as the caller wrote it.

    Returns:
        The words of the query joined by spaces. Empty when no word is present.
    """
    return " ".join(re.findall(r"\w+", query.lower()))


@dataclass(frozen=True)
class IndexSpec:
    """The name, type, label and property a search leg's index must have.

    Attributes:
        name: The index name, from ``fulltext_index_name`` or ``vector_index_name``.
        index_type: ``FULLTEXT`` or ``VECTOR``, as Neo4j reports it.
        label: The node label the index covers.
        prop: The indexed property.
    """

    name: str
    index_type: str
    label: str
    prop: str


async def indexes_ready(
    store: GraphStore, specs: Sequence[IndexSpec], *, timeout: float | None = None
) -> IndexState:
    """Return READY when every spec names an ONLINE index of the right shape.

    The name alone is not enough: an index under the same name but built for
    another label or property would return wrong passages, so type, label and
    property are checked too.

    Args:
        store: The graph store to ask.
        specs: The indexes that a call needs.
        timeout: Server-side transaction timeout in seconds. None uses the
            server's default.

    Returns:
        ``IndexState.READY`` or ``IndexState.NOT_READY``.
    """
    rows = await store.execute_read(
        index_states_query(),
        {"names": [spec.name for spec in specs]},
        timeout=timeout,
    )
    found = {row["name"]: row for row in rows}
    for spec in specs:
        row = found.get(spec.name)
        if row is None or row["state"] != _ONLINE:
            return IndexState.NOT_READY
        if row["type"] != spec.index_type:
            return IndexState.NOT_READY
        if list(row["labelsOrTypes"] or []) != [spec.label]:
            return IndexState.NOT_READY
        if list(row["properties"] or []) != [spec.prop]:
            return IndexState.NOT_READY
    return IndexState.READY
