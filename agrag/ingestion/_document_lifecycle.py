"""Shared graph helpers for document version lifecycle operations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from agrag.cypher.relations import close_part_of_query
from agrag.graphdb.base import GraphStore


if TYPE_CHECKING:
    from agrag.graphdb.base import GraphStoreTransaction


class DocumentLookup(BaseModel):
    """Persisted identity and current content hash for one document."""

    document_node_id: UUID
    current_content_hash: str


async def find_document(
    graph_store: GraphStore, *, document_key: str
) -> DocumentLookup | None:
    """Look up a persisted Document node by its stable key.

    Args:
        graph_store: Where the Document node is read.
        document_key: The stable key to look up.

    Returns:
        The node's id and current content hash, or ``None`` when no node
        is stored under the key or the stored row is unreadable.
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
        return DocumentLookup(
            document_node_id=UUID(str(row["id"])),
            current_content_hash=str(row["current_content_hash"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


async def close_open_part_of_edges(
    graph_store: GraphStore | GraphStoreTransaction,
    *,
    document_node_id: UUID,
    job_id: UUID | None = None,
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

    Returns:
        The number of edges closed.
    """
    rows = await graph_store.execute_write(
        close_part_of_query(),
        {
            "document_node_id": str(document_node_id),
            "job_id": str(job_id) if job_id is not None else None,
        },
    )
    return int(rows[0].get("closed", 0)) if rows else 0
