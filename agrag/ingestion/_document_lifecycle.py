"""Shared graph helpers for document version lifecycle operations.

A document is decided against the stamps of its newest open chunk. The
decision is one of three outcomes: nothing to do, re-extract in place with
the same chunks, or write a new version.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from agrag.common.schema_fingerprint import RunRecord
from agrag.cypher.documents import current_run_record_query, find_document_query
from agrag.cypher.relations import close_has_part_query
from agrag.graphdb.base import GraphStore


if TYPE_CHECKING:
    from agrag.graphdb.base import GraphStoreTransaction


class UpdateDecision(StrEnum):
    """What an update does with a document already in the graph.

    Attributes:
        NO_OP: The stored version matches the new input in every stamp.
        IN_PLACE: Only the extraction setup differs or was never recorded
            (a refresh whose extraction failed), so the chunks are kept and
            re-extracted.
        NEW_VERSION: The content, the chunking, the schema or the stamps are
            missing or differ, so a new version is written.
    """

    NO_OP = "no_op"
    IN_PLACE = "in_place"
    NEW_VERSION = "new_version"


class DocumentLookup(BaseModel):
    """Persisted identity and the stamps of the newest open chunk of a document.

    Attributes:
        document_node_id: The id of the persisted Document node.
        current_content_hash: The content hash of the current version.
        has_open_chunks: Whether the current version has a committed chunk
            behind an open ``HAS_PART`` edge.
        current_chunker_hash: The chunker fingerprint recorded on that chunk,
            or ``None`` when it records none.
        current_schema_fingerprint: The schema fingerprint recorded on that
            chunk, or ``None`` when it records none.
        current_extraction_fingerprint: The extraction fingerprint recorded on
            that chunk, or ``None`` when it records none.
    """

    document_node_id: UUID
    current_content_hash: str
    has_open_chunks: bool = False
    current_chunker_hash: str | None = None
    current_schema_fingerprint: str | None = None
    current_extraction_fingerprint: str | None = None

    def decide(
        self, *, content_hash: str, chunker_hash: str, run: RunRecord
    ) -> UpdateDecision:
        """Pick the update outcome for a new input against the stored version.

        A document without an open chunk is always written as a new version.
        So is any change to the content, the chunking or the schema. When those
        match, the chunks are kept and re-extracted in place if the extraction
        stamp differs or is missing. A missing stamp marks a version whose
        extraction failed, so it is retried rather than treated as current.

        Args:
            content_hash: The content hash of the new input.
            chunker_hash: The chunker fingerprint of the new input.
            run: The run record of the new run.

        Returns:
            ``NEW_VERSION``, ``IN_PLACE`` or ``NO_OP``.
        """
        if (
            not self.has_open_chunks
            or self.current_content_hash != content_hash
            or self.current_chunker_hash != chunker_hash
            or self.current_schema_fingerprint != run.schema_fingerprint
        ):
            return UpdateDecision.NEW_VERSION
        if self.current_extraction_fingerprint == run.extraction_fingerprint:
            return UpdateDecision.NO_OP
        return UpdateDecision.IN_PLACE


async def find_document(
    graph_store: GraphStore, *, document_key: str
) -> DocumentLookup | None:
    """Look up a persisted Document node and the stamps of its open chunk.

    Args:
        graph_store: Where the Document node is read.
        document_key: The stable key to look up.

    Returns:
        The node's id, current content hash and the stamps of its newest open
        chunk, or ``None`` when no node is stored under the key or the stored
        row is unreadable. Without an open chunk, ``has_open_chunks`` is
        ``False`` and every stamp is ``None``.
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
    run_rows = await graph_store.execute_read(
        current_run_record_query(), {"document_key": document_key}
    )
    if not run_rows:
        return DocumentLookup(
            document_node_id=document_node_id,
            current_content_hash=current_content_hash,
        )
    run_row = run_rows[0]
    return DocumentLookup(
        document_node_id=document_node_id,
        current_content_hash=current_content_hash,
        has_open_chunks=True,
        current_chunker_hash=_optional_str(run_row.get("chunker_hash")),
        current_schema_fingerprint=_optional_str(run_row.get("schema_fingerprint")),
        current_extraction_fingerprint=_optional_str(
            run_row.get("extraction_fingerprint")
        ),
    )


def _optional_str(value: object) -> str | None:
    """Return a stored stamp as a string, keeping a missing one as ``None``."""
    if value is None:
        return None
    return str(value)


async def close_open_has_part_edges(
    graph_store: GraphStore | GraphStoreTransaction,
    *,
    document_node_id: UUID,
    job_id: UUID | None = None,
    keep_node_ids: Sequence[UUID] = (),
) -> int:
    rows = await graph_store.execute_write(
        close_has_part_query(),
        {
            "document_node_id": str(document_node_id),
            "job_id": str(job_id) if job_id is not None else None,
            "keep_node_ids": [str(node_id) for node_id in keep_node_ids],
        },
    )
    return int(rows[0].get("closed", 0)) if rows else 0
