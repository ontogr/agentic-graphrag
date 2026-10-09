"""Chunking: how a Document becomes Chunks.

``Chunker`` packs the sections of a document into chunks. ``ChunkedDocument``
carries the chunks with where each chunk hangs. ``Graph`` takes one.
"""

from agrag.chunking.chunker import (
    DEFAULT_TOKENIZER,
    ChunkedDocument,
    Chunker,
    ChunkingError,
    ChunkPlacement,
)


__all__ = [
    "DEFAULT_TOKENIZER",
    "ChunkPlacement",
    "ChunkedDocument",
    "Chunker",
    "ChunkingError",
]
