"""Pure record construction for the Document/PART_OF lexical backbone.

This module is internal. ``Graph.add`` and ``Graph.update`` call these
functions to turn already-built ``Document``/``Chunk`` objects into
``NodeRecord``/``RelationRecord`` writes. Nothing here touches ``GraphStore``.
"""

from datetime import datetime
from uuid import UUID

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.ingestion.merge import part_of_id


def distinct_documents(documents: list[Document]) -> list[Document]:
    """Return each document once, keeping first-occurrence order.

    Args:
        documents: The documents seen while chunking one ``add()`` call,
            possibly repeating the same document across batches.

    Returns:
        One entry per distinct ``Document.resolved_id``.
    """
    seen: set[UUID] = set()
    result: list[Document] = []
    for document in documents:
        if document.resolved_id in seen:
            continue
        seen.add(document.resolved_id)
        result.append(document)
    return result


def build_document_record(document: Document) -> NodeRecord:
    """Return document as a GraphStore write record for its Document node."""
    return document.to_node_record()


def build_part_of_records(
    document_node_id: UUID, chunks: list[Chunk]
) -> list[RelationRecord]:
    """Return one open Document -[:PART_OF]-> Chunk record per chunk.

    Args:
        document_node_id: The id of the persisted Document node these chunks
            belong to.
        chunks: The chunks to link. Every chunk must have a resolved id.

    Returns:
        One RelationRecord per chunk, with ``valid_at`` set and
        ``invalid_at`` unset.

    Raises:
        ValueError: A chunk's id is None.
    """
    now = datetime.now().isoformat()
    records: list[RelationRecord] = []
    for chunk in chunks:
        if chunk.id is None:
            raise ValueError("Chunk.id must be set before building a PART_OF record.")
        records.append(
            RelationRecord(
                id=part_of_id(document_node_id, chunk.id),
                type="PART_OF",
                start_id=document_node_id,
                end_id=chunk.id,
                properties={"valid_at": now, "invalid_at": None},
            )
        )
    return records
