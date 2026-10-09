"""The section chunker: one packer that serves every source format."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

from chonkie import RecursiveChunker
from chonkie.tokenizer import AutoTokenizer
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from agrag.chunking._tables import table_texts
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import (
    Document,
    DocumentSection,
    Unit,
    UnitKind,
)
from agrag.common.data_models.provenance import (
    PageProvenance,
    PageSpan,
    TextProvenance,
)
from agrag.common.data_models.structure import (
    chunk_id,
    common_ancestor,
    heading_paths,
    node_id,
    reading_positions,
    section_keys,
    version_id,
)


DEFAULT_SIZE = 600
DEFAULT_TOKENIZER = "o200k_base"
CHUNKER_NAME = "section"
_MIN_CHARACTERS_PER_PIECE = 24


class ChunkingError(Exception):
    """A chunker could not split a document without changing its text."""


def fingerprint_of(value: object) -> str:
    """Return a short stable hash of a JSON-safe value.

    Args:
        value: Data made of dicts, lists, strings, numbers, booleans and ``None``.

    Returns:
        The first 16 hex characters of the SHA-256 of the canonical JSON.
    """
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _by_page(spans: list[PageSpan]) -> list[PageSpan]:
    return sorted(spans, key=lambda span: span.page_no)


def _is_page_layout(section: DocumentSection) -> bool:
    """Return whether a section's units have pages and no text offsets."""
    return bool(section.units) and section.units[0].char_start is None


@dataclass(frozen=True, slots=True)
class TextPiece:
    """A piece of text that ``Chunker.split`` made.

    Attributes:
        text: The text of the piece. It equals the slice of the source text from
            ``start_index`` to ``end_index``.
        start_index: The offset of the first character in the source text.
        end_index: The offset just past the last character in the source text.
        token_count: The number of tokens in the piece.
    """

    text: str
    start_index: int
    end_index: int
    token_count: int


@dataclass(slots=True)
class _Piece:
    """Text that goes into a chunk whole, with where it came from."""

    text: str
    start: int | None
    end: int | None
    pages: list[PageSpan]
    section: int
    position: int
    tokens: int


