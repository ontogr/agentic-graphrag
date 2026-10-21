"""Unit tests for reciprocal rank fusion, the hybrid search step.

Fusion is pure arithmetic over ranked id lists, so these tests need no store.
"""

import pytest

from agrag.evidence.search import reciprocal_rank_fusion


class TestReciprocalRankFusion:
    """Fused scores reward ids that rank high in more than one list."""

    def test_id_in_both_lists_outranks_id_in_one_list_at_same_rank(self) -> None:
        """An id that two legs both rank first gets the highest fused score."""
        scores = reciprocal_rank_fusion([["a", "b"], ["a", "c"]])

        ordered = sorted(scores, key=lambda item: -scores[item])
        assert ordered[0] == "a"
        assert scores["b"] == scores["c"]

    def test_scores_follow_the_standard_formula(self) -> None:
        """Each list adds 1 / (constant + rank) with ranks starting at 1."""
        scores = reciprocal_rank_fusion([["a", "b"], ["b"]], constant=10)

        assert scores["a"] == pytest.approx(1 / 11)
        assert scores["b"] == pytest.approx(1 / 12 + 1 / 11)

    def test_empty_input_gives_no_scores(self) -> None:
        """No rankings give an empty result."""
        assert reciprocal_rank_fusion([]) == {}
        assert reciprocal_rank_fusion([[], []]) == {}
