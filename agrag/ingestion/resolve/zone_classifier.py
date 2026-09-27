"""Zone classification for entity-resolution candidate pairs."""

from collections.abc import Mapping, Sequence
from typing import cast
from uuid import UUID

import numpy as np

from agrag.ingestion._clustering import average_linkage_clusters


HARD_MERGE_THRESHOLD = 0.95
DISCARD_THRESHOLD = 0.80
FUZZY_FAST_PATH_THRESHOLD = 0.97
MAX_LLM_PAIRS = 500


def classify_zone(fuzzy_score: float, embedding_similarity: float | None) -> str:
    """Assign a candidate pair to a resolution zone.

    A near-identical fuzzy score merges without consulting the embedding.
    Otherwise the embedding similarity decides: at or above the hard-merge
    threshold the pair merges, inside the discard-to-hard-merge band it
    needs LLM review, and below the discard threshold it is dropped. A
    missing embedding with a below-fast-path fuzzy score also discards,
    since no signal supports a merge.

    Args:
        fuzzy_score: Token-sort-ratio similarity in ``[0, 1]``.
        embedding_similarity: Cosine similarity in ``[-1, 1]``, or ``None``
            when no embedding is available.

    Returns:
        ``"hard_merge"``, ``"ambiguous"``, or ``"discard"``.
    """
    if fuzzy_score >= FUZZY_FAST_PATH_THRESHOLD:
        return "hard_merge"
    if embedding_similarity is None:
        return "discard"
    if embedding_similarity >= HARD_MERGE_THRESHOLD:
        return "hard_merge"
    if embedding_similarity >= DISCARD_THRESHOLD:
        return "ambiguous"
    return "discard"


def select_llm_pairs(
    candidates: Sequence[tuple[int, int, float] | tuple[int, int, float, float]],
    *,
    max_pairs: int = MAX_LLM_PAIRS,
) -> list[tuple[int, int]]:
    """Rank ambiguous candidates for LLM review, most similar first.

    Triples rank by similarity descending. Quadruples carrying a fuzzy
    score as fourth element rank by rank fusion: the cosine rank plus
    the fuzzy rank, smallest first, with ties broken by index pair.
    All candidates must share one shape.

    Args:
        candidates: ``(left_index, right_index, similarity)`` triples,
            or quadruples with a fuzzy score appended.
        max_pairs: Maximum pairs to return.

    Returns:
        Index pairs in ranked order, capped at ``max_pairs``.
    """
    if max_pairs <= 0:
        return []
    if candidates and len(candidates[0]) == 4:
        fused = cast(Sequence[tuple[int, int, float, float]], candidates)
        return _rank_fused_pairs(fused, max_pairs)
    triples = cast(Sequence[tuple[int, int, float]], candidates)
    ranked = sorted(triples, key=lambda candidate: candidate[2], reverse=True)
    return [(left, right) for left, right, _ in ranked[:max_pairs]]


def _competition_rank(scores: list[float]) -> list[int]:
    """Map each score to its zero-based rank, highest first.

    Tied scores share the best rank for their group.
    """
    order = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)
    ranks = [0] * len(scores)
    for position, index in enumerate(order):
        if position and scores[index] == scores[order[position - 1]]:
            ranks[index] = ranks[order[position - 1]]
        else:
            ranks[index] = position
    return ranks


def _rank_fused_pairs(
    candidates: Sequence[tuple[int, int, float, float]], max_pairs: int
) -> list[tuple[int, int]]:
    """Rank cosine-plus-fuzzy quadruples by rank-sum fusion."""
    cosine_rank = _competition_rank([similarity for _, _, similarity, _ in candidates])
    fuzzy_rank = _competition_rank([fuzzy for _, _, _, fuzzy in candidates])
    order = sorted(
        range(len(candidates)),
        key=lambda index: (
            cosine_rank[index] + fuzzy_rank[index],
            candidates[index][0],
            candidates[index][1],
        ),
    )
    return [(candidates[index][0], candidates[index][1]) for index in order[:max_pairs]]


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
