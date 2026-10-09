"""The Chunk model: one retrieval-sized piece of a Document."""

import json
import re
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from agrag.common.data_models.data_point import DataPoint
from agrag.common.data_models.graph_record import NodeRecord
from agrag.common.data_models.provenance import PageProvenance, TextProvenance


# The fixed system label every Chunk node is written with.
CHUNK_LABEL = "Chunk"


def _clean_heading(heading: str) -> str:
    """Make a heading safe to place in a prompt line."""
    return re.sub(r"-{3,}", "-", " ".join(heading.split()))


class Chunk(DataPoint):
    """One retrieval-sized piece of a Document.

    Attributes:
        document_id: The id of the persisted Document graph node this chunk
            belongs to (see ``Document.node_id_for``). It stays stable across
            content versions of the same logical document. Per-version
            identity lives in ``Chunk.id`` instead.
        index: The position of the chunk within its document, from 0.
        text: The chunk text.
        provenance: The location of this chunk in its source. A text source gives
            character offsets. A source with page layout gives pages and boxes, and
            a source with neither gives no page spans.
        heading_path: The headings that contain this chunk, from outermost to
            innermost. Empty for a chunk with no heading above it.
        content_kind: ``"text"`` for a chunk of running text and ``"table"`` for a
            chunk made from a table.
        chunker: The name of the chunker that made this chunk. ``None`` for a chunk
            written before chunkers were recorded.
        chunker_hash: The fingerprint of the settings of the chunker that made this
            chunk. ``None`` for a chunk written before chunkers were recorded.
        section_ids: The node ids of the sections whose text the chunk holds, in
            reading order. Empty for a document with no sections.
    """

    id: UUID | None = None
    document_id: UUID
    index: int = 0
    text: str
    provenance: TextProvenance | PageProvenance = Field(discriminator="kind")
    heading_path: list[str] = Field(default_factory=list)
    content_kind: Literal["text", "table"] = "text"
    chunker: str | None = None
    chunker_hash: str | None = None
    embedding: list[float] | None = None
    section_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_section_refs(self) -> "Chunk":
        for heading in self.heading_path:
            if not heading.strip():
                raise ValueError("heading_path must not hold a blank heading")
        if len(set(self.section_ids)) != len(self.section_ids):
            raise ValueError("section_ids must not repeat a section")
        return self

    @model_validator(mode="after")
    def _check_provenance(self) -> "Chunk":
        if isinstance(self.provenance, TextProvenance):
            start, end = self.provenance.char_start, self.provenance.char_end
            if not 0 <= start <= end:
                raise ValueError("text provenance needs 0 <= char_start <= char_end")
        if self.content_kind == "table" and isinstance(self.provenance, TextProvenance):
            raise ValueError("a table chunk must carry page provenance")
        return self

    @model_validator(mode="after")
    def _resolve_id(self) -> "Chunk":
        if self.id is None:
            raise ValueError("Chunk.id must be set by the chunker.")
        return self

    @property
    def contextual_text(self) -> str:
        """The text with its heading path above it, for embedding.

        The stored text and its offsets do not change. A chunk with no heading path
        returns its text.
        """
        label = self.section_label()
        return self.text if label is None else f"{label}\n\n{self.text}"

    def section_label(self) -> str | None:
        """Return the heading path as one line, or ``None`` when the path is empty.

        Whitespace runs in a heading become one space, and runs of three or more
        dashes become one dash, so a heading cannot end the text block of the
        extraction prompt.
        """
        if not self.heading_path:
            return None
        return " > ".join(_clean_heading(heading) for heading in self.heading_path)

    def to_node_record(self) -> NodeRecord:
        """Return this chunk as a GraphStore write record.

        Provenance is flattened to a plain JSON-safe dict via model_dump.
        GraphStore's own serialize.node_params only converts UUIDs and walks
        containers.

        Raises:
            ValueError: id is None.
        """
        if self.id is None:
            raise ValueError("Chunk.id must be set before writing to GraphStore.")
        properties: dict[str, object] = {
            "document_id": str(self.document_id),
            "index": self.index,
            "text": self.text,
            "provenance": json.dumps(self.provenance.model_dump(mode="json")),
            "heading_path": self.heading_path,
            "content_kind": self.content_kind,
            "created_at": self.created_at.isoformat(),
        }
        if self.chunker is not None:
            properties["chunker"] = self.chunker
        if self.chunker_hash is not None:
            properties["chunker_hash"] = self.chunker_hash
        if self.section_ids:
            properties["section_ids"] = [str(i) for i in self.section_ids]
        if self.embedding is not None:
            properties["embedding"] = self.embedding
        return NodeRecord(id=self.id, labels=[CHUNK_LABEL], properties=properties)
