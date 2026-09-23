"""Pure record construction for the Document/PART_OF lexical backbone.

This module is internal. ``Graph.add`` and ``Graph.update`` call these
functions to turn already-built ``Document``/``Chunk`` objects into
``NodeRecord``/``RelationRecord`` writes. Nothing here touches ``GraphStore``.
"""

from datetime import UTC, datetime
from uuid import UUID

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.ingestion.merge import next_chunk_id, part_of_id


def distinct_documents(documents: list[Document]) -> list[Document]:
    """Return each document once, keeping first-occurrence order.

    Args:
        documents: The documents seen while chunking one ``add()`` call,
            possibly repeating the same document across batches.

    Returns:
        One entry per distinct stable document key.
    """
    seen: set[str] = set()
    result: list[Document] = []
    for document in documents:
        if document.resolved_document_key in seen:
            continue
        seen.add(document.resolved_document_key)
        result.append(document)
    return result


def build_document_record(document: Document) -> NodeRecord:
    """Return document as a GraphStore write record for its Document node."""
    return document.to_node_record()


def build_part_of_records(
    document_node_id: UUID, chunks: list[Chunk], *, version_id: str
) -> list[RelationRecord]:
    """Return one open Document -[:PART_OF]-> Chunk record per chunk.

    Edge identity is keyed on the document version: rebuilding the same
    version returns the same records, so repeat ingestion converges
    instead of writing parallel edges, while a new version gets new
    edges and preserves the closed interval's history.

    Args:
        document_node_id: The id of the persisted Document node these chunks
            belong to.
        chunks: The chunks to link. Every chunk must have a resolved id.
        version_id: The identifier for this document version. Callers pass
            the content-derived version so identical re-ingests converge.

    Returns:
        One RelationRecord per chunk, with ``valid_at`` set and
        ``invalid_at`` unset.

    Raises:
        ValueError: A chunk's id is None.
    """
    now = datetime.now(UTC).isoformat()
    records: list[RelationRecord] = []
    for chunk in chunks:
        if chunk.id is None:
            raise ValueError("Chunk.id must be set before building a PART_OF record.")
        records.append(
            RelationRecord(
                id=part_of_id(document_node_id, chunk.id, version_id),
                type="PART_OF",
                start_id=document_node_id,
                end_id=chunk.id,
                properties={
                    "valid_at": now,
                    "invalid_at": None,
                    "version_id": version_id,
                },
            )
        )
    return records


def build_next_chunk_records(chunks: list[Chunk]) -> list[RelationRecord]:
    """Return edges joining adjacent chunks within each document.

    Records carry no temporal fields: sequencing is version-independent,
    unlike ``PART_OF`` currency.
    """
    by_document: dict[UUID, list[Chunk]] = {}
    for chunk in chunks:
        by_document.setdefault(chunk.document_id, []).append(chunk)

    records: list[RelationRecord] = []
    for document_chunks in by_document.values():
        ordered = sorted(document_chunks, key=lambda chunk: chunk.index)
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if previous.id is None or current.id is None:
                raise ValueError(
                    "Chunk.id must be set before building NEXT_CHUNK records."
                )
            records.append(
                RelationRecord(
                    id=next_chunk_id(previous.id, current.id),
                    type="NEXT_CHUNK",
                    start_id=previous.id,
                    end_id=current.id,
                    properties={},
                )
            )
    return records
