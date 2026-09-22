"""Tests for ambiguous-zone classification and LLM pair selection.

Covers classify_zone's exact thresholds (fuzzy fast path at 0.97,
hard-merge at embedding 0.95, discard below embedding 0.80, each tested
at, just above, and just below the boundary), select_llm_pairs ranking
ambiguous candidates by similarity with a cap, precluster_ambiguous
auto-merging only tight sub-clusters, and FuzzyMatch never returning
NO_MATCH for any dissimilar pair.
"""

from uuid import uuid4

import pytest

from agrag.common.data_models.extraction import ExtractedEntity
from agrag.ingestion.resolve import ComparisonVerdict, FuzzyMatch
from agrag.ingestion.resolve.zone_classifier import (
    MAX_LLM_PAIRS,
    classify_zone,
    precluster_ambiguous,
    select_llm_pairs,
)


def _entity(text: str) -> ExtractedEntity:
    """Build a minimal ExtractedEntity."""
    return ExtractedEntity(
        chunk_id=uuid4(),
        label="Person",
        text=text,
        char_start=0,
        char_end=max(len(text), 1),
    )


class TestClassifyZone:
    """classify_zone routes pairs to hard_merge, ambiguous, or discard."""

    @pytest.mark.parametrize(
        ("fuzzy_score", "expected"),
        [(0.9699, "discard"), (0.97, "hard_merge"), (0.99, "hard_merge")],
    )
    def test_fuzzy_fast_path_boundary(self, fuzzy_score: float, expected: str) -> None:
        """The 0.97 fuzzy score merges without consulting the embedding."""
        assert classify_zone(fuzzy_score, None) == expected

    @pytest.mark.parametrize(
        ("embedding", "expected"),
        [(0.9499, "ambiguous"), (0.95, "hard_merge"), (0.96, "hard_merge")],
    )
    def test_hard_merge_boundary(self, embedding: float, expected: str) -> None:
        """The 0.95 embedding similarity merges a below-fast-path pair."""
        assert classify_zone(0.5, embedding) == expected

    @pytest.mark.parametrize(
        ("embedding", "expected"),
        [(0.7999, "discard"), (0.80, "ambiguous"), (0.81, "ambiguous")],
    )
    def test_discard_boundary(self, embedding: float, expected: str) -> None:
        """The 0.80 embedding similarity separates ambiguous from discard."""
        assert classify_zone(0.5, embedding) == expected

    def test_high_fuzzy_wins_over_low_embedding(self) -> None:
        """A fast-path fuzzy score merges despite a terrible embedding."""
        assert classify_zone(0.99, 0.0) == "hard_merge"

    def test_missing_embedding_discards_below_fast_path(self) -> None:
        """No embedding and no fast-path score leaves no merge signal."""
        assert classify_zone(0.5, None) == "discard"


class TestSelectLlmPairs:
    """select_llm_pairs ranks ambiguous pairs most-similar-first, capped."""

    def test_ranks_by_similarity_descending(self) -> None:
        """Output order follows similarity, not input order."""
        candidates = [(0, 1, 0.82), (2, 3, 0.90), (4, 5, 0.85)]

        assert select_llm_pairs(candidates) == [(2, 3), (4, 5), (0, 1)]

    def test_caps_at_max_pairs(self) -> None:
        """Only the most similar max_pairs pairs are returned."""
        candidates = [(0, 1, 0.82), (2, 3, 0.90), (4, 5, 0.85)]

        assert select_llm_pairs(candidates, max_pairs=2) == [(2, 3), (4, 5)]

    def test_default_cap_is_max_llm_pairs(self) -> None:
        """The default cap drops everything past MAX_LLM_PAIRS."""
        candidates = [(i, i + 1, 0.85) for i in range(MAX_LLM_PAIRS + 1)]

        assert len(select_llm_pairs(candidates)) == MAX_LLM_PAIRS


class TestPreclusterAmbiguous:
    """precluster_ambiguous auto-merges only tight sub-clusters."""

    def test_tight_pair_auto_merges(self) -> None:
        """A pair inside the hard-merge zone comes back as one group."""
        ids = [uuid4(), uuid4(), uuid4()]

        assert precluster_ambiguous(ids, {(0, 1): 0.99}) == [ids[0:2]]

    def test_ambiguous_band_pair_needs_llm_review(self) -> None:
        """A merely ambiguous similarity never auto-merges."""
        ids = [uuid4(), uuid4()]

        assert precluster_ambiguous(ids, {(0, 1): 0.85}) == []

    def test_unknown_pairs_count_as_maximally_distant(self) -> None:
        """Pairs absent from similarities cannot join a group."""
        ids = [uuid4(), uuid4(), uuid4()]

        assert precluster_ambiguous(ids, {(0, 1): 0.99}) == [ids[0:2]]


class TestFuzzyMatchFastPath:
    """FuzzyMatch never rejects, however dissimilar the pair."""

    @pytest.mark.parametrize(
        ("first", "second"),
        [
            ("Apple", "Banana"),
            ("Ada", "Quantum Physics"),
            ("X", "Completely unrelated words here"),
        ],
    )
    async def test_never_returns_no_match(self, first: str, second: str) -> None:
        """Dissimilar pairs defer with UNCERTAIN instead of NO_MATCH."""
        matcher = FuzzyMatch()

        verdict = await matcher.compare(_entity(first), _entity(second))

        assert verdict is not ComparisonVerdict.NO_MATCH
        assert verdict is ComparisonVerdict.UNCERTAIN
