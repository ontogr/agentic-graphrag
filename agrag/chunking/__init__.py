"""Chunking: how a Document becomes Chunks.

``Chunker`` packs the sections of a document into chunks. ``Graph`` takes one.
"""

from agrag.chunking.chunker import DEFAULT_TOKENIZER, Chunker, ChunkingError


__all__ = ["DEFAULT_TOKENIZER", "Chunker", "ChunkingError"]
