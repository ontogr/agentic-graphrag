"""Cross-encoder reranker for fused evidence hits."""

import asyncio
import importlib.util
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, cast

from agrag.embedding.errors import EmbeddingMissingExtraError
from agrag.retrieval.settings import RetrievalSettings


_LOGGER = logging.getLogger(__name__)

Reranker = Callable[[str, Sequence[str]], Awaitable[Sequence[float]]]

# Cross-encoder models read roughly this much of each passage; longer text
# adds latency without changing the score.
MAX_PASSAGE_CHARS = 2000

_MODEL_CACHE: dict[str, Any] = {}

# One asyncio lock per model name; created inside _load_cross_encoder, which
# always runs on the event loop, so the dict itself needs no thread safety.
_MODEL_LOAD_LOCKS: dict[str, asyncio.Lock] = {}


def _build_cross_encoder(model: str) -> Any:
    """Construct a new CrossEncoder instance for the given model name."""
    try:
        from sentence_transformers import CrossEncoder  # noqa: PLC0415
    except ImportError as exc:
        raise EmbeddingMissingExtraError("embed-local") from exc

    return CrossEncoder(model)


async def _load_cross_encoder(model: str) -> Any:
    """Return a cached CrossEncoder instance, loading it once per model name.

    Construction runs via ``asyncio.to_thread`` because it can do real
    filesystem or network work (downloading weights) that would otherwise
    block the event loop on a cache miss. Concurrent first loads of the same
    model share one construction behind the per-model lock, so only one
    instance (and one download) occurs. Instances are cached per name so
    switching models does not evict whatever was already loaded for a
    different name.

    Args:
        model: The sentence-transformers CrossEncoder model name/path.

    Returns:
        The cached CrossEncoder instance for the model name.
    """
    lock = _MODEL_LOAD_LOCKS.setdefault(model, asyncio.Lock())
    async with lock:
        if model not in _MODEL_CACHE:
            _MODEL_CACHE[model] = await asyncio.to_thread(_build_cross_encoder, model)
    return _MODEL_CACHE[model]


class CrossEncoderReranker:
    """A reranker backed by a sentence-transformers CrossEncoder.

    Requires the ``embed-local`` extra. The model loads lazily on the first
    call, so constructing the reranker never downloads weights. Every
    blocking call into the model runs in a worker thread so the event loop
    stays free while a batch scores.

    A running worker thread cannot be cancelled, so a caller timeout
    (``asyncio.timeout`` around the ``await``) stops only the waiting, not
    the prediction. Each call therefore runs its prediction inside a
    semaphore and awaits it through ``asyncio.shield``: a timed-out caller
    gives up its wait while the prediction finishes, and the next call waits
    on the semaphore instead of stacking a second prediction.
    """

    def __init__(self, model: str) -> None:
        """Build the reranker.

        Args:
            model: The sentence-transformers CrossEncoder model name/path.

        Raises:
            EmbeddingMissingExtraError: The ``embed-local`` extra is not installed.
        """
        if importlib.util.find_spec("sentence_transformers") is None:
            raise EmbeddingMissingExtraError("embed-local")
        self._model_name = model
        self._predict_semaphore = asyncio.Semaphore(1)

    async def warm_up(self) -> None:
        """Load the model, so the first rerank call is not slow."""
        await _load_cross_encoder(self._model_name)

    async def __call__(self, query: str, texts: Sequence[str]) -> list[float]:
        """Score each passage against the query.

        Args:
            query: The natural-language query text.
            texts: The passage texts to score.

        Returns:
            One score per text, in the input order, higher is better.
        """
        pairs = [(query, text[:MAX_PASSAGE_CHARS]) for text in texts]

        async def predict() -> list[float]:
            cross_encoder = await _load_cross_encoder(self._model_name)
            async with self._predict_semaphore:
                scores = await asyncio.to_thread(
                    cross_encoder.predict, cast(list[Any], pairs)
                )
            return [float(score) for score in scores]

        task = asyncio.create_task(predict())
        # A caller whose timeout fires stops waiting through the shield, so
        # nobody may await this task's outcome; read the exception once so
        # asyncio does not log it as never retrieved.
        task.add_done_callback(lambda t: None if t.cancelled() else t.exception())
        return await asyncio.shield(task)


def reranker_from_settings(settings: RetrievalSettings) -> CrossEncoderReranker | None:
    """Build the reranker the retrieval settings configure, or ``None``.

    Never loads the model; loading happens on the first rerank call or an
    explicit ``warm_up``.

    Args:
        settings: The retrieval settings to read.

    Returns:
        A ``CrossEncoderReranker`` when rerank is enabled and
        sentence-transformers is installed. ``None`` when rerank is
        disabled, or when it is enabled but the ``embed-local`` extra is
        missing (one warning is logged; hybrid search runs without rerank).
    """
    if not settings.rerank_enabled:
        return None
    try:
        return CrossEncoderReranker(settings.cross_encoder_model)
    except EmbeddingMissingExtraError:
        _LOGGER.warning(
            "rerank is enabled but the embed-local extra is not installed; "
            "hybrid search runs without rerank"
        )
        return None
