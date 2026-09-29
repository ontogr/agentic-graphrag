"""The turn-window strategy: whole chat turns packed to a token budget."""

from typing import Any

from chonkie.tokenizer import AutoTokenizer
from pydantic import Field, PrivateAttr, SerializeAsAny

from agrag.chunking._text import build_marked_chunks, shifted_spans
from agrag.chunking.base import DEFAULT_TOKENIZER, Chunker, SpanChunker
from agrag.chunking.recursive import RecursiveChunker
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document


class TurnWindowChunker(Chunker):
    """Packs whole chat turns into windows of at most ``chunk_size`` tokens.

    The chunker reads ``Document.turns``. A window holds one or more whole turns, and
    a chunk boundary never falls inside a turn. Tokens are counted for each turn
    alone, so the separators between turns are not part of the count. Text before
    the first turn joins the first window, and text after a turn joins the window
    that holds that turn.

    A turn above the budget is split by ``fallback``, and its chunks have the
    chunker name ``turn-window:<fallback strategy>``. A document without turns is
    split by ``fallback`` as a whole and its chunks have the same name.

    Attributes:
        chunk_size: The most tokens in a window, counted with ``tokenizer``.
        turn_overlap: The number of turns that a window repeats from the window
            before it. A window always moves on by at least one turn.
        tokenizer: The tokenizer that counts size. ``"character"`` counts characters.
        fallback: The chunker for a turn above the budget and for a document without
            turns.
    """

    chunk_size: int = Field(default=256, gt=0)
    turn_overlap: int = Field(default=0, ge=0)
    tokenizer: str = DEFAULT_TOKENIZER
    fallback: SerializeAsAny[SpanChunker] = Field(default_factory=RecursiveChunker)

    _counter: Any = PrivateAttr(default=None)

    def model_post_init(self, context: Any, /) -> None:
        """Load the tokenizer once, so a bad name fails at construction."""
        super().model_post_init(context)
        try:
            self._counter = AutoTokenizer(self.tokenizer)
        except Exception as exc:
            raise ValueError(f"Cannot build the turn-window chunker: {exc}") from exc

    @property
    def strategy(self) -> str:
        """The strategy name, ``"turn-window"``."""
        return "turn-window"

    def _split(self, document: Document) -> list[Chunk]:
        text = document.text
        fallback_name = f"{self.strategy}:{self.fallback.strategy}"
        turns = document.turns
        if not turns:
            spans = self.fallback.spans(text)
            if not spans and text.strip():
                raise self._error(document, 0, "no chunks for non-empty text")
            return build_marked_chunks(
                document, [(a, b, fallback_name) for a, b in spans]
            )

        tokens = [
            self._counter.count_tokens(text[t.char_start : t.char_end]) for t in turns
        ]
        count = len(turns)

        def region_start(i: int) -> int:
            """Chunk start for turn i: text before the first turn joins turn 0."""
            if i == 0 and text[: turns[0].char_start].strip():
                return 0
            return turns[i].char_start

        def region_end(j: int) -> int:
            """Chunk end for turn j: non-blank text after the turn stays with it."""
            following = turns[j + 1].char_start if j + 1 < count else len(text)
            return (
                following
                if text[turns[j].char_end : following].strip()
                else turns[j].char_end
            )

        pieces: list[tuple[int, int, str | None]] = []
        i = 0
        while i < count:
            if tokens[i] > self.chunk_size:
                start, end = region_start(i), region_end(i)
                pieces.extend(
                    (a, b, fallback_name)
                    for a, b in shifted_spans(self.fallback.spans, text, start, end)
                )
                i += 1
                continue
            j = i
            total = tokens[i]
            while (
                j + 1 < count
                and tokens[j + 1] <= self.chunk_size
                and total + tokens[j + 1] <= self.chunk_size
            ):
                j += 1
                total += tokens[j]
            pieces.append((region_start(i), region_end(j), None))
            reached_end = j + 1 >= count
            if reached_end or tokens[j + 1] > self.chunk_size:
                i = j + 1
            else:
                i = max(j - self.turn_overlap + 1, i + 1)
        return build_marked_chunks(document, pieces)
