"""The heading-aware strategy: sections packed to a token budget."""

from typing import Any

from chonkie.tokenizer import AutoTokenizer
from pydantic import Field, PrivateAttr, SerializeAsAny

from agrag.chunking._text import build_marked_chunks, shifted_spans
from agrag.chunking.base import DEFAULT_TOKENIZER, Chunker, SpanChunker
from agrag.chunking.recursive import RecursiveChunker
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document


class HeadingChunker(Chunker):
    """Cuts a document into sections at its headings and packs them to a budget.

    The chunker reads ``Document.heading_outline``. A heading of ``split_level`` or
    higher (a level number at or below ``split_level``) starts a new section, and no
    chunk holds such a heading except at its start. A section within ``chunk_size``
    tokens is one chunk. A larger section is cut at its deeper headings and the
    parts are packed to the budget. A part that is still too large goes to
    ``fallback``, and its chunks have the chunker name ``heading:<fallback
    strategy>``. A document with no headings goes to ``fallback`` as a whole and its
    chunks have the same name. Only the plain text loaders for Markdown and AsciiDoc
    fill the outline.

    Attributes:
        chunk_size: The most tokens in a chunk, counted with ``tokenizer``. Tokens
            are counted for each part alone, so a packed chunk can be a few tokens
            over.
        split_level: The deepest heading level that starts a new section, from 1 to 6.
        tokenizer: The tokenizer that counts size. ``"character"`` counts characters.
        fallback: The chunker for a part above the budget and for a document without
            headings.
    """

    chunk_size: int = Field(default=256, gt=0)
    split_level: int = Field(default=2, ge=1, le=6)
    tokenizer: str = DEFAULT_TOKENIZER
    fallback: SerializeAsAny[SpanChunker] = Field(default_factory=RecursiveChunker)

    _counter: Any = PrivateAttr(default=None)

    def model_post_init(self, context: Any, /) -> None:
        """Load the tokenizer once, so a bad name fails at construction."""
        super().model_post_init(context)
        try:
            self._counter = AutoTokenizer(self.tokenizer)
        except Exception as exc:
            raise ValueError(f"Cannot build the heading chunker: {exc}") from exc

    @property
    def strategy(self) -> str:
        """The strategy name, ``"heading"``."""
        return "heading"

    def _split(self, document: Document) -> list[Chunk]:
        text = document.text
        fallback_name = f"{self.strategy}:{self.fallback.strategy}"
        offsets = sorted(
            {
                h.char_start
                for h in document.heading_outline
                if 0 <= h.char_start < len(text)
            }
        )
        if not offsets:
            spans = self.fallback.spans(text)
            if not spans and text.strip():
                raise self._error(document, 0, "no chunks for non-empty text")
            return build_marked_chunks(
                document, [(a, b, fallback_name) for a, b in spans]
            )

        top_offsets = sorted(
            {
                h.char_start
                for h in document.heading_outline
                if h.level <= self.split_level and 0 <= h.char_start < len(text)
            }
            | {0}
        )
        deep_offsets = [o for o in offsets if o not in set(top_offsets)]
        pieces: list[tuple[int, int, str | None]] = []
        for start, end in zip(top_offsets, [*top_offsets[1:], len(text)], strict=True):
            pieces.extend(self._section(text, start, end, deep_offsets, fallback_name))
        return build_marked_chunks(document, pieces)

    def _section(
        self,
        text: str,
        start: int,
        end: int,
        deep_offsets: list[int],
        fallback_name: str,
    ) -> list[tuple[int, int, str | None]]:
        """Return the chunk pieces of one top section."""
        if not text[start:end].strip():
            return []
        if self._tokens(text, start, end) <= self.chunk_size:
            return [self._trim(text, start, end, None)]
        cuts = [start, *(o for o in deep_offsets if start < o < end), end]
        parts = list(zip(cuts, cuts[1:], strict=False))
        pieces: list[tuple[int, int, str | None]] = []
        group_start, group_end, group_tokens = parts[0][0], parts[0][0], 0
        for a, b in parts:
            size = self._tokens(text, a, b)
            if size > self.chunk_size:
                if group_end > group_start:
                    pieces.append(self._trim(text, group_start, group_end, None))
                pieces.extend(
                    self._trim(text, x, y, fallback_name)
                    for x, y in shifted_spans(self.fallback.spans, text, a, b)
                )
                group_start, group_end, group_tokens = b, b, 0
            elif group_end > group_start and group_tokens + size > self.chunk_size:
                pieces.append(self._trim(text, group_start, group_end, None))
                group_start, group_end, group_tokens = a, b, size
            else:
                if group_end == group_start:
                    group_start = a
                group_end = b
                group_tokens += size
        if group_end > group_start:
            pieces.append(self._trim(text, group_start, group_end, None))
        return [p for p in pieces if p[1] > p[0]]

    def _tokens(self, text: str, start: int, end: int) -> int:
        return self._counter.count_tokens(text[start:end])

    @staticmethod
    def _trim(
        text: str, start: int, end: int, name: str | None
    ) -> tuple[int, int, str | None]:
        """Drop the blank text at the end of a piece."""
        return start, start + len(text[start:end].rstrip()), name
