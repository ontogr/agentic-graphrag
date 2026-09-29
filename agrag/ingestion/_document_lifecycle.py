"""Shared graph helpers for document version lifecycle operations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.relations import close_part_of_query
from agrag.graphdb.base import GraphStore


if TYPE_CHECKING:
    from agrag.graphdb.base import GraphStoreTransaction


class DocumentLookup(BaseModel):
    """Persisted identity, current content hash and chunker for one document.

    Attributes:
        document_node_id: The id of the persisted Document node.
        current_content_hash: The content hash of the current version.
        current_chunker_hash: The chunker fingerprint recorded on a current chunk,
            or ``None`` when no current chunk records one.
    """

    document_node_id: UUID
    current_content_hash: str
    current_chunker_hash: str | None = None


async def find_document(
    graph_store: GraphStore, *, document_key: str
) -> DocumentLookup | None:
    """Look up a persisted Document node by its stable key.

    Args:
        graph_store: Where the Document node is read.
        document_key: The stable key to look up.

    Returns:
        The node's id, current content hash and current chunker fingerprint,
        or ``None`` when no node is stored under the key or the stored row is
        unreadable.
    """
    rows = await graph_store.execute_read(
        "MATCH (n:_AgragNode:Document {document_key: $document_key}) "
        "RETURN n.id AS id, n.current_content_hash AS current_content_hash",
        {"document_key": document_key},
    )
    if not rows:
        return None
    row = rows[0]
    try:
        document_node_id = UUID(str(row["id"]))
        current_content_hash = str(row["current_content_hash"])
    except (KeyError, TypeError, ValueError):
        return None
    chunk_rows = await graph_store.execute_read(
        "MATCH (d:_AgragNode:Document {document_key: $document_key})"
        "-[p:PART_OF]->(c:_AgragNode:Chunk) "
        f"WHERE p.invalid_at IS NULL AND {pending_filter_clause('p')} "
        f"AND {pending_filter_clause('c')} "
        "RETURN c.chunker_hash AS chunker_hash LIMIT 1",
        {"document_key": document_key},
    )
    chunker_hash = chunk_rows[0].get("chunker_hash") if chunk_rows else None
    return DocumentLookup(
        document_node_id=document_node_id,
        current_content_hash=current_content_hash,
        current_chunker_hash=str(chunker_hash) if chunker_hash else None,
    )


async def close_open_part_of_edges(
    graph_store: GraphStore | GraphStoreTransaction,
    *,
    document_node_id: UUID,
    job_id: UUID | None = None,
    keep_chunk_ids: Sequence[UUID] = (),
) -> int:
    """Close every currently-open PART_OF edge for a Document node.

    Only edges with ``invalid_at IS NULL`` are touched, so repeating the
    call closes nothing further.

    Args:
        graph_store: Where the edges are closed. A ``GraphStoreTransaction``
            handle runs the close inside that transaction, which is how the
            Cutover Job runner makes closing the superseded version atomic
            with its commit flip.
        document_node_id: The persisted Document node's id.
        job_id: The in-flight Cutover Job's id. The edges that job just
            wrote stay open, so closing the superseded version does not
            close the version replacing it. None closes every open edge
            the committed graph holds.
        keep_chunk_ids: Chunks whose edges stay open. A replacement version
            can produce a chunk with the id of one it replaces, and closing
            that chunk's edge would hide the new chunk.

    Returns:
        The number of edges closed.
    """
    rows = await graph_store.execute_write(
        close_part_of_query(),
        {
            "document_node_id": str(document_node_id),
            "job_id": str(job_id) if job_id is not None else None,
            "keep_chunk_ids": [str(chunk_id) for chunk_id in keep_chunk_ids],
        },
    )
    return int(rows[0].get("closed", 0)) if rows else 0
