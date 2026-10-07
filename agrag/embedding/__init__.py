"""Text embedding: turn strings into dense vectors."""

from opentelemetry.trace import Tracer

from agrag.embedding.base import Embedder
from agrag.embedding.fastembed_bm25 import FastEmbedBM25Embedder
from agrag.embedding.sentence_transformers import SentenceTransformerEmbedder
from agrag.embedding.settings import EmbeddingSettings
from agrag.embedding.sparse_base import SparseEmbedder, SparseVector


def build_embedder(value: str | Embedder, *, tracer: Tracer | None = None) -> Embedder:
    """Build an embedder from a model name, or return an embedder unchanged.

    Args:
        value: A sentence-transformers model name, such as
            ``"ibm-granite/granite-embedding-small-english-r2"`` (the default
            model), or an already-constructed ``Embedder`` for full control
            over device, batching, or caching.
        tracer: Passed to the newly-built embedder. Not valid together with
            an already-constructed ``value``. That instance's tracer, if
            any, was already fixed at its own construction.

    Returns:
        A ready-to-use embedder.

    Raises:
        ValueError: ``tracer`` is given together with an already-constructed
            ``value``.
    """
    if isinstance(value, Embedder):
        if tracer is not None:
            raise ValueError(
                "tracer has no effect on an already-constructed Embedder; "
                "pass it to the embedder's own constructor instead."
            )
        return value
    return SentenceTransformerEmbedder(
        settings=EmbeddingSettings(model=value), tracer=tracer
    )


__all__ = [
    "Embedder",
    "EmbeddingSettings",
    "FastEmbedBM25Embedder",
    "SentenceTransformerEmbedder",
    "SparseEmbedder",
    "SparseVector",
    "build_embedder",
]
