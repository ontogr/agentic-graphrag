"""Regression test of the exact and fuzzy resolver tiers on company names.

Resolves every name of ``tests/fixtures/eval/resolution/company_clusters.json``
with the two deterministic tiers and gates on B-cubed F1. The tiers merge only
names that are equal or near identical, so a renamed company (Facebook and Meta)
stays split. That is expected: the score shows what these tiers do alone. Most
of the score comes from the many names that need no merge, and pairwise recall
is near zero. A fall below the threshold means the tiers merged different
companies, or lost a merge they made before.

The system is deterministic, so the threshold is the measured score (0.8236)
minus 0.02, rounded down to 0.01. The in-batch candidate source must never call
the graph store.
"""

from unittest.mock import AsyncMock

from agrag.eval import cluster_quality_metric, resolution_case, run_resolver
from agrag.ingestion.resolve.candidate_source import GraphCandidateSource
from agrag.ingestion.resolve.resolver import ExactMatch, FuzzyMatch, Resolver
from tests.integration.eval._resolution_quality import (
    load_company_clusters,
    mentions_and_gold,
)


THRESHOLD = 0.80


class TestResolutionRegression:
    """The exact and fuzzy tiers keep the measured cluster quality."""

    async def test_exact_and_fuzzy_tiers_meet_threshold_on_company_names(self) -> None:
        """B-cubed F1 stays at or above the gate, without touching the store."""
        graph_store = AsyncMock()
        resolver = Resolver(
            comparators=[ExactMatch(), FuzzyMatch()],
            candidate_source=GraphCandidateSource(
                graph_store=graph_store, embedder=None, vector_store=None
            ),
            embedder=None,
        )
        mentions, gold = mentions_and_gold(load_company_clusters().clusters)

        predicted = await run_resolver(resolver, mentions)
        metric = cluster_quality_metric(threshold=THRESHOLD)
        score = metric.measure(resolution_case(mentions, predicted, gold))

        assert graph_store.mock_calls == []
        assert score >= THRESHOLD
