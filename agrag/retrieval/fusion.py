"""Reciprocal Rank Fusion: combine ranked results from multiple methods."""

from agrag.common.data_models.search_result import SearchResult


def fuse(
    results_by_method: dict[str, list[SearchResult]],
    *,
    rrf_k: int = 60,
) -> list[SearchResult]:
    """Combine every method's ranked results into one deduplicated list.

    Runs unconditionally, even for a single method, so a Rerank pass
    never sees duplicates. Uses Reciprocal Rank Fusion: an item's
    fused score is the sum of 1 / (rrf_k + rank) across every method
    that returned it.

    Each method contributes at most one vote per item, scored at the
    item's best (lowest) rank within that method. A multi-label
    entity that surfaces in two positions of one method's output, or
    a pre-fusion ``merged_into`` collapse, only adds one vote from
    that method, so duplicate hits from a single retriever cannot
    unfairly promote an item over a single best hit from another
    method.

    Deduplication uses SearchResult.identity_key, which is (type, id)
    after hydration has already resolved any merged_into chain to the
    live survivor. Fusion does not re-resolve identity; it trusts that
    every SearchResult it receives already carries a live id.

    Args:
        results_by_method: Each method's own ranked output, keyed by
            method name.
        rrf_k: The RRF constant; higher values flatten the influence
            of rank position.

    Returns:
        One list, ranked by fused score descending, one entry per
        distinct identity_key.
    """
    scores: dict[tuple[str, object], float] = {}
    best_result: dict[tuple[str, object], SearchResult] = {}

    for _method, results in results_by_method.items():
        # One vote per (method, item): track the best rank this method
        # has seen for each item, so a multi-label duplicate does not
        # contribute extra votes.
        method_best_rank: dict[tuple[str, object], int] = {}
        for rank, result in enumerate(results):
            key = result.identity_key
            if key not in method_best_rank or rank < method_best_rank[key]:
                method_best_rank[key] = rank
            # Keep the result with the highest individual score; this is
            # independent of the rank-based RRF score.
            if key not in best_result or result.score > best_result[key].score:
                best_result[key] = result
        for key, best_rank in method_best_rank.items():
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + best_rank + 1)

    fused: list[SearchResult] = []
    for key, rrf_score in sorted(
        scores.items(), key=lambda item: item[1], reverse=True
    ):
        result = best_result[key]
        fused.append(
            SearchResult(
                item=result.item,
                score=rrf_score,
                method=result.method,
            )
        )

    return fused
