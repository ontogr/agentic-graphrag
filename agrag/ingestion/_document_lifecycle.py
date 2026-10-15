"""Shared graph helpers for document version lifecycle operations.

A document is decided against its dates and the stamps of its newest open chunk.
The decision can skip work, update dates, re-extract in place, or write a new
version.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel

from agrag.common.data_models.update_decision import UpdateDecision
from agrag.common.schema_fingerprint import RunRecord
from agrag.cypher.documents import current_run_record_query, find_document_query
from agrag.cypher.relations import close_has_part_query
from agrag.graphdb.base import GraphStore


if TYPE_CHECKING:
    from agrag.graphdb.base import GraphStoreTransaction


@dataclass(frozen=True, slots=True)
class DocumentChange:
    """A committed change to one document, written as an activation record.

    The cutover job passes it to the commit transaction, which appends one
    activation to the document's history in the same transaction that flips
    its edges.

    Attributes:
        document_node_id: The id of the Document node the change applies to.
        document_key: The stable key of the document.
        verb: ``add`` for the first version of a key, ``update`` for a new
            version that replaces the current one, or ``delete`` for a
            soft deletion.
        content_hash: The content hash of the new version, or ``None`` for a
            delete.
        previous_content_hash: The content hash of the version the change
            replaces, or ``None`` when the key had no stored version.
        version_id: The version id of the new version, or ``None`` for a
            delete.
    """

    document_node_id: UUID
    document_key: str
    verb: Literal["add", "update", "delete"]
    content_hash: str | None
    previous_content_hash: str | None
    version_id: str | None


class DocumentLookup(BaseModel):
    """Persisted identity and the stamps of the newest open chunk of a document.

    Attributes:
        document_node_id: The id of the persisted Document node.
        current_content_hash: The content hash of the current version.
        has_open_chunks: Whether the current version has a committed chunk
            behind an open ``HAS_PART`` edge.
        current_version_id: The version id on that edge, or ``None`` when the
            document has no open chunk.
        current_chunker_hash: The chunker fingerprint recorded on that chunk,
            or ``None`` when it records none.
        current_schema_fingerprint: The schema fingerprint recorded on that
            chunk, or ``None`` when it records none.
        current_extraction_fingerprint: The extraction fingerprint recorded on
            that chunk, or ``None`` when it records none.
        current_published_at: The stored publication date.
        current_content_date: The stored content date.
    """

    document_node_id: UUID
    current_content_hash: str
    has_open_chunks: bool = False
    current_version_id: str | None = None
    current_chunker_hash: str | None = None
    current_schema_fingerprint: str | None = None
    current_extraction_fingerprint: str | None = None
    current_published_at: date | None = None
    current_content_date: date | None = None

    def decide(
        self,
        *,
        content_hash: str,
        version_id: str,
        chunker_hash: str,
        run: RunRecord,
        force: bool = False,
        published_at: date | None = None,
        content_date: date | None = None,
    ) -> UpdateDecision:
        """Pick the update outcome for a new input against the stored version.

        A document without an open chunk is always written as a new version.
        So is any change to the content, the section structure, the chunking or
        the schema. When those match, the chunks are kept and re-extracted if
        forced or if the extraction stamp differs or is missing. Date-only
        changes are written without extraction.

        Args:
            content_hash: The content hash of the new input.
            version_id: The version id of the new input, from ``version_id``.
            chunker_hash: The chunker fingerprint of the new input.
            run: The run record of the new run.
            force: Whether to re-extract matching chunks.
            published_at: The new publication date, if known.
            content_date: The new content date, if known.

        Returns:
            The selected update outcome.
        """
        if (
            not self.has_open_chunks
            or self.current_content_hash != content_hash
            or self.current_version_id != version_id
            or self.current_chunker_hash != chunker_hash
            or self.current_schema_fingerprint != run.schema_fingerprint
        ):
            return UpdateDecision.NEW_VERSION
        if force or self.current_extraction_fingerprint != run.extraction_fingerprint:
            return UpdateDecision.IN_PLACE
        if (
            self.current_published_at != published_at
            or self.current_content_date != content_date
        ):
            return UpdateDecision.METADATA_ONLY
        return UpdateDecision.NO_OP


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
    current_published_at = row.get("published_at")
    current_content_date = row.get("content_date")
    run_rows = await graph_store.execute_read(
        current_run_record_query(), {"document_key": document_key}
    )
    if not run_rows:
        return DocumentLookup(
            document_node_id=document_node_id,
            current_content_hash=current_content_hash,
            current_published_at=current_published_at,
            current_content_date=current_content_date,
        )
    run_row = run_rows[0]
    return DocumentLookup(
        document_node_id=document_node_id,
        current_content_hash=current_content_hash,
        current_published_at=current_published_at,
        current_content_date=current_content_date,
        has_open_chunks=True,
        current_version_id=_optional_str(run_row.get("version_id")),
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
