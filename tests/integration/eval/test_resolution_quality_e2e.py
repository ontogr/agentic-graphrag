"""Resolution quality test of the full resolver on company names.

Resolves every name of ``tests/fixtures/eval/resolution/company_clusters.json``
(SEC EDGAR and GLEIF records, see the NOTICE beside it) with all tiers: exact,
fuzzy, embedding similarity and LLM verification. It gates on B-cubed F1 and on
pairwise F1. The report has the B-cubed and pairwise scores, the matches per
tier, and the false merges and missed gold pairs with their zone fates. It
goes to ``reports/eval/resolution_quality.json``, or to the directory in
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

    run 1: 0.880, 0.675
    run 2: 0.878, 0.667
    run 3: 0.882, 0.675

The exact and fuzzy tiers alone score 0.829 and 0.019 on the same names. Most
B-cubed credit comes from names that need no merge, so the B-cubed gate sits
just under the score of the deterministic tiers. The pairwise gate is what
fails when the embedding or LLM tier stops merging.
"""

import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import pytest

from agrag.common.text import normalize_text
from agrag.embedding import SentenceTransformerEmbedder
from agrag.eval import (
    ClusterAssignment,
    cluster_quality_metric,
    resolution_case,
    run_resolver_detailed,
)
from agrag.ingestion.extract import ExtractionLLMSettings
from agrag.ingestion.resolve.candidate_source import GraphCandidateSource
from agrag.ingestion.resolve.resolver import (
    ExactMatch,
    FuzzyMatch,
    LLMVerify,
    ResolutionGroup,
    ResolutionResult,
    ResolvedMatch,
    Resolver,
)
from agrag.ingestion.resolve.zone_classifier import (
    DISCARD_THRESHOLD,
    HARD_MERGE_THRESHOLD,
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


def _cosine(left: list[float], right: list[float]) -> float:
    """Return the cosine similarity of two vectors."""
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _pairs_of(assignment: ClusterAssignment) -> set[tuple[int, int]]:
    """Expand clusters into unordered index pairs."""
    pairs: set[tuple[int, int]] = set()
    for cluster in assignment.clusters:
        for first in range(len(cluster)):
            for second in range(first + 1, len(cluster)):
                left, right = cluster[first], cluster[second]
                pairs.add((min(left, right), max(left, right)))
    return pairs


class _PairFate(TypedDict):
    """One scored pair and the outcome supported by resolver evidence."""

    pair: list[str]
    fate: str
    cosine: float


async def _pair_fates(
    mentions: list[str],
    gold: ClusterAssignment,
    predicted: ClusterAssignment,
    result: ResolutionResult,
    embedder: SentenceTransformerEmbedder,
) -> tuple[list[_PairFate], list[_PairFate]]:
    """Explain pair outcomes using direct resolver evidence when available."""
    vectors = await embedder.embed(mentions)
    similarities: dict[tuple[int, int], float] = {}
    for left in range(len(mentions)):
        for right in range(left + 1, len(mentions)):
            similarities[(left, right)] = _cosine(vectors[left], vectors[right])
    direct_matches = {
        (
            min(match.left_index, match.right_index),
            max(match.left_index, match.right_index),
        ): match.comparator
        for match in result.matches
    }
    gold_pairs = _pairs_of(gold)
    predicted_pairs = _pairs_of(predicted)

    def fate(left: int, right: int, merged: bool) -> _PairFate:
        """Label a pair without attributing a decision that was not recorded."""
        pair = (left, right)
        sim = similarities[pair]
        comparator = direct_matches.get(pair)
        if comparator == "llm":
            label = "accepted-by-llm"
        elif comparator == "embedding":
            label = "accepted-by-embedding"
        elif comparator == "fuzzy_fast_path":
            label = "accepted-by-fuzzy-fast-path"
        elif normalize_text(mentions[left]) == normalize_text(mentions[right]):
            label = "accepted-by-exact-match"
        elif merged:
            label = "transitive-merge"
        elif sim < DISCARD_THRESHOLD:
            label = "low-similarity-not-merged"
        elif sim >= HARD_MERGE_THRESHOLD:
            label = "high-similarity-not-merged"
        else:
            label = "boundary-not-merged"
        names = sorted([mentions[left], mentions[right]])
        return {"pair": names, "fate": label, "cosine": round(sim, 4)}

    false = sorted(predicted_pairs - gold_pairs)
    missed = sorted(gold_pairs - predicted_pairs)
    false_merges = [fate(left, right, True) for left, right in false]
    missed_pairs = [fate(left, right, False) for left, right in missed]
    false_merges.sort(key=lambda entry: entry["pair"])
    missed_pairs.sort(key=lambda entry: entry["pair"])
    return false_merges, missed_pairs


async def test_pair_fates_report_transitive_merges_without_llm_attribution() -> None:
    """A cluster path does not make every pair an LLM-confirmed match."""

    class _FakeEmbedder:
        async def embed(self, mentions: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in mentions]

    now = datetime.now(UTC)
    result = ResolutionResult(
        groups=[ResolutionGroup(entity_indices=[0, 1, 2])],
        matches=[
            ResolvedMatch(
                left_index=0,
                right_index=1,
                comparator="llm",
                decided_at=now,
            ),
            ResolvedMatch(
                left_index=1,
                right_index=2,
                comparator="embedding",
                decided_at=now,
            ),
        ],
    )
    predicted = ClusterAssignment(size=3, clusters=[[0, 1, 2]])
    gold = ClusterAssignment(size=3, clusters=[[0, 1]])

    false_merges, _ = await _pair_fates(
        ["Alpha", "Beta", "Gamma"], gold, predicted, result, _FakeEmbedder()
    )

    assert false_merges == [
        {"pair": ["Alpha", "Gamma"], "fate": "transitive-merge", "cosine": 1.0},
        {"pair": ["Beta", "Gamma"], "fate": "accepted-by-embedding", "cosine": 1.0},
    ]


async def test_full_resolver_meets_threshold_on_company_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The resolver clusters company names at or above the gate."""
    pytest.importorskip("sentence_transformers")
    settings = _llm_settings()
    embedder = SentenceTransformerEmbedder()
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

    predicted, result = await run_resolver_detailed(resolver, mentions)
    metric = cluster_quality_metric(threshold=THRESHOLD)
    score = metric.measure(resolution_case(mentions, predicted, gold))
    false_merges, missed_pairs = await _pair_fates(
        list(mentions), gold, predicted, result, embedder
    )

    if "E2E_ARTIFACT_DIR" not in os.environ:
        monkeypatch.setenv("E2E_ARTIFACT_DIR", str(REPORT_DIR))
    report = write_artifact(
        "resolution_quality",
        {
            "mentions": len(mentions),
            "scores": {"b_cubed_f": score, **metric.score_breakdown},
            "matches_by_tier": predicted.matches_by_tier,
            "false_merges": false_merges,
            "missed_pairs": missed_pairs,
        },
    )

    assert report["mentions"] == len(mentions)
    assert predicted.matches_by_tier.get("llm", 0) >= 1
    assert predicted.failed_llm_requests == 0
    assert score >= THRESHOLD
    assert metric.score_breakdown["pairwise_f"] >= PAIRWISE_THRESHOLD
