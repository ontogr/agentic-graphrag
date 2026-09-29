"""The Chunk model: one retrieval-sized piece of a Document."""

import json
import re
from typing import Literal
from uuid import NAMESPACE_OID, UUID, uuid5

from pydantic import Field, model_validator

from agrag.common.data_models.data_point import DataPoint
from agrag.common.data_models.graph_record import NodeRecord
from agrag.common.data_models.provenance import PageProvenance, TextProvenance


# The fixed system label every Chunk node is written with.
CHUNK_LABEL = "Chunk"
""""""


def _clean_heading(heading: str) -> str:
    """Make a heading safe to place in a prompt line."""
    return re.sub(r"-{3,}", "-", " ".join(heading.split()))


class Chunk(DataPoint):
    """One retrieval-sized piece of a Document.

    Attributes:
        document_id: The id of the persisted Document graph node this chunk
            belongs to (see ``Document.node_id_for``). Stable across content
            versions of the same logical document; per-version identity lives
            in ``Chunk.id`` instead.
        index: The position of the chunk within its document, from 0.
        text: The chunk text.
        provenance: The location of this chunk in its source. The shape of this
            value depends on which chunker made the chunk.
        heading_path: The headings that contain this chunk, from outermost to innermost.
            Empty for a docling chunk and for a chunk with no heading above it.
        content_kind: The kind of content in this chunk. A text chunker always sets
            ``"text"``. A docling chunk can also be ``"table_row"``.
        chunker: The strategy name of the chunker that made this chunk. ``None`` for a
            chunk written before chunkers were recorded.
        chunker_hash: The fingerprint of the settings of the chunker that made this
            chunk. ``None`` for a chunk written before chunkers were recorded.
        level: ``1`` for a parent chunk, ``0`` for every other chunk. A parent
            chunk is the unit of extraction. A child chunk is the unit of search.
        parent_id: The id of the parent chunk of a child chunk. ``None`` for a
            parent and for a chunk that has no parent.
    """

    id: UUID | None = None
    document_id: UUID
    index: int = 0
    text: str
    provenance: TextProvenance | PageProvenance = Field(discriminator="kind")
    heading_path: list[str] = Field(default_factory=list)
    content_kind: Literal["text", "table_row", "code", "heading"] = "text"
    chunker: str | None = None
    chunker_hash: str | None = None
    level: int = 0
    parent_id: UUID | None = None
    embedding: list[float] | None = None

    @model_validator(mode="after")
    def _check_level(self) -> "Chunk":
        """Allow levels 0 and 1, and a parent id only on a level 0 chunk."""
        if self.level not in (0, 1):
            raise ValueError(f"level must be 0 or 1, got {self.level}")
        if self.level == 1 and self.parent_id is not None:
            raise ValueError("a parent chunk (level 1) cannot have a parent_id")
        return self

    @model_validator(mode="after")
    def _resolve_id(self) -> "Chunk":
        """Compute ``id`` from the document, provenance, and index unless passed."""
        if self.id is None:
            self.id = self.id_for(
                document_id=self.document_id,
                provenance=self.provenance,
                index=self.index,
                level=self.level,
            )
        return self

    @classmethod
    def id_for(
        cls,
        *,
        document_id: UUID,
        version_id: UUID | None = None,
        provenance: TextProvenance | PageProvenance,
        index: int,
        chunker_hash: str | None = None,
        level: int = 0,
    ) -> UUID:
        """Compute the chunk id.

        For a text chunk, the id comes from the document id and the character span. A
        change in chunk size shifts the span, so it also changes the id. When supplied,
        ``version_id`` makes the id distinct for each version of a document.

        For a docling chunk, the id comes from the document id, the chunker hash and
        the chunk index instead. The hash keeps a re-chunk with new settings from
        overwriting chunk N of the earlier settings. Docling parsing is not always the
        same between runs, so this id is not stable across a re-parse of the same
        source.

        Args:
            document_id: The id of the parent Document.
            version_id: Optional id for the parent document version.
            provenance: The provenance of the chunk. Its type picks which id rule
                applies.
            index: The position of the chunk within its document.
            chunker_hash: The fingerprint of the chunker. Only a docling chunk uses
                it; a text chunk id ignores it.
            level: The chunk level. A parent chunk (level 1) adds a level part, so a
                parent and a child with the same span get different ids. The id of a
                level 0 chunk does not change.

        Returns:
            The chunk id.
        """
        version_suffix = f":{version_id}" if version_id is not None else ""
        level_suffix = f":L{level}" if level != 0 else ""
        if isinstance(provenance, TextProvenance):
            key = (
                f"Chunk:{document_id}{version_suffix}:"
                f"{provenance.char_start}:{provenance.char_end}{level_suffix}"
            )
        else:
            hash_part = f"{chunker_hash}:" if chunker_hash is not None else ""
            key = (
                f"Chunk:{document_id}{version_suffix}:{hash_part}{index}{level_suffix}"
            )
        return uuid5(NAMESPACE_OID, key)

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

        Provenance is flattened to a plain JSON-safe dict via model_dump —
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
        if self.level != 0:
            properties["level"] = self.level
        if self.parent_id is not None:
            properties["parent_id"] = str(self.parent_id)
        if self.embedding is not None:
            properties["embedding"] = self.embedding
        return NodeRecord(id=self.id, labels=[CHUNK_LABEL], properties=properties)
