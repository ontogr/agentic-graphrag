"""Opt-in chunkers that need a package extra: semantic, neural and code."""

from abc import abstractmethod
from bisect import bisect_left
from typing import Any

from pydantic import Field

from agrag.chunking.base import (
    DEFAULT_TOKENIZER,
    Chunker,
    ChunkerMissingExtraError,
    SpanChunker,
)


def byte_spans_to_char_spans(
    text: str, spans: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    """Convert UTF-8 byte spans of ``text`` to character spans.

    Args:
        text: The text the byte offsets index once encoded as UTF-8.
        spans: Half-open byte spans.

    Returns:
        The same spans as character offsets. ASCII text returns the spans as given.
    """
    if text.isascii():
        return list(spans)
    boundaries = [0]
    total = 0
    for char in text:
        total += len(char.encode("utf-8"))
        boundaries.append(total)
    return [(bisect_left(boundaries, a), bisect_left(boundaries, b)) for a, b in spans]


class _ExtraSpanChunker(SpanChunker):
    """A span chunker whose engine needs a package extra.

    The engine is built on the first ``spans()`` call, so a chunker can be built,
    printed and hashed without the extra. A missing package raises
    ``ChunkerMissingExtraError`` at that first call.
    """

    def model_post_init(self, context: Any, /) -> None:
        """Compute the fingerprint only, so the extra is not needed to build."""
        Chunker.model_post_init(self, context)

    def spans(self, text: str) -> list[tuple[int, int]]:
        """Return the character spans this strategy cuts text into.

        Raises:
            ChunkerMissingExtraError: The package extra is not installed.
        """
        if self._engine is None:
            try:
                self._engine = self._build_engine()
            except ImportError as exc:
                raise ChunkerMissingExtraError(self.strategy, self._extra_name) from exc
        return super().spans(text)

    @property
    @abstractmethod
    def _extra_name(self) -> str:
        """The package extra that this chunker needs."""


class SemanticChunker(_ExtraSpanChunker):
    """Cuts where the meaning of neighbouring sentences changes.

    Needs the ``chunk-semantic`` extra. The chunker embeds sentences with a small
    static model and cuts where similarity drops below ``threshold``.

    Attributes:
        embedding_model: The model that embeds sentences. The first use downloads it.
        threshold: The similarity below which a new chunk starts, from 0 to 1.
        chunk_size: The largest chunk size, as chonkie's semantic chunker counts it.
        similarity_window: The number of sentences that a similarity looks across.
    """

    embedding_model: str = "minishlab/potion-base-32M"
    threshold: float = Field(default=0.8, gt=0, le=1)
    chunk_size: int = Field(default=256, gt=0)
    similarity_window: int = Field(default=3, gt=0)

    @property
    def strategy(self) -> str:
        """The strategy name, ``"semantic"``."""
        return "semantic"

    @property
    def _extra_name(self) -> str:
        return "chunk-semantic"

    def _build_engine(self) -> Any:
        from chonkie import SemanticChunker as ChonkieSemanticChunker  # noqa: PLC0415

        return ChonkieSemanticChunker(
            embedding_model=self.embedding_model,
            threshold=self.threshold,
            chunk_size=self.chunk_size,
            similarity_window=self.similarity_window,
        )


class NeuralChunker(_ExtraSpanChunker):
    """Cuts where a token classification model predicts a topic break.

    Needs the ``chunk-neural`` extra. The first use downloads the model.

    Attributes:
        model: The Hugging Face model id. ``None`` uses chonkie's default model.
        device_map: The device for the model, for example ``"cpu"`` or ``"auto"``.
        min_characters_per_chunk: The smallest chunk the splitter keeps apart.
    """

    model: str | None = None
    device_map: str = "cpu"
    min_characters_per_chunk: int = Field(default=10, gt=0)

    @property
    def strategy(self) -> str:
        """The strategy name, ``"neural"``."""
        return "neural"

    @property
    def _extra_name(self) -> str:
        return "chunk-neural"

    def _build_engine(self) -> Any:
        from chonkie import NeuralChunker as ChonkieNeuralChunker  # noqa: PLC0415

        options: dict[str, Any] = {}
        if self.model is not None:
            options["model"] = self.model
        return ChonkieNeuralChunker(
            device_map=self.device_map,
            min_characters_per_chunk=self.min_characters_per_chunk,
            **options,
        )


class CodeChunker(_ExtraSpanChunker):
    """Cuts source code along its syntax tree.

    Needs the ``chunk-code`` extra. The parser reports byte offsets, and this
    chunker converts them to character offsets, so chunk text equals the source
    slice for non-ASCII code too.

    Attributes:
        language: A tree-sitter language name, or ``"auto"`` to detect it.
        chunk_size: The largest chunk size, counted with ``tokenizer``.
        tokenizer: The tokenizer that counts size. ``"character"`` counts characters.
    """

    language: str = "auto"
    chunk_size: int = Field(default=256, gt=0)
    tokenizer: str = DEFAULT_TOKENIZER

    @property
    def strategy(self) -> str:
        """The strategy name, ``"code"``."""
        return "code"

    @property
    def _extra_name(self) -> str:
        return "chunk-code"

    def spans(self, text: str) -> list[tuple[int, int]]:
        """Return character spans, converted from the parser's byte spans."""
        return byte_spans_to_char_spans(text, super().spans(text))

    def _build_engine(self) -> Any:
        from chonkie import CodeChunker as ChonkieCodeChunker  # noqa: PLC0415

        return ChonkieCodeChunker(
            tokenizer=self.tokenizer,
            chunk_size=self.chunk_size,
            language=self.language,
        )
