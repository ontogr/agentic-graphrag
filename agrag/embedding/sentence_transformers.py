"""Sentence-transformers embedder implementation."""

import asyncio
from collections.abc import Sequence
from typing import Any, cast

from agrag.embedding.base import Embedder, EmbeddingCache, NullEmbeddingCache
from agrag.embedding.errors import EmbeddingMissingExtraError
from agrag.embedding.settings import EmbeddingSettings


class SentenceTransformerEmbedder(Embedder):
    """An embedder backed by sentence-transformers.

    The model loads lazily on first ``embed``, so constructing the embedder
    does not touch the GPU or download weights. Every blocking call into the
    model runs in a worker thread (``asyncio.to_thread``), so the event loop
    stays free for other work while a large batch encodes.
    """

    def __init__(
        self,
        *,
        settings: EmbeddingSettings | None = None,
        cache: EmbeddingCache | None = None,
        model: object | None = None,
    ) -> None:
        """Build the embedder.

        Args:
            settings: Embedder configuration. Defaults to ``EmbeddingSettings()``.
            cache: An optional content-addressed cache. Defaults to a no-op cache.
            model: A pre-built sentence-transformers model, for tests. When set,
                ``__init__`` imports nothing and ``embed`` calls this object
                directly instead of building one.
        """
        self._settings = settings or EmbeddingSettings()
        self._cache = cache or NullEmbeddingCache()
        self._model = model

    @property
    def model(self) -> str:
        """The configured model name."""
        return self._settings.model

    @property
    def dimensions(self) -> int:
        """The dimension the loaded model produces.

        Accessing this loads the model the first time.

        Raises:
            EmbeddingMissingExtraError: sentence-transformers is not installed.
        """
        return self._model_dimension(self._ensure_model())

    @staticmethod
    def _model_dimension(model: Any) -> int:
        """Read the embedding dimension, across sentence-transformers versions.

        sentence-transformers renamed ``get_sentence_embedding_dimension`` to
        ``get_embedding_dimension`` in 6.0; support both so the embedder works
        before and after the rename.

        Args:
            model: A loaded sentence-transformers model.

        Returns:
            The embedding dimension.
        """
        if hasattr(model, "get_embedding_dimension"):
            return model.get_embedding_dimension()
        return model.get_sentence_embedding_dimension()

    def _ensure_model(self) -> Any:
        """Load the model once and cache it.

        Returns:
            The loaded model object.

        Raises:
            EmbeddingMissingExtraError: sentence-transformers is not installed.
        """
        if self._model is None:
            try:
                # Lazy import: a clean install must raise EmbeddingMissingExtraError,
                # not ImportError, when sentence-transformers is absent.
                from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            except ImportError as exc:
                raise EmbeddingMissingExtraError("embed-local") from exc
            self._model = SentenceTransformer(
                self._settings.model,
                device=self._settings.device,
                cache_folder=self._settings.cache_folder,
            )
        return self._model

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of texts, using the cache where possible.

        Args:
            texts: The texts to embed, in order.

        Returns:
            One vector per input text, in the same order.
        """
        normalize = self._settings.normalize
        cached = [
            await self._cache.get(text=t, model=self.model, normalize=normalize)
            for t in texts
        ]
        misses = [i for i, v in enumerate(cached) if v is None]
        if misses:
            model = await asyncio.to_thread(self._ensure_model)
            new_vectors = await asyncio.to_thread(
                model.encode,
                [texts[i] for i in misses],
                batch_size=self._settings.batch_size,
                normalize_embeddings=normalize,
            )
            for i, vector in zip(misses, new_vectors, strict=True):
                vector_list = list(vector.tolist())
                cached[i] = vector_list
                await self._cache.set(
                    text=texts[i],
                    model=self.model,
                    normalize=normalize,
                    vector=vector_list,
                )
        return cast(list[list[float]], cached)
