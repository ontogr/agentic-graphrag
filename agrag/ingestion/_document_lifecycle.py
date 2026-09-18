"""Shared graph helpers for document version lifecycle operations."""

from uuid import UUID

from pydantic import BaseModel

from agrag.cypher.relations import close_part_of_query
from agrag.graphdb.base import GraphStore


class DocumentLookup(BaseModel):
    """Persisted identity and current content hash for one document."""

    document_node_id: UUID
    current_content_hash: str


async def find_document(
    graph_store: GraphStore, *, document_key: str
) -> DocumentLookup | None:
    """Find a persisted document by its stable key."""
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
    graph_store: GraphStore, *, document_node_id: UUID
) -> int:
    """Close open PART_OF edges and return the number changed."""
    rows = await graph_store.execute_write(
        close_part_of_query(), {"document_node_id": str(document_node_id)}
    )
    return int(rows[0].get("closed", 0)) if rows else 0
