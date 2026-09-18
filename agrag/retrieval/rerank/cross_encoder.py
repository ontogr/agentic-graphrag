"""Cross-encoder reranker using sentence-transformers."""

import asyncio
from typing import Any, cast

from agrag.common.data_models.community import Community
from agrag.common.data_models.search_result import SearchResult


_MODEL_CACHE: dict[str, Any] = {}

# One asyncio lock per model name; created inside _load_cross_encoder, which
# always runs on the event loop, so the dict itself needs no thread safety.
_MODEL_LOAD_LOCKS: dict[str, asyncio.Lock] = {}


def _build_cross_encoder(model: str) -> Any:
    """Construct a new CrossEncoder instance for the given model name."""
    from sentence_transformers import CrossEncoder  # noqa: PLC0415

    return CrossEncoder(model)


async def _load_cross_encoder(model: str) -> Any:
    """Return a cached CrossEncoder instance, loading it once per model name.

    A CrossEncoder holds real weights in memory; reloading it fresh on
    every search() call is cheap enough to ignore at this model's size,
    but becomes the dominant cost for a larger one configured via
    RetrievalSettings.cross_encoder_model. Cached per name so switching
    models doesn't need a process restart, and doesn't evict whatever was
    already loaded for a different name. Construction runs via
    asyncio.to_thread, same as predict(), since it can do real
    filesystem or network work (downloading weights) that would
    otherwise block the event loop on a cache miss.
    """
    lock = _MODEL_LOAD_LOCKS.setdefault(model, asyncio.Lock())
    async with lock:
        if model not in _MODEL_CACHE:
            _MODEL_CACHE[model] = await asyncio.to_thread(_build_cross_encoder, model)
    return _MODEL_CACHE[model]


async def cross_encoder_rerank(
    query: str,
    results: list[SearchResult],
    *,
    model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    min_score: float | None = None,
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

    Args:
        query: The natural-language query text.
        results: The fused results to rerank.
        model: The sentence-transformers CrossEncoder model name/path.
            Callers pass RetrievalSettings.cross_encoder_model.
        min_score: Optional minimum score threshold. Results below this
            are dropped.

    Returns:
        Results reranked by cross-encoder score, descending.
    """
    if not results:
        return []

    try:
        cross_encoder = await _load_cross_encoder(model)
    except ImportError:
        # Without the extra, return results unchanged.
        return results

    pairs = [(query, _text_of(result)) for result in results]
    scores = await asyncio.to_thread(cross_encoder.predict, cast(list[Any], pairs))

    reranked: list[SearchResult] = []
    for result, score in zip(results, scores, strict=True):
        score_val = float(score)
        if min_score is not None and score_val < min_score:
            continue
        reranked.append(
            SearchResult(item=result.item, score=score_val, method="cross_encoder")
        )

    reranked.sort(key=lambda r: r.score, reverse=True)
    return reranked


def _text_of(result: SearchResult) -> str:
    """Extract display text from a SearchResult's item."""
    from agrag.common.data_models.chunk import Chunk  # noqa: PLC0415
    from agrag.common.data_models.entity import Entity  # noqa: PLC0415
    from agrag.common.data_models.relation import Relation  # noqa: PLC0415
    from agrag.common.data_models.resolved_entity import ResolvedEntity  # noqa: PLC0415

    item = result.item
    if isinstance(item, (Entity, ResolvedEntity)):
        return item.embedding_text
    if isinstance(item, Chunk):
        return item.text
    if isinstance(item, Relation):
        return f"{item.type}({item.source_id}, {item.target_id})"
    if isinstance(item, Community):
        return item.embedding_text
    return str(item)
