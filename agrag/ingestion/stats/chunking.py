"""Chunking-stage stats."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from pydantic import BaseModel

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, UnitKind


class ChunkingStats(BaseModel):
    """Chunking-stage results.

    Attributes:
        chunks: The number of chunks made.
        sections: The number of sections in the chunked documents.
        tables: The number of tables in the chunked documents.
        figures: The number of figures in the chunked documents.
    """

    chunks: int = 0
    sections: int = 0
    tables: int = 0
    figures: int = 0

    @classmethod
    def from_documents(
        cls, documents: Sequence[Document], chunks: Sequence[Chunk]
    ) -> ChunkingStats:
        """Count what the chunker and the loaders produced.

        Args:
            documents: The documents that were chunked.
            chunks: The chunks made from them.

        Returns:
            The counts.
        """
        kinds = Counter(
            unit.kind
            for document in documents
            for section in document.sections
            for unit in section.units
        )
        return cls(
            chunks=len(chunks),
            sections=sum(len(document.sections) for document in documents),
            tables=kinds[UnitKind.TABLE],
            figures=kinds[UnitKind.FIGURE],
        )
