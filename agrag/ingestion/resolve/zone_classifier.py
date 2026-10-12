"""Pair selection and sub-clustering for entity-resolution LLM review."""

from collections.abc import Mapping
from uuid import UUID

import numpy as np

from agrag.ingestion._clustering import average_linkage_clusters


HARD_MERGE_THRESHOLD = 0.95
DISCARD_THRESHOLD = 0.80
MAX_LLM_PAIRS = 500


def select_llm_pairs(
    candidates: list[tuple[int, int, float]], *, max_pairs: int = MAX_LLM_PAIRS
) -> list[tuple[int, int]]:
    """Rank ambiguous candidates for LLM review and keep the first ``max_pairs``.

    The order is similarity, highest first. Pairs with equal similarity keep the
    lower ``(left_index, right_index)`` first, so the same input always yields
    the same pairs. The pairs this drops are the least similar, and the caller
    must report them as undecided.

    Args:
        candidates: ``(left_index, right_index, similarity)`` triples.
        max_pairs: Maximum pairs to return.

    Returns:
        Index pairs in the order above, at most ``max_pairs`` of them.
    """
    if max_pairs <= 0:
        return []
    ranked = sorted(
        candidates, key=lambda candidate: (-candidate[2], candidate[0], candidate[1])
    )
    return [(left, right) for left, right, _ in ranked[:max_pairs]]


def precluster_ambiguous(
    ids: list[UUID],
    similarities: Mapping[tuple[int, int], float],
    *,
    hard_merge_threshold: float = HARD_MERGE_THRESHOLD,
) -> list[list[UUID]]:
    """Find tight ambiguous sub-clusters that can merge without LLM review.

    Runs average-linkage clustering cut at ``1 - HARD_MERGE_THRESHOLD`` so
    only groups whose mean pairwise distance sits inside the hard-merge
    zone come back. Pairs absent from ``similarities`` count as maximally
    distant and never join a group.

    Args:
        ids: Candidate entity identifiers.
        similarities: Cosine similarity keyed by ``(left, right)`` index
            into ``ids``, symmetric entries optional.
        hard_merge_threshold: Similarity required for an automatic merge.

    Returns:
        Only multi-member groups; singletons need LLM review or discard.
    """
    count = len(ids)
    distances = np.ones((count, count))
    for index in range(count):
        distances[index, index] = 0.0
    for (left, right), similarity in similarities.items():
        # Rounding can push the similarity of identical vectors above 1.
        distance = max(0.0, 1.0 - similarity)
        distances[left, right] = distance
        distances[right, left] = distance
    clusters = average_linkage_clusters(
        ids, distances, cut_distance=1.0 - hard_merge_threshold
    )
    return [cluster for cluster in clusters if len(cluster) > 1]
