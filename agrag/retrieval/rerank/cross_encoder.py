"""Cross-encoder reranker using sentence-transformers."""

from agrag.common.data_models.search_result import SearchResult


async def cross_encoder_rerank(
    query: str,
    results: list[SearchResult],
    *,
    min_score: float | None = None,
) -> list[SearchResult]:
    """Rerank results using a cross-encoder model.

    Requires the ``embed-local`` extra (sentence-transformers).
    Scores (query, text) pairs and reorders by relevance. Drops
    results scoring below min_score when set.

    Args:
        query: The natural-language query text.
        results: The fused results to rerank.
        min_score: Optional minimum score threshold. Results below
            this are dropped.

    Returns:
        Results reranked by cross-encoder score, descending.
    """
    if not results:
        return []

    try:
        from sentence_transformers import (  # noqa: PLC0415
            CrossEncoder,
        )
    except ImportError:
        # Without the extra, return results unchanged.
        return results

    model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    pairs = [(query, _text_of(result)) for result in results]
    scores = model.predict(pairs)

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
            )
        )

    reranked.sort(key=lambda r: r.score, reverse=True)
    return reranked


def _text_of(result: SearchResult) -> str:
    """Extract display text from a SearchResult's item."""
    from agrag.common.data_models.chunk import Chunk  # noqa: PLC0415
    from agrag.common.data_models.entity import Entity  # noqa: PLC0415
    from agrag.common.data_models.relation import Relation  # noqa: PLC0415

    item = result.item
    if isinstance(item, Entity):
        return item.embedding_text
    if isinstance(item, Chunk):
        return item.text
    if isinstance(item, Relation):
        return f"{item.type}({item.source_id}, {item.target_id})"
    return str(item)
