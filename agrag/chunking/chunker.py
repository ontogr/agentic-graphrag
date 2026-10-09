"""The section chunker: one packer that serves every source format."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Literal
from uuid import UUID

from chonkie import RecursiveChunker
from chonkie.tokenizer import AutoTokenizer

from agrag.chunking._tables import table_texts, would_exceed
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
    unit_keys,
    version_id,
)


DEFAULT_SIZE = 600
DEFAULT_TOKENIZER = "o200k_base"
CHUNKER_NAME = "section"
_SEPARATOR = "\n\n"
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
    is_heading: bool = False


@dataclass(frozen=True, slots=True)
class ChunkPlacement:
    """Where one chunk hangs in the structure of its document.

    Attributes:
        chunk_index: The index of the chunk in ``ChunkedDocument.chunks``.
        parent_node_id: The id of the table node the chunk came from, or of the
            lowest section that holds its text, or of the document node when no
            section does.
        order: The edge order under the parent: the reading position of the first
            unit in a text chunk, or the chunk index for a table chunk.
    """

    chunk_index: int
    parent_node_id: UUID
    order: int


@dataclass(frozen=True, slots=True)
class ChunkedDocument:
    """The chunks of one document with where each chunk hangs.

    Attributes:
        chunks: The chunks in reading order. Their indexes run from 0.
        placements: One placement per chunk, in the same order as ``chunks``.
    """

    chunks: list[Chunk]
    placements: list[ChunkPlacement]


@dataclass(frozen=True)
class Chunker:
    """Packs the sections of a Document into chunks.

    The chunker walks the sections in reading order. It packs the units of a
    section into a chunk until the next unit would pass ``size`` tokens. It splits a
    unit that is over ``size`` on its own, at paragraph, sentence, clause or word
    boundaries. When a section ends and the open chunk holds fewer than ``min_size``
    tokens, the chunk goes on into the next section. A table never mixes with text:
    it becomes one chunk, or row groups that each repeat the header row.

    A chunk joins the text of its pieces with a blank line. Size counts that joined
    text: every piece plus every blank line between pieces. A document whose units
    all carry text offsets gives text provenance over the span of its units. A
    document whose units carry no offsets gives page provenance.

    Attributes:
        size: The most tokens in a chunk.
        min_size: A chunk with fewer tokens than this goes on into the next section.
            ``None``, the default, means a quarter of ``size``.
        tokenizer: The tokenizer that counts tokens. A name that chonkie accepts.
    """

    size: int = DEFAULT_SIZE
    min_size: int | None = None
    tokenizer: str = DEFAULT_TOKENIZER

    _count: Callable[[str], int] = field(init=False, repr=False, compare=False)
    _splitter: Callable[[str], list[Any]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Check the settings and build the tokenizer and the splitter once."""
        if self.size <= 0:
            raise ValueError("size must be a positive integer")
        if self.effective_min_size < 0:
            raise ValueError("min_size must not be negative")
        if self.effective_min_size >= self.size:
            raise ValueError("min_size must be smaller than size")
        object.__setattr__(self, "_count", AutoTokenizer(self.tokenizer).count_tokens)
        object.__setattr__(
            self,
            "_splitter",
            RecursiveChunker(
                tokenizer=self.tokenizer,
                chunk_size=self.size,
                min_characters_per_chunk=_MIN_CHARACTERS_PER_PIECE,
            ),
        )

    @property
    def effective_min_size(self) -> int:
        """Return the merge threshold: ``min_size``, or a quarter of ``size``."""
        return self.size // 4 if self.min_size is None else self.min_size

    def settings(self) -> dict[str, Any]:
        """Return the settings as plain data."""
        return {
            "size": self.size,
            "min_size": self.effective_min_size,
            "tokenizer": self.tokenizer,
        }

    @cached_property
    def fingerprint(self) -> str:
        """Return the hash of the settings. Equal settings give equal hashes."""
        return fingerprint_of(self.settings())

    def count_tokens(self, text: str) -> int:
        """Return the number of tokens in a text, counted with ``tokenizer``."""
        return self._count(text)

    def split(self, text: str) -> list[TextPiece]:
        """Split a text into pieces of at most ``size`` tokens.

        Args:
            text: The text to split.

        Returns:
            The pieces in order. Each piece's text is a slice of the input text.

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

    def chunk(self, document: Document) -> ChunkedDocument:
        """Split a document into chunks with their placements.

        Args:
            document: The document to split.

        Returns:
            The chunks in reading order with one placement per chunk.

        Raises:
            ChunkingError: The document mixes units that carry text offsets with
                units that carry none, or the splitter changed or dropped text.
        """
        return _Run(self, document).run()


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
        units = [unit for section in document.sections for unit in section.units]
        offsets = [unit.char_start is not None for unit in units]
        if any(offsets) and not all(offsets):
            raise ChunkingError(
                "the document mixes units with text offsets and units with none"
            )
        self._is_text = bool(units) and all(offsets)
        self._sections = document.sections
        self._version = version_id(document)
        keys = section_keys(document)
        self._section_ids = [node_id(key, self._version) for key in keys]
        self._unit_ids = {
            at: node_id(key, self._version)
            for at, key in unit_keys(document, keys).items()
        }
        self._paths = heading_paths(self._sections)
        self._heading_positions, self._unit_positions = reading_positions(document)
        self._document_id = Document.node_id_for(
            document_key=document.resolved_document_key
        )
        self._separator_cost = chunker.count_tokens(_SEPARATOR)
        self._chunks: list[Chunk] = []
        self._placements: list[ChunkPlacement] = []
        self._open: list[_Piece] = []
        self._used = 0
        self._taken_orders: set[tuple[UUID, int]] = set()

    def run(self) -> ChunkedDocument:
        """Pack every section and return the chunks with their placements."""
        chunker = self._chunker
        for i, section in enumerate(self._sections):
            if self._open and self._used >= chunker.effective_min_size:
                self._flush()
            if section.heading:
                for piece in self._split_heading(section.heading, i):
                    self._add(piece)
            for j, unit in enumerate(section.units):
                position = self._unit_positions[i][j]
                if unit.kind == UnitKind.TABLE:
                    self._flush()
                    self._table(unit, i, j, position)
                elif unit.text.strip():
                    for piece in self._split_unit(unit, i, position):
                        self._add(piece)
        self._flush()
        return ChunkedDocument(chunks=self._chunks, placements=self._placements)

    def _heading_piece(self, heading: str, section: int) -> _Piece:
        return _Piece(
            text=heading,
            start=None,
            end=None,
            pages=[],
            section=section,
            position=self._heading_positions[section],
            tokens=self._chunker.count_tokens(heading),
            is_heading=True,
        )

    def _split_heading(self, heading: str, section: int) -> list[_Piece]:
        """Return the heading as one piece, or as several when it is over size."""
        whole = self._heading_piece(heading, section)
        if whole.tokens <= self._chunker.size:
            return [whole]
        return [
            _Piece(
                text=part.text,
                start=None,
                end=None,
                pages=[],
                section=section,
                position=whole.position,
                tokens=part.token_count,
                is_heading=True,
            )
            for part in self._chunker.split(heading)
        ]

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
        if self._open:
            cost = self._separator_cost + piece.tokens
            if would_exceed(self._used, cost, self._chunker.size):
                self._flush()
                self._open.append(piece)
                self._used = piece.tokens
            else:
                self._open.append(piece)
                self._used += cost
        else:
            self._open.append(piece)
            self._used = piece.tokens

    def _table(self, unit: Unit, section: int, unit_index: int, position: int) -> None:
        texts = table_texts(unit, self._chunker.size, self._chunker.count_tokens)
        table_id = self._unit_ids.get((section, unit_index))
        if table_id is None:
            raise ChunkingError("a table chunk has no table unit at its position")
        # One table keeps the pages of its unit. Row groups each hold a subset of
        # the rows with no per-row pages, so they claim no pages at all.
        spans = _by_page(unit.pages) if len(texts) == 1 else []
        for text in texts:
            self._emit(
                text,
                PageProvenance(page_spans=spans),
                [section],
                position,
                kind="table",
                table=table_id,
            )

    def _flush(self) -> None:
        pieces = self._open
        if not pieces:
            return
        text = _SEPARATOR.join(piece.text for piece in pieces)
        provenance: TextProvenance | PageProvenance
        if self._is_text:
            starts = [piece.start for piece in pieces if piece.start is not None]
            ends = [piece.end for piece in pieces if piece.end is not None]
            if not starts or not ends:
                if all(piece.is_heading for piece in pieces):
                    # Headings carry no offsets, so a chunk of headings alone has
                    # no text span. The section tree still records them.
                    self._open, self._used = [], 0
                    return
                raise ChunkingError("a text chunk holds no text offsets")
            provenance = TextProvenance(char_start=min(starts), char_end=max(ends))
        else:
            provenance = PageProvenance(
                page_spans=_by_page([span for piece in pieces for span in piece.pages])
            )
        # Headings ride along as context. Only the sections that gave units set
        # the coverage, so an empty section never pulls the path up to itself.
        covered = sorted({piece.section for piece in pieces if not piece.is_heading})
        self._emit(text, provenance, covered, pieces[0].position)
        self._open, self._used = [], 0

    def _emit(
        self,
        text: str,
        provenance: TextProvenance | PageProvenance,
        covered: list[int],
        position: int,
        kind: Literal["text", "table"] = "text",
        *,
        table: UUID | None = None,
    ) -> None:
        ancestor = None if not covered else common_ancestor(self._sections, covered)
        index = len(self._chunks)
        fingerprint = self._chunker.fingerprint
        section_ids = [] if self._whole else [self._section_ids[i] for i in covered]
        if table is not None:
            parent, order = table, index
        elif self._whole or ancestor is None:
            parent, order = self._document_id, position
        else:
            parent, order = self._section_ids[ancestor], position
        # Pieces split from one unit share its position. Bump the order past
        # taken values so sibling edges keep the pieces' reading order.
        while (parent, order) in self._taken_orders:
            order += 1
        self._taken_orders.add((parent, order))
        self._chunks.append(
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
            )
        )
        self._placements.append(
            ChunkPlacement(chunk_index=index, parent_node_id=parent, order=order)
        )
