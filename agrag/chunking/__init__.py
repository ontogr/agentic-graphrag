"""Chunking: how a Document becomes Chunks.

A ``Chunker`` splits one document. A ``Chunking`` holds the rules that pick a chunker
for each document, and ``DEFAULT_CHUNKING`` is the preset that ``Graph`` uses.
"""

from agrag.chunking.base import Chunker, ChunkingError
from agrag.chunking.docling import DoclingChunker
from agrag.chunking.recursive import RecursiveChunker, SplitLevel
from agrag.chunking.rules import DEFAULT_CHUNKING, Chunking, ChunkingRule, RuleMatch
from agrag.chunking.sentence import SentenceChunker
from agrag.chunking.token import TokenChunker


__all__ = [
    "DEFAULT_CHUNKING",
    "Chunker",
    "Chunking",
    "ChunkingError",
    "ChunkingRule",
    "DoclingChunker",
    "RecursiveChunker",
    "RuleMatch",
    "SentenceChunker",
    "SplitLevel",
    "TokenChunker",
]
