"""Tests that a per-call override of a Recipe preset leaves the preset unmutated."""

from agrag.retrieval.recipes import (
    HYBRID_RERANKED,
)


class TestRecipe:
    """Recipe is a named, data-only configuration."""

    def test_model_copy_overrides_min_score_without_mutating_preset(self) -> None:
        """A per-call override leaves the shared preset unmutated."""
        updated = HYBRID_RERANKED.model_copy(update={"min_score": 0.5})

        assert updated.min_score == 0.5
        assert HYBRID_RERANKED.min_score is None
