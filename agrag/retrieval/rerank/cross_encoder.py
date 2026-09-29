"""Cross-encoder reranker using sentence-transformers."""

import asyncio
from typing import Any, cast

from opentelemetry.trace import Tracer

from agrag.common.data_models.search_result import SearchResult
from agrag.observability import get_tracer, record_swallowed_exception
from agrag.retrieval.tracing import record_results, result_text


_MODEL_CACHE: dict[str, Any] = {}

# One asyncio lock per model name; created inside _load_cross_encoder, which
# always runs on the event loop, so the dict itself needs no thread safety.
_MODEL_LOAD_LOCKS: dict[str, asyncio.Lock] = {}


def _build_cross_encoder(model: str) -> Any:
    """Construct a new CrossEncoder instance for the given model name."""
    from sentence_transformers import CrossEncoder  # noqa: PLC0415

    return CrossEncoder(model)


async def _load_cross_encoder(model: str, *, tracer: Tracer | None = None) -> Any:
    """Return a cached CrossEncoder instance, loading it once per model name.

    A CrossEncoder holds real weights in memory; reloading it fresh on
    every search() call is cheap enough to ignore at this model's size,
    but becomes the dominant cost for a larger one configured via
    RetrievalSettings.cross_encoder_model. Cached per name so switching
    models doesn't need a process restart, and doesn't evict whatever was
    already loaded for a different name. Construction runs via
    asyncio.to_thread, same as predict(), since it can do real
    filesystem or network work (downloading weights) that would
    otherwise block the event loop on a cache miss. A cache miss opens a
    model-load span under the per-model lock, so concurrent first callers
    produce one span.

    Args:
        model: The sentence-transformers CrossEncoder model name/path.
        tracer: Opens the model-load span. None opens no recorded span.

    Returns:
        The cached CrossEncoder instance for the model name.
    """
    lock = _MODEL_LOAD_LOCKS.setdefault(model, asyncio.Lock())
    async with lock:
        if model not in _MODEL_CACHE:
            with get_tracer(tracer).start_as_current_span(
                "agrag.retrieval.rerank.model_load",
                attributes={"agrag.model": model},
            ):
                _MODEL_CACHE[model] = await asyncio.to_thread(
                    _build_cross_encoder, model
                )
    return _MODEL_CACHE[model]


async def cross_encoder_rerank(
    query: str,
    results: list[SearchResult],
    *,
    model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    min_score: float | None = None,
    tracer: Tracer | None = None,
) -> list[SearchResult]:
    """Rerank results using a cross-encoder model.

    Requires the ``embed-local`` extra (sentence-transformers). Scores
    (query, text) pairs and reorders by relevance. Drops results scoring
    below min_score when set. The model is cached per name (see
    _load_cross_encoder), and the blocking predict() call runs via
    asyncio.to_thread so a larger configured model cannot stall the event
    loop for other concurrent search() calls. Concurrent first loads of the
    same model share one in-flight construction behind a per-model lock, so
    only one instance (and one download) occurs.

    Without the extra, the results are returned unchanged: the span records
    the ImportError and sets ``agrag.skipped``, and its status stays UNSET.

    Args:
        query: The natural-language query text.
        results: The fused results to rerank.
        model: The sentence-transformers CrossEncoder model name/path.
            Callers pass RetrievalSettings.cross_encoder_model.
        min_score: Optional minimum score threshold. Results below this
            are dropped.
        tracer: Opens the rerank spans. None opens no recorded span.

    Returns:
        Results reranked by cross-encoder score, descending.
    """
    if not results:
        return []

    attributes: dict[str, str | int | float] = {
        "agrag.model": model,
        "agrag.input_count": len(results),
    }
    if min_score is not None:
        attributes["agrag.min_score"] = min_score

    with get_tracer(tracer).start_as_current_span(
        "agrag.retrieval.rerank.cross_encoder", attributes=attributes
    ) as span:
        try:
            cross_encoder = await _load_cross_encoder(model, tracer=tracer)
        except ImportError as exc:
            # Without the extra, return results unchanged.
            record_swallowed_exception(exc)
            if span.is_recording():
                span.set_attribute("agrag.skipped", True)
            record_results(span, results)
            return results

        pairs = [(query, result_text(result)) for result in results]
        scores = await asyncio.to_thread(cross_encoder.predict, cast(list[Any], pairs))

        reranked: list[SearchResult] = []
        for result, score in zip(results, scores, strict=True):
            score_val = float(score)
            if min_score is not None and score_val < min_score:
                continue
            reranked.append(
                SearchResult(
                    item=result.item,
                    score=score_val,
                    method="cross_encoder",
                    parent=result.parent,
                )
            )

        reranked.sort(key=lambda r: r.score, reverse=True)
        record_results(span, reranked)
        return reranked
