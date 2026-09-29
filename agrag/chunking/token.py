"""The token strategy: fixed-size windows of tokens, with optional overlap."""

from typing import Any

from chonkie import TokenChunker as ChonkieTokenChunker
from pydantic import Field, model_validator

from agrag.chunking.base import DEFAULT_TOKENIZER, SpanChunker


class TokenChunker(SpanChunker):
    """Cuts the text into windows of ``chunk_size`` tokens.

    Neighbouring chunks overlap when ``chunk_overlap`` is set, and each chunk keeps
    its exact span in the document.

    Attributes:
        chunk_size: The window size, counted with ``tokenizer``.
        chunk_overlap: The overlap between neighbours. An int counts tokens. A float
            from 0 up to 1 is a share of ``chunk_size``.
        tokenizer: The tokenizer that counts size. ``"character"`` counts characters.
    """

    chunk_size: int = Field(default=256, gt=0)
    chunk_overlap: int | float = Field(default=0, ge=0)
    tokenizer: str = DEFAULT_TOKENIZER

    @model_validator(mode="after")
    def _overlap_below_size(self) -> "TokenChunker":
        """Reject an overlap that is not smaller than the window."""
        limit = 1 if isinstance(self.chunk_overlap, float) else self.chunk_size
        if self.chunk_overlap >= limit:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size "
                "(or below 1 when it is a float)"
            )
        return self

    @property
    def strategy(self) -> str:
        """The strategy name, ``"token"``."""
        return "token"

    def _build_engine(self) -> Any:
        return ChonkieTokenChunker(
            tokenizer=self.tokenizer,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
