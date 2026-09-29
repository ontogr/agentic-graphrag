"""The sentence strategy: whole sentences packed up to a token budget."""

from typing import Any

from chonkie import SentenceChunker as ChonkieSentenceChunker
from pydantic import Field, model_validator

from agrag.chunking.base import DEFAULT_TOKENIZER, SpanChunker


class SentenceChunker(SpanChunker):
    """Packs whole sentences into chunks of at most ``chunk_size`` tokens.

    A single sentence longer than ``chunk_size`` stays whole, so a chunk can be
    larger than the budget when the text has a very long sentence.

    Attributes:
        chunk_size: The largest chunk size, counted with ``tokenizer``.
        chunk_overlap: The overlap between neighbours, in tokens. Each chunk keeps
            its exact span in the document.
        min_sentences_per_chunk: The fewest sentences in a chunk.
        min_characters_per_sentence: The shortest text that counts as a sentence.
        tokenizer: The tokenizer that counts size. ``"character"`` counts characters.
    """

    chunk_size: int = Field(default=256, gt=0)
    chunk_overlap: int = Field(default=0, ge=0)
    min_sentences_per_chunk: int = Field(default=1, gt=0)
    min_characters_per_sentence: int = Field(default=12, gt=0)
    tokenizer: str = DEFAULT_TOKENIZER

    @model_validator(mode="after")
    def _overlap_below_size(self) -> "SentenceChunker":
        """Reject an overlap that is not smaller than the budget."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self

    @property
    def strategy(self) -> str:
        """The strategy name, ``"sentence"``."""
        return "sentence"

    def _build_engine(self) -> Any:
        return ChonkieSentenceChunker(
            tokenizer=self.tokenizer,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            min_sentences_per_chunk=self.min_sentences_per_chunk,
            min_characters_per_sentence=self.min_characters_per_sentence,
        )
