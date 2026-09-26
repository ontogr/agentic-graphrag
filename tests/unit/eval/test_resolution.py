"""Tests for ``agrag.eval.resolution``.

The scoring arithmetic belongs to ``er-evaluation`` and is not re-tested. These
tests cover the direction of each error, the handling of singletons and bad
input, and one run of the real exact and fuzzy tiers with a mock graph store.
"""

from unittest.mock import AsyncMock

import pytest

from agrag.eval import (
    ClusterAssignment,
    cluster_quality_metric,
    resolution_case,
    run_resolver,
)
from agrag.ingestion.resolve.candidate_source import GraphCandidateSource
from agrag.ingestion.resolve.resolver import ExactMatch, FuzzyMatch, Resolver


MENTIONS = ["a", "b", "c", "d"]
GOLD = ClusterAssignment(size=4, clusters=[[0, 1, 2]])


def _score(predicted: ClusterAssignment, gold: ClusterAssignment = GOLD) -> dict:
    """Measure one case and return its score and breakdown."""
    metric = cluster_quality_metric()
    metric.measure(resolution_case(MENTIONS, predicted, gold))
    return {"score": metric.score, **metric.score_breakdown}


class TestClusterQualityMetric:
    """The metric moves the right way for each kind of error."""

    def test_perfect_prediction_scores_one(self) -> None:
        """Identical clusters give every value 1.0."""
        result = _score(GOLD)

        assert result["score"] == 1.0
        assert result["pairwise_f"] == 1.0

    def test_over_merge_lowers_precision_not_recall(self) -> None:
        """Merging two gold clusters costs precision on both scales."""
        gold = ClusterAssignment(size=4, clusters=[[0, 1], [2, 3]])
        result = _score(ClusterAssignment(size=4, clusters=[[0, 1, 2, 3]]), gold)

        assert result["b_cubed_precision"] < 1.0
        assert result["pairwise_precision"] < 1.0
        assert result["b_cubed_recall"] == 1.0
        assert result["pairwise_recall"] == 1.0

    def test_under_merge_lowers_recall_not_precision(self) -> None:
        """Splitting a gold cluster costs recall on both scales."""
        result = _score(ClusterAssignment(size=4, clusters=[[0, 1]]))

        assert result["b_cubed_recall"] < 1.0
        assert result["pairwise_recall"] < 1.0
        assert result["b_cubed_precision"] == 1.0
        assert result["pairwise_precision"] == 1.0

    def test_unlisted_indices_count_as_singletons(self) -> None:
        """An empty prediction equals a prediction that lists every singleton."""
        listed = ClusterAssignment(size=4, clusters=[[0], [1], [2], [3]])

        assert _score(ClusterAssignment(size=4, clusters=[])) == _score(listed)
        assert _score(listed)["score"] < 1.0

    def test_different_sizes_raise(self) -> None:
        """A prediction over other mentions than gold cannot be scored."""
        metric = cluster_quality_metric()
        case = resolution_case(MENTIONS, ClusterAssignment(size=3, clusters=[]), GOLD)

        with pytest.raises(ValueError, match="3 mentions but gold has 4"):
            metric.measure(case)

    @pytest.mark.parametrize(
        "clusters", [[[0, 4]], [[0, 1], [1, 2]]], ids=["out-of-range", "repeated"]
    )
    def test_invalid_clusters_are_rejected(self, clusters: list[list[int]]) -> None:
        """An index outside the mentions, or in two clusters, is an error."""
        with pytest.raises(ValueError):
            ClusterAssignment(size=4, clusters=clusters)


class TestRunResolver:
    """``run_resolver`` reports the clusters of a real exact and fuzzy resolver."""

    async def test_groups_exact_and_fuzzy_pairs_without_the_store(self) -> None:
        """Repeated and near-identical names cluster; the graph store is not used."""
        graph_store = AsyncMock()
        resolver = Resolver(
            comparators=[ExactMatch(), FuzzyMatch()],
            candidate_source=GraphCandidateSource(
                graph_store=graph_store, embedder=None, vector_store=None
            ),
            embedder=None,
        )
        mentions = ["Acme Corp", "acme corp", "Corp Acme", "Zenith Ltd"]

        result = await run_resolver(resolver, mentions)

        assert result.size == 4
        merged = [sorted(cluster) for cluster in result.clusters if len(cluster) > 1]
        assert merged == [[0, 1, 2]]
        assert result.matches_by_tier == {"fuzzy_fast_path": 2}
        assert graph_store.mock_calls == []