class Chunker(BaseModel):
    """Packs the sections of a Document into chunks.

    The chunker walks the sections in reading order. It packs the units of a
    section into a chunk until the next unit would pass ``size`` tokens. It splits a
    unit that is over ``size`` on its own, at paragraph, sentence, clause or word
    boundaries. When a section ends and the open chunk holds fewer than ``min_size``
    tokens, the chunk goes on into the next section. A table never mixes with text:
    it becomes one chunk, or row groups that each repeat the header row.

    A chunk from a text source is an exact slice of ``Document.text``. A chunk from a
    source with page layout joins the text of its units with a blank line. A document
    with no sections, such as one record row, is one unit of text.

    Size counts the text of the units. The blank lines that join units are not counted,
    so a chunk can pass ``size`` by a few tokens.

    Attributes:
        size: The most tokens in a chunk.
        min_size: A chunk with fewer tokens than this goes on into the next section.
            Zero, the default, means a quarter of ``size``.
        tokenizer: The tokenizer that counts tokens. A name that chonkie accepts.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    size: int = Field(default=DEFAULT_SIZE, gt=0)
    min_size: int = Field(default=0, ge=0)
    tokenizer: str = DEFAULT_TOKENIZER

    _count: Any = PrivateAttr(default=None)
    _splitter: Any = PrivateAttr(default=None)
    _fingerprint: str = PrivateAttr(default="")

    @model_validator(mode="before")
    @classmethod
    def _default_min_size(cls, data: Any) -> Any:
        """Set ``min_size`` to a quarter of ``size`` when the caller gives none."""
        if isinstance(data, dict) and not data.get("min_size"):
            return {**data, "min_size": data.get("size", DEFAULT_SIZE) // 4}
        return data

    def model_post_init(self, context: Any, /) -> None:
        """Check the settings and build the tokenizer and the splitter once."""
        if self.min_size >= self.size:
            raise ValueError("min_size must be smaller than size")
        self._count = AutoTokenizer(self.tokenizer).count_tokens
        self._splitter = RecursiveChunker(
            tokenizer=self.tokenizer,
            chunk_size=self.size,
            min_characters_per_chunk=_MIN_CHARACTERS_PER_PIECE,
        )
        self._fingerprint = fingerprint_of(self.settings())

    def settings(self) -> dict[str, Any]:
        """Return the settings as plain data."""
        return self.model_dump()

    def fingerprint(self) -> str:
        """Return the hash of the settings. Equal settings give equal hashes."""
        return self._fingerprint

    def count_tokens(self, text: str) -> int:
        """Return the number of tokens in a text, counted with ``tokenizer``."""
        return self._count(text)

    def split(self, text: str) -> list[TextPiece]:
        """Split a text into pieces of at most ``size`` tokens.

        Args:
            text: The text to split.

        Returns:
            The pieces in order. ``text`` of each piece equals the slice of the text
            from its ``start_index`` to its ``end_index``.

        Raises:
            ChunkingError: A piece does not match its slice, or the pieces do not
                join back into the text.
        """
        parts = [
            TextPiece(
                text=part.text,
                start_index=part.start_index,
                end_index=part.end_index,
                token_count=part.token_count,
            )
            for part in self._splitter(text)
        ]
        if any(part.text != text[part.start_index : part.end_index] for part in parts):
            raise ChunkingError("the splitter moved text away from its offsets")
        if "".join(part.text for part in parts) != text:
            raise ChunkingError("the splitter changed or dropped text")
        return parts

    def chunk(self, document: Document) -> list[Chunk]:
        """Split a document into chunks.

        Args:
            document: The document to split.

        Returns:
            The chunks in reading order. Their indexes run from 0 without gaps.

        Raises:
            ChunkingError: The splitter changed or dropped text.
        """
        return _Run(self, document).chunks()


class _Run:
    """The state of one ``Chunker.chunk`` call."""

    def __init__(self, chunker: Chunker, document: Document) -> None:
        self._chunker = chunker
        # A document without sections, such as one record row, is one unit of text.
        self._whole = not document.sections and bool(document.text.strip())
        if self._whole:
            body = Unit(
                kind=UnitKind.PARAGRAPH,
                text=document.text,
                char_start=0,
                char_end=len(document.text),
            )
            section = DocumentSection(heading="", depth=0, units=[body])
            document = document.model_copy(update={"sections": [section]})
        self._document = document
        self._sections = document.sections
        self._version = version_id(document)
        self._section_ids = [
            node_id(key, self._version) for key in section_keys(document)
        ]
        self._paths = heading_paths(self._sections)
        self._document_id = Document.node_id_for(
            document_key=document.resolved_document_key
        )
        self._out: list[Chunk] = []
        self._open: list[_Piece] = []
        self._used = 0

    def chunks(self) -> list[Chunk]:
        """Pack every section and return the chunks."""
        chunker = self._chunker
        _, unit_positions = reading_positions(self._document)
        for i, section in enumerate(self._sections):
            if self._open and self._used >= chunker.min_size:
                self._flush()
            if section.heading and _is_page_layout(section):
                heading = Unit(kind=UnitKind.PARAGRAPH, text=section.heading)
                self._add(self._piece(heading, i, 0))
            for j, unit in enumerate(section.units):
                position = unit_positions[i][j]
                if unit.kind == UnitKind.TABLE:
                    self._flush()
                    self._table(unit, i, position)
                elif unit.text.strip():
                    for piece in self._split_unit(unit, i, position):
                        self._add(piece)
        self._flush()
        return self._out

    def _piece(self, unit: Unit, section: int, position: int) -> _Piece:
        return _Piece(
            text=unit.text,
            start=unit.char_start,
            end=unit.char_end,
            pages=unit.pages,
            section=section,
            position=position,
            tokens=self._chunker.count_tokens(unit.text),
        )

    def _split_unit(self, unit: Unit, section: int, position: int) -> list[_Piece]:
        """Return the unit as one piece, or as several when it is over the size."""
        whole = self._piece(unit, section, position)
        if whole.tokens <= self._chunker.size:
            return [whole]
        base = unit.char_start
        return [
            _Piece(
                text=part.text,
                start=None if base is None else base + part.start_index,
                end=None if base is None else base + part.end_index,
                pages=unit.pages,
                section=section,
                position=position,
                tokens=part.token_count,
            )
            for part in self._chunker.split(unit.text)
        ]

    def _add(self, piece: _Piece) -> None:
        if self._open and self._used + piece.tokens > self._chunker.size:
            self._flush()
        self._open.append(piece)
        self._used += piece.tokens

    def _table(self, unit: Unit, section: int, position: int) -> None:
        spans = _by_page(unit.pages)
        for text in table_texts(unit, self._chunker.size, self._chunker.count_tokens):
            provenance = PageProvenance(page_spans=spans)
            self._emit(text, provenance, [section], position, "table")

    def _flush(self) -> None:
        pieces = self._open
        if not pieces:
            return
        first, last = pieces[0], pieces[-1]
        provenance: TextProvenance | PageProvenance
        if first.start is not None and last.end is not None:
            text = self._document.text[first.start : last.end]
            provenance = TextProvenance(char_start=first.start, char_end=last.end)
        else:
            text = "\n\n".join(piece.text for piece in pieces)
            provenance = PageProvenance(
                page_spans=_by_page([span for piece in pieces for span in piece.pages])
            )
        covered = sorted({piece.section for piece in pieces})
        self._emit(text, provenance, covered, first.position)
        self._open, self._used = [], 0

    def _emit(
        self,
        text: str,
        provenance: TextProvenance | PageProvenance,
        covered: list[int],
        position: int,
        kind: Literal["text", "table"] = "text",
    ) -> None:
        ancestor = common_ancestor(self._sections, covered)
        index = len(self._out)
        fingerprint = self._chunker.fingerprint()
        section_ids = [] if self._whole else [self._section_ids[i] for i in covered]
        parent_section_id = None
        if not self._whole and ancestor is not None:
            parent_section_id = self._section_ids[ancestor]
        self._out.append(
            Chunk(
                id=chunk_id(self._document_id, self._version, fingerprint, index),
                document_id=self._document_id,
                index=index,
                text=text,
                provenance=provenance,
                heading_path=[] if ancestor is None else self._paths[ancestor],
                content_kind=kind,
                chunker=CHUNKER_NAME,
                chunker_hash=fingerprint,
                section_ids=section_ids,
                parent_section_id=parent_section_id,
                position=position,
            )
        )
