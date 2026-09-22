"""Zone classification for entity-resolution candidate pairs."""

from collections.abc import Mapping
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
    candidates: list[tuple[int, int, float]], *, max_pairs: int = MAX_LLM_PAIRS
) -> list[tuple[int, int]]:
    """Rank ambiguous candidates for LLM review, most similar first.

    Args:
        candidates: ``(left_index, right_index, similarity)`` triples.
        max_pairs: Maximum pairs to return.

    Returns:
        Index pairs ordered by similarity descending, capped at
        ``max_pairs``.
    """
    ranked = sorted(candidates, key=lambda candidate: candidate[2], reverse=True)
    return [(left, right) for left, right, _ in ranked[:max_pairs]]


def precluster_ambiguous(
    ids: list[UUID], similarities: Mapping[tuple[int, int], float]
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

    Returns:
        Only multi-member groups; singletons need LLM review or discard.
    """
    count = len(ids)
    distances = np.ones((count, count))
    for index in range(count):
        distances[index, index] = 0.0
    for (left, right), similarity in similarities.items():
        distance = 1.0 - similarity
        distances[left, right] = distance
        distances[right, left] = distance
    clusters = average_linkage_clusters(
        ids, distances, cut_distance=1.0 - HARD_MERGE_THRESHOLD
    )
    return [cluster for cluster in clusters if len(cluster) > 1]
