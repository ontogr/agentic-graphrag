"""The recursive strategy: split on the coarsest delimiter that fits the budget."""

from typing import Any, Literal

from chonkie import RecursiveChunker as ChonkieRecursiveChunker
from chonkie import RecursiveLevel, RecursiveRules
from pydantic import BaseModel, ConfigDict, Field

from agrag.chunking.base import DEFAULT_TOKENIZER, SpanChunker


class SplitLevel(BaseModel):
    """One level of recursive split rules.

    Attributes:
        delimiters: The strings to split on at this level. ``None`` means none.
        whitespace: Whether to split on whitespace at this level.
        include_delim: Whether a delimiter stays with the previous piece, the next
            piece, or is dropped.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    delimiters: list[str] | None = None
    whitespace: bool = False
    include_delim: Literal["prev", "next"] | None = "prev"


class RecursiveChunker(SpanChunker):
    """Splits on paragraph, sentence and word boundaries, coarsest first.

    Attributes:
        chunk_size: The largest chunk size, counted with ``tokenizer``.
        tokenizer: The tokenizer that counts size. ``"character"`` counts characters.
        min_characters_per_chunk: The smallest piece the splitter keeps apart.
        levels: The split levels, coarsest first. ``None`` uses the default levels
            (paragraphs, sentences, punctuation, words, characters).
    """

    chunk_size: int = Field(default=256, gt=0)
    tokenizer: str = DEFAULT_TOKENIZER
    min_characters_per_chunk: int = Field(default=24, gt=0)
    levels: list[SplitLevel] | None = None

    @property
    def strategy(self) -> str:
        """The strategy name, ``"recursive"``."""
        return "recursive"

    def _build_engine(self) -> Any:
        rules = {}
        if self.levels is not None:
            rules["rules"] = RecursiveRules(
                levels=[
                    RecursiveLevel(
                        delimiters=level.delimiters,
                        whitespace=level.whitespace,
                        include_delim=level.include_delim,
                    )
                    for level in self.levels
                ]
            )
        return ChonkieRecursiveChunker(
            tokenizer=self.tokenizer,
            chunk_size=self.chunk_size,
            min_characters_per_chunk=self.min_characters_per_chunk,
            **rules,
        )
