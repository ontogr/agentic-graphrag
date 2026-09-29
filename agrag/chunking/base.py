"""The Chunker contract: how a Document becomes Chunks, and how that is recorded."""

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    PrivateAttr,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from agrag.chunking._text import build_text_chunks
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.provenance import TextProvenance


DEFAULT_TOKENIZER = "o200k_base"


def fingerprint_of(value: object) -> str:
    """Return a short stable hash of a JSON-safe value.

    Args:
        value: Data made of dicts, lists, strings, numbers, booleans and ``None``.

    Returns:
        The first 16 hex characters of the SHA-256 of the canonical JSON.
    """
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class ChunkingError(Exception):
    """A chunker broke the chunk contract or could not chunk a document."""


class Chunker(BaseModel, ABC):
    """Splits one Document into Chunks and builds their provenance.

    A chunker is plain data: its fields are its settings. ``settings()`` lists them
    and ``fingerprint()`` hashes them, so two chunkers with equal settings have equal
    fingerprints. Subclasses implement ``strategy`` and ``_split``. ``chunk()``
    checks what ``_split`` returns and records the chunker on every chunk.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    _fingerprint: str = PrivateAttr(default="")

    def model_post_init(self, context: Any, /) -> None:
        """Compute the fingerprint once, after the settings are validated."""
        self._fingerprint = fingerprint_of(self.settings())

    @property
    @abstractmethod
    def strategy(self) -> str:
        """The stable name of this strategy, for example ``"recursive"``."""

    def chunk(self, document: Document) -> list[Chunk]:
        """Split a document into chunks.

        Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
        with text provenance has text equal to ``document.text`` at its offsets.

        Args:
            document: The document to split.

        Returns:
            The chunks, in document order, each with ``chunker`` and ``chunker_hash``
            set. A strategy that sets ``chunker`` itself keeps its value.

        Raises:
            ChunkingError: The strategy returned chunks that break the contract.
        """
        chunks = self._split(document)
        self._check(document, chunks)
        return [
            chunk.model_copy(
                update={
                    "chunker": chunk.chunker or self.strategy,
                    "chunker_hash": self._fingerprint,
                }
            )
            for chunk in chunks
        ]

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Put the strategy name first, so a dumped chunker names its strategy."""
        return {"strategy": self.strategy, **handler(self)}

    def settings(self) -> dict[str, Any]:
        """Return the strategy name and every setting as JSON-safe data.

        A setting that is itself a chunker appears as that chunker's settings.
        """
        dumped = self.model_dump(mode="json")
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, Chunker):
                dumped[name] = value.settings()
        return dumped

    def fingerprint(self) -> str:
        """Return the hash of ``settings()``, 16 hex characters."""
        return self._fingerprint

    @abstractmethod
    def _split(self, document: Document) -> list[Chunk]:
        """Split a document. ``chunk()`` validates and stamps the result."""

    def _check(self, document: Document, chunks: list[Chunk]) -> None:
        """Raise ChunkingError when chunks break the contract."""
        previous_start = 0
        for position, chunk in enumerate(chunks):
            if chunk.index != position:
                raise self._error(document, position, f"index is {chunk.index}")
            if not chunk.text:
                raise self._error(document, position, "text is empty")
            provenance = chunk.provenance
            if not isinstance(provenance, TextProvenance):
                continue
            start, end = provenance.char_start, provenance.char_end
            if not 0 <= start < end <= len(document.text):
                raise self._error(
                    document, position, f"span {start}:{end} is outside the text"
                )
            if start < previous_start:
                raise self._error(document, position, "span is out of order")
            if chunk.text != document.text[start:end]:
                raise self._error(
                    document, position, "text differs from the source at its span"
                )
            previous_start = start

    def _error(self, document: Document, index: int, reason: str) -> ChunkingError:
        return ChunkingError(
            f"{self.strategy} chunker, document {document.resolved_document_key!r}, "
            f"chunk {index}: {reason}"
        )


class SpanChunker(Chunker):
    """A chunker that only decides where to cut; text and offsets come from the source.

    Subclasses build an engine that returns objects with ``start_index`` and
    ``end_index`` for a text. The chunk text is always a slice of the document text,
    so a lossy tokenizer round trip cannot change it.
    """

    _engine: Any = PrivateAttr(default=None)

    def model_post_init(self, context: Any, /) -> None:
        """Build the engine once, so a bad setting fails at construction."""
        super().model_post_init(context)
        try:
            self._engine = self._build_engine()
        except Exception as exc:
            raise ValueError(
                f"Cannot build the {self.strategy} chunker: {exc}"
            ) from exc

    @abstractmethod
    def _build_engine(self) -> Any:
        """Return an object whose ``chunk(text)`` yields pieces with offsets."""

    def spans(self, text: str) -> list[tuple[int, int]]:
        """Return the half-open character spans this strategy cuts text into.

        A cut inside a character that a tokenizer splits into several tokens makes
        an empty piece. This method drops empty pieces, and no text is lost with them.

        Args:
            text: The text to cut.

        Returns:
            The spans, in order, all non-empty.
        """
        return [
            (piece.start_index, piece.end_index)
            for piece in self._engine.chunk(text)
            if piece.end_index > piece.start_index
        ]

    def _split(self, document: Document) -> list[Chunk]:
        spans = self.spans(document.text)
        if not spans and document.text.strip():
            raise self._error(document, 0, "no chunks for non-empty text")
        return build_text_chunks(document, spans)
