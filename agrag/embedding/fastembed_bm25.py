"""BM25 sparse embedder backed by FastEmbed."""

import asyncio
from collections.abc import Sequence
from typing import Any

from agrag.embedding.errors import EmbeddingMissingExtraError
from agrag.embedding.sparse_base import SparseEmbedder, SparseVector


DEFAULT_BM25_MODEL = "Qdrant/bm25"


class FastEmbedBM25Embedder(SparseEmbedder):
    """A sparse BM25 embedder built on FastEmbed.

    The model loads lazily on first ``embed``, so constructing the embedder
    does not download weights. Each blocking call into FastEmbed runs in a
    worker thread, keeping the event loop free. FastEmbed ships with the
    ``qdrant`` extra, so a clean install without that extra raises
    ``EmbeddingMissingExtraError`` rather than ``ImportError``.
    """

    def __init__(self, *, model: str | None = None) -> None:
        """Build the embedder.

        Args:
            model: The FastEmbed BM25 model name. Defaults to FastEmbed's
                built-in BM25 model.
        """
        self._model_name = model
        self._model: Any = None
        self._model_lock = asyncio.Lock()

    @property
    def model(self) -> str:
        """The configured model name, or the FastEmbed default when unset."""
        return self._model_name or DEFAULT_BM25_MODEL

    def _build_model(self) -> Any:
        """Construct a new FastEmbed sparse embedding model instance.

        Returns:
            The loaded sparse embedding model.

        Raises:
            EmbeddingMissingExtraError: fastembed is not installed.
        """
        try:
            # Lazy import: a clean install must raise
            # EmbeddingMissingExtraError, not ImportError, when fastembed
            # is absent. fastembed is bundled into the `qdrant` extra.
            from fastembed import SparseTextEmbedding  # noqa: PLC0415
        except ImportError as exc:
            raise EmbeddingMissingExtraError("qdrant") from exc
        model_name = self._model_name or DEFAULT_BM25_MODEL
        return SparseTextEmbedding(model_name=model_name)

    async def _ensure_model_async(self) -> Any:
        """Load the model once and cache it, safely under concurrent calls.

        Only the first caller through the lock builds the model, in a worker
        thread so the event loop stays free; later callers reuse the cached
        instance instead of each loading their own copy. A failed build
        leaves ``self._model`` unset, so the next call retries instead of
        caching the failure.

        Returns:
            The loaded sparse embedding model.

        Raises:
            EmbeddingMissingExtraError: fastembed is not installed.
        """
        if self._model is not None:
            return self._model
        async with self._model_lock:
            if self._model is None:
                self._model = await asyncio.to_thread(self._build_model)
        return self._model

    async def embed(self, texts: Sequence[str]) -> list[SparseVector]:
        """Embed a batch of documents into BM25 sparse vectors.

        Applies FastEmbed's document-side term-frequency and length
        normalization weighting. Use ``query_embed`` for search queries.

        Args:
            texts: The document texts to embed, in order.

        Returns:
            One sparse vector per input text, in the same order.
        """
        model = await self._ensure_model_async()

        def _encode() -> list[Any]:
            return list(model.embed(list(texts)))

        raw = await asyncio.to_thread(_encode)
        return self._to_sparse_vectors(raw)

    async def query_embed(self, texts: Sequence[str]) -> list[SparseVector]:
        """Embed a batch of search queries into BM25 sparse vectors.

        Uses FastEmbed's ``query_embed``, which assigns each unique query
        term a uniform weight of ``1.0`` rather than the document-side
        term-frequency and length-normalization weighting ``embed`` applies;
        IDF weighting is applied separately by the sparse index's
        ``Modifier.IDF`` at query time.

        Args:
            texts: The query texts to embed, in order.

        Returns:
            One sparse vector per input text, in the same order.
        """
        model = await self._ensure_model_async()

        def _encode() -> list[Any]:
            return list(model.query_embed(list(texts)))

        raw = await asyncio.to_thread(_encode)
        return self._to_sparse_vectors(raw)

    @staticmethod
    def _to_sparse_vectors(raw: list[Any]) -> list[SparseVector]:
        """Convert FastEmbed's sparse embedding objects to ``SparseVector``.

        Args:
            raw: FastEmbed ``SparseEmbedding`` objects.

        Returns:
            One ``SparseVector`` per input, in the same order.
        """
        return [
            SparseVector(
                indices=[int(i) for i in sv.indices],
                values=[float(v) for v in sv.values],
            )
            for sv in raw
        ]
