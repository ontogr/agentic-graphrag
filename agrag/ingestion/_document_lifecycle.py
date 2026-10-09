"""Shared graph helpers for document version lifecycle operations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from agrag.cypher.documents import current_chunker_hash_query, find_document_query
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
        find_document_query(), {"document_key": document_key}
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
        current_chunker_hash_query(), {"document_key": document_key}
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
    keep_node_ids: Sequence[UUID] = (),
) -> int:
    rows = await graph_store.execute_write(
        close_part_of_query(),
        {
            "document_node_id": str(document_node_id),
            "job_id": str(job_id) if job_id is not None else None,
            "keep_node_ids": [str(node_id) for node_id in keep_node_ids],
        },
    )
    return int(rows[0].get("closed", 0)) if rows else 0
