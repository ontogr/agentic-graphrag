"""Resolution quality test of the full resolver on company names.

Resolves every name of ``tests/fixtures/eval/resolution/company_clusters.json``
(SEC EDGAR and GLEIF records, see the NOTICE beside it) with all tiers: exact,
fuzzy, embedding similarity and LLM verification. It gates on B-cubed F1 and on
pairwise F1. The report has the B-cubed and pairwise scores and the matches per
tier. It goes to ``reports/eval/resolution_quality.json``, or to the directory in
``E2E_ARTIFACT_DIR``.

The test skips without ``LLM_*`` settings or without ``sentence-transformers``.
The embedder is the default of ``EmbeddingSettings``, which runs on the local
machine and downloads its weights on first use.

Cost: at most 50 LLM requests of 10 pairs each per run. The resolver sends at
most 500 boundary pairs per label to the LLM, and every name has one label. The
requests run one after another, so they do not trip a concurrency limit.
``LLMVerify`` maps a failed request to "no match", so the test also asserts that
the LLM confirmed at least one match. A dead endpoint then fails the run.

Each threshold is the lowest of three baseline runs minus 0.05, rounded down to
0.05. Baseline runs (B-cubed F1, pairwise F1):

    run 1: 0.884, 0.679
    run 2: 0.884, 0.679
    run 3: 0.886, 0.687

The exact and fuzzy tiers alone score 0.824 and 0.019 on the same names. Most
B-cubed credit comes from names that need no merge, so the B-cubed gate sits
just under the score of the deterministic tiers. The pairwise gate is what
fails when the embedding or LLM tier stops merging.
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from agrag.embedding import SentenceTransformerEmbedder
from agrag.eval import cluster_quality_metric, resolution_case, run_resolver
from agrag.ingestion.extract import ExtractionLLMSettings
from agrag.ingestion.resolve.candidate_source import GraphCandidateSource
from agrag.ingestion.resolve.resolver import (
    ExactMatch,
    FuzzyMatch,
    LLMVerify,
    Resolver,
)
from tests.integration.e2e._artifact import write_artifact
from tests.integration.eval._resolution_quality import (
    load_company_clusters,
    mentions_and_gold,
)


REPORT_DIR = Path(__file__).parents[3] / "reports" / "eval"

# Minimum B-cubed F1 and pairwise F1.
THRESHOLD = 0.80
PAIRWISE_THRESHOLD = 0.60


def _llm_settings() -> ExtractionLLMSettings:
    """Read the LLM endpoint from the environment, or skip when it is not set."""
    try:
        settings = ExtractionLLMSettings.from_openai_compatible_env()
    except RuntimeError:
        pytest.skip("LLM endpoint not configured")
    if not settings.clients[0].api_key:
        pytest.skip("LLM API key not configured")
    return settings


async def test_full_resolver_meets_threshold_on_company_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The resolver clusters company names at or above the gate."""
    pytest.importorskip("sentence_transformers")
    settings = _llm_settings()
    embedder = SentenceTransformerEmbedder()
    graph_store = AsyncMock()
    resolver = Resolver(
        comparators=[
            ExactMatch(),
            FuzzyMatch(),
            LLMVerify(chunks_by_id={}, settings=settings),
        ],
        candidate_source=GraphCandidateSource(
            graph_store=None,
            embedder=embedder,
            vector_store=None,
        ),
        embedder=embedder,
    )
    mentions, gold = mentions_and_gold(load_company_clusters().clusters)

    predicted = await run_resolver(resolver, mentions)
    metric = cluster_quality_metric(threshold=THRESHOLD)
    score = metric.measure(resolution_case(mentions, predicted, gold))

    if "E2E_ARTIFACT_DIR" not in os.environ:
        monkeypatch.setenv("E2E_ARTIFACT_DIR", str(REPORT_DIR))
    report = write_artifact(
        "resolution_quality",
        {
            "mentions": len(mentions),
            "scores": {"b_cubed_f": score, **metric.score_breakdown},
            "matches_by_tier": predicted.matches_by_tier,
        },
    )

    assert graph_store.mock_calls == []
    assert report["mentions"] == len(mentions)
    assert predicted.matches_by_tier.get("llm", 0) >= 1
    assert score >= THRESHOLD
    assert metric.score_breakdown["pairwise_f"] >= PAIRWISE_THRESHOLD
