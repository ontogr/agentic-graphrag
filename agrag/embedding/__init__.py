"""Text embedding: turn strings into dense vectors."""

from agrag.embedding.base import Embedder
from agrag.embedding.fastembed_bm25 import FastEmbedBM25Embedder
from agrag.embedding.sentence_transformers import SentenceTransformerEmbedder
from agrag.embedding.settings import EmbeddingSettings
from agrag.embedding.sparse_base import SparseEmbedder, SparseVector


def build_embedder(value: str | Embedder) -> Embedder:
    """Build an embedder from a model name, or return an embedder unchanged.

    Args:
        value: A sentence-transformers model name, such as
            ``"ibm-granite/granite-embedding-small-english-r2"`` (the default
            model), or an already-constructed ``Embedder`` for full control
            over device, batching, or caching.

    Returns:
        A ready-to-use embedder.
    """
    if isinstance(value, Embedder):
        return value
    return SentenceTransformerEmbedder(settings=EmbeddingSettings(model=value))


__all__ = [
    "Embedder",
    "EmbeddingSettings",
    "FastEmbedBM25Embedder",
    "SentenceTransformerEmbedder",
    "SparseEmbedder",
    "SparseVector",
    "build_embedder",
]
