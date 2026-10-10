"""Tests for LLM pair selection and ambiguous-cluster preclustering.

Covers select_llm_pairs ranking ambiguous candidates by similarity with a cap,
and precluster_ambiguous auto-merging only tight sub-clusters.
"""

from uuid import uuid4

from agrag.ingestion.resolve.zone_classifier import (
    precluster_ambiguous,
    select_llm_pairs,
)


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

    def test_non_positive_cap_returns_no_pairs(self) -> None:
        """A non-positive cap cannot bypass the LLM review limit."""
        candidates = [(0, 1, 0.82), (2, 3, 0.90)]

        assert select_llm_pairs(candidates, max_pairs=-1) == []


class TestPreclusterAmbiguous:
    """precluster_ambiguous auto-merges only tight sub-clusters."""

    def test_tight_pair_auto_merges(self) -> None:
        """A pair inside the hard-merge zone comes back as one group."""
        ids = [uuid4(), uuid4(), uuid4()]

        assert precluster_ambiguous(ids, {(0, 1): 0.99}) == [ids[0:2]]

    def test_similarity_above_one_from_rounding_still_merges(self) -> None:
        """Float error can put a cosine similarity of identical vectors above 1."""
        ids = [uuid4(), uuid4(), uuid4()]

        assert precluster_ambiguous(ids, {(0, 1): 1.0000000002}) == [ids[0:2]]

    def test_ambiguous_band_pair_needs_llm_review(self) -> None:
        """A merely ambiguous similarity never auto-merges."""
        ids = [uuid4(), uuid4()]

        assert precluster_ambiguous(ids, {(0, 1): 0.85}) == []

    def test_uses_configured_hard_merge_threshold(self) -> None:
        """A pair below the active threshold stays out of auto-merge."""
        ids = [uuid4(), uuid4()]

        assert (
            precluster_ambiguous(ids, {(0, 1): 0.97}, hard_merge_threshold=0.99) == []
        )
