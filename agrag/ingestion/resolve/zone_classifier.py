"""Embedding-similarity zones for non-vetoing entity comparison."""

from enum import StrEnum


FUZZY_FAST_PATH_THRESHOLD = 0.97
HARD_MERGE_THRESHOLD = 0.95
DISCARD_THRESHOLD = 0.80


class ComparisonZone(StrEnum):
    """The resolution tier selected for a candidate pair."""

    HARD_MERGE = "hard_merge"
    AMBIGUOUS = "ambiguous"
    DISCARD = "discard"


def classify_zone(
    *, fuzzy_score: float | None = None, embedding_similarity: float | None = None
) -> ComparisonZone:
    """Classify a pair, allowing fuzzy similarity only to accept fast."""
    if fuzzy_score is not None and fuzzy_score >= FUZZY_FAST_PATH_THRESHOLD:
        return ComparisonZone.HARD_MERGE
    if embedding_similarity is None:
        raise ValueError("embedding_similarity is required without a fuzzy fast path")
    if embedding_similarity >= HARD_MERGE_THRESHOLD:
        return ComparisonZone.HARD_MERGE
    if embedding_similarity >= DISCARD_THRESHOLD:
        return ComparisonZone.AMBIGUOUS
    return ComparisonZone.DISCARD
