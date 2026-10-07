"""Dense embedder backed by FastEmbed and ONNX Runtime."""

import asyncio
import threading
from collections.abc import Sequence
from typing import Any, cast

import numpy as np
from opentelemetry.trace import SpanKind, Tracer

from agrag.embedding.base import Embedder, EmbeddingCache, NullEmbeddingCache
from agrag.embedding.settings import EmbeddingSettings
from agrag.observability import get_tracer


GRANITE_MODEL = "ibm-granite/granite-embedding-small-english-r2"

_GRANITE_ONNX_REPO = "onnx-community/granite-embedding-small-english-r2-ONNX"
_GRANITE_DIMENSIONS = 384
_registration_lock = threading.Lock()


def _register_granite(text_embedding: Any) -> None:
    """Register the granite model with FastEmbed when the installed release lacks it.

    Args:
        text_embedding: The ``fastembed.TextEmbedding`` class.
    """
    # FastEmbed added this model in qdrant/fastembed#702, after its 0.8.1 release.
    # Until a release lists it, register the same ONNX export here. Delete this
    # function and its call once the minimum fastembed version lists the model.
    from fastembed.common.model_description import (  # noqa: PLC0415
        ModelSource,
        PoolingType,
    )

    with _registration_lock:
        supported = {m["model"] for m in text_embedding.list_supported_models()}
        if GRANITE_MODEL in supported:
            return
        # The embedder applies ``EmbeddingSettings.normalize`` itself, so the model
        # returns raw CLS vectors, as FastEmbed's own entry does.
        text_embedding.add_custom_model(
            model=GRANITE_MODEL,
            pooling=PoolingType.CLS,
            normalization=False,
            sources=ModelSource(hf=_GRANITE_ONNX_REPO),
            dim=_GRANITE_DIMENSIONS,
            model_file="onnx/model.onnx",
            additional_files=["onnx/model.onnx_data"],
        )


class FastEmbedEmbedder(Embedder):
    """A dense embedder built on FastEmbed, which runs ONNX models on the CPU.

    The model loads lazily on first ``embed``, so constructing the embedder does
    not download weights. Each blocking call into FastEmbed runs in a worker
    thread, which keeps the event loop free for other work while a large batch
    encodes.
    """

    def __init__(
        self,
        *,
        settings: EmbeddingSettings | None = None,
        cache: EmbeddingCache | None = None,
        model: object | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        """Build the embedder.

        Args:
            settings: Embedder configuration. Defaults to ``EmbeddingSettings()``.
                FastEmbed ignores ``device``.
            cache: An optional content-addressed cache. Defaults to a no-op cache.
            model: A pre-built FastEmbed ``TextEmbedding``, for tests. When set,
                ``embed`` calls this object instead of building one.
            tracer: Opens every span this embedder's methods produce.
        """
        self._settings = settings or EmbeddingSettings()
        self._cache = cache or NullEmbeddingCache()
        self._model = model
        self._tracer = get_tracer(tracer)
        self._model_lock = asyncio.Lock()

    @property
    def model(self) -> str:
        """The configured model name."""
        return self._settings.model

    async def dimensions(self) -> int:
        """Return the dimension the loaded model produces.

        Calling this loads the model the first time, through the same locked
        worker-thread path ``embed`` uses, so it is safe to call concurrently
        with ``embed``.
        """
        model = await self._ensure_model_async()
        return cast(int, model.embedding_size)

    def _build_model(self) -> Any:
        """Construct a new FastEmbed model instance.

        Returns:
            The loaded ``TextEmbedding`` model.
        """
        # Import here: onnxruntime is slow to import, and a caller that never
        # embeds should not pay for it.
        from fastembed import TextEmbedding  # noqa: PLC0415

        if self._settings.model == GRANITE_MODEL:
            _register_granite(TextEmbedding)
        return TextEmbedding(
            model_name=self._settings.model, cache_dir=self._settings.cache_folder
        )

    async def _ensure_model_async(self) -> Any:
        """Load the model once, safely under concurrent calls.

        Only the first caller through the lock builds the model, in a worker thread
        so the event loop stays free. Later callers reuse it. A failed build leaves
        the model unset, so the next call retries.

        Returns:
            The loaded model.
        """
        if self._model is not None:
            return self._model
        async with self._model_lock:
            if self._model is None:
                with self._tracer.start_as_current_span(
                    "agrag.embedding.model_load",
                    kind=SpanKind.INTERNAL,
                    attributes={"agrag.model": self.model},
                ):
                    self._model = await asyncio.to_thread(self._build_model)
        return self._model

    def _encode(self, model: Any, texts: list[str]) -> list[list[float]]:
        """Encode texts, normalizing each vector when the settings ask for it.

        Args:
            model: The loaded FastEmbed model.
            texts: The texts to encode.

        Returns:
            One vector per text. A zero vector stays zero.
        """
        vectors: list[list[float]] = []
        for raw in model.embed(texts, batch_size=self._settings.batch_size):
            vector = np.asarray(raw)
            norm = np.linalg.norm(vector)
            if self._settings.normalize and norm > 0:
                vector = vector / norm
            vectors.append(vector.tolist())
        return vectors

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
            model = await self._ensure_model_async()
            with self._tracer.start_as_current_span(
                "agrag.embedding.encode",
                kind=SpanKind.INTERNAL,
                attributes={
                    "agrag.text_count": len(misses),
                    "agrag.cache_hit_count": len(texts) - len(misses),
                },
            ):
                new_vectors = await asyncio.to_thread(
                    self._encode, model, [texts[i] for i in misses]
                )
            for i, vector in zip(misses, new_vectors, strict=True):
                cached[i] = vector
                await self._cache.set(
                    text=texts[i], model=self.model, normalize=normalize, vector=vector
                )
        return cast(list[list[float]], cached)
