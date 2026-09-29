"""Chunking: how a Document becomes Chunks.

A ``Chunker`` splits one document. A ``Chunking`` holds the rules that pick a chunker
for each document, and ``DEFAULT_CHUNKING`` is the preset that ``Graph`` uses.
"""

from agrag.chunking.base import Chunker, ChunkerMissingExtraError, ChunkingError
from agrag.chunking.docling import DoclingChunker
from agrag.chunking.extras import CodeChunker, NeuralChunker, SemanticChunker
from agrag.chunking.heading import HeadingChunker
from agrag.chunking.parent_child import ParentChildChunker
from agrag.chunking.recursive import RecursiveChunker, SplitLevel
from agrag.chunking.rules import DEFAULT_CHUNKING, Chunking, ChunkingRule, RuleMatch
from agrag.chunking.sentence import SentenceChunker
from agrag.chunking.token import TokenChunker
from agrag.chunking.turns import TurnWindowChunker


__all__ = [
    "DEFAULT_CHUNKING",
    "Chunker",
    "ChunkerMissingExtraError",
    "Chunking",
    "ChunkingError",
    "ChunkingRule",
    "CodeChunker",
    "DoclingChunker",
    "HeadingChunker",
    "NeuralChunker",
    "ParentChildChunker",
    "RecursiveChunker",
    "RuleMatch",
    "SemanticChunker",
    "SentenceChunker",
    "SplitLevel",
    "TokenChunker",
    "TurnWindowChunker",
]
