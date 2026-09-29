"""Docling adapters for the chunker: the token counter and the table serializer.

This module imports docling at load time, so ``agrag.chunking.docling`` imports it
only when a docling document is chunked. That keeps the ``docling`` extra optional.
"""

from collections.abc import Callable
from typing import Any

from chonkie.tokenizer import AutoTokenizer
from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer,
    ChunkingSerializerProvider,
)
from docling_core.transforms.chunker.tokenizer.base import BaseTokenizer
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.transforms.serializer.base import BaseDocSerializer
from docling_core.transforms.serializer.markdown import MarkdownTableSerializer
from docling_core.types.doc import DoclingDocument
from pydantic import PrivateAttr


class _AgragTokenizer(BaseTokenizer):
    """Docling tokenizer backed by the tokenizer the text strategies use."""

    name: str
    max_tokens: int
    _counter: Any = PrivateAttr(default=None)

    def model_post_init(self, context: Any, /) -> None:
        """Load the tokenizer once."""
        self._counter = AutoTokenizer(self.name)

    def count_tokens(self, text: str) -> int:
        """Return the number of tokens in the text."""
        return self._counter.count_tokens(text)

    def get_max_tokens(self) -> int:
        """Return the token budget of a chunk."""
        return self.max_tokens

    def get_tokenizer(self) -> Callable[[str], int]:
        """Return the counting function, which docling's splitter calls."""
        return self.count_tokens


def build_tokenizer(name: str, max_tokens: int) -> BaseTokenizer:
    """Build the tokenizer that docling's chunker counts with.

    Args:
        name: A tokenizer name. A name with a slash is a Hugging Face model id.
        max_tokens: The token budget of a chunk.

    Returns:
        The docling tokenizer.
    """
    if "/" in name:
        return HuggingFaceTokenizer.from_pretrained(name, max_tokens=max_tokens)
    return _AgragTokenizer(name=name, max_tokens=max_tokens)


class MarkdownTableProvider(ChunkingSerializerProvider):
    """Serializes tables as Markdown in chunk text."""

    def get_serializer(self, doc: DoclingDocument) -> BaseDocSerializer:
        """Return a chunking serializer with a Markdown table serializer."""
        return ChunkingDocSerializer(
            doc=doc, table_serializer=MarkdownTableSerializer()
        )
