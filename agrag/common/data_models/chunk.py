"""The Chunk model: one retrieval-sized piece of a Document."""

from typing import Literal
from uuid import NAMESPACE_OID, UUID, uuid5

from pydantic import Field, model_validator

from agrag.common.data_models.data_point import DataPoint
from agrag.common.data_models.provenance import PageProvenance, TextProvenance


class Chunk(DataPoint):
    """One retrieval-sized piece of a Document.

    Attributes:
        document_id: The id of the parent Document. Use this id to look up fields such
        as
            ``record_index`` on the parent Document.
        index: The position of the chunk within its document, from 0.
        text: The chunk text.
        provenance: The location of this chunk in its source. The shape of this value
        depends
            on which chunker made the chunk.
        heading_path: The headings that contain this chunk, from outermost to innermost.
            Empty for a docling chunk and for a chunk with no heading above it.
        content_kind: The kind of content in this chunk. A text chunker always sets
            ``"text"``. A docling chunk can also be ``"table_row"``.
    """

    id: UUID | None = None
    document_id: UUID
    index: int = 0
    text: str
    provenance: TextProvenance | PageProvenance = Field(discriminator="kind")
    heading_path: list[str] = Field(default_factory=list)
    content_kind: Literal["text", "table_row", "code", "heading"] = "text"

    @model_validator(mode="after")
    def _resolve_id(self) -> "Chunk":
        """Compute ``id`` from the document, provenance, and index unless passed."""
        if self.id is None:
            self.id = self.id_for(
                document_id=self.document_id,
                provenance=self.provenance,
                index=self.index,
            )
        return self

    @classmethod
    def id_for(
        cls,
        *,
        document_id: UUID,
        provenance: TextProvenance | PageProvenance,
        index: int,
    ) -> UUID:
        """Compute the chunk id.

        For a text chunk, the id comes from the document id and the character span. A
        change in chunk size shifts the span, so it also changes the id.

        For a docling chunk, the id comes from the document id and the chunk index
        instead.
        Docling parsing is not always the same between runs, so this id is not stable
        across
        a re-parse of the same source.

        Args:
            document_id: The id of the parent Document.
            provenance: The provenance of the chunk. Its type picks which id rule
            applies.
            index: The position of the chunk within its document.

        Returns:
            The chunk id.
        """
        if isinstance(provenance, TextProvenance):
            key = f"Chunk:{document_id}:{provenance.char_start}:{provenance.char_end}"
        else:
            key = f"Chunk:{document_id}:{index}"
        return uuid5(NAMESPACE_OID, key)
