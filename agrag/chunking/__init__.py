"""Chunking helpers for the ingestion layer.

This module isolates the chonkie dependency to one import site, so the rest of the
codebase (and tests) can build a chunker without importing chonkie directly.
"""

from chonkie import RecursiveChunker


def default_chunker(chunk_size: int = 1024) -> RecursiveChunker:
    """Build the default text chunker.

    Args:
        chunk_size: The maximum number of characters per chunk.

    Returns:
        A character-based recursive chunker.
    """
    return RecursiveChunker(
        chunk_size=chunk_size, tokenizer="character", min_characters_per_chunk=24
    )


__all__ = ["default_chunker", "RecursiveChunker"]
