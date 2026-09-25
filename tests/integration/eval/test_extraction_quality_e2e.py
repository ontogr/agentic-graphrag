"""Extraction quality regression test on a KPI-EDGAR gold slice.

Runs a real extractor over 18 hand-picked sentences of SEC filings from the KPI-EDGAR
test split (MIT licence, see ``tests/fixtures/eval/extraction/NOTICE``) and gates on
the micro F1 of entities and of relation triples, both with exact span
matching. The relaxed scores (overlap of at least 0.5) go to the report
beside them, so a gap shows a span boundary problem and not a missed entity.

The report is written to ``reports/eval/extraction_quality.json``, or to the
directory in ``E2E_ARTIFACT_DIR``. The test skips without ``LLM_*`` settings.

Each threshold is the lowest of three baseline runs minus 0.05, rounded down to
0.05. Baseline runs (entity F1, relation F1):

    run 1: 0.538, 0.209
    run 2: 0.542, 0.214
    run 3: 0.564, 0.235
"""

import os
from collections import Counter
from pathlib import Path

import pytest

from agrag.common.data_models.graph_schema import GraphSchema
from agrag.eval import (
    ExtractionGold,
    entity_quality_metric,
    micro_scores,
    relation_quality_metric,
    run_extractor,
)
from agrag.ingestion.extract import (
    BAMLExtractor,
    ExtractionLLMSettings,
    Extractor,
)
from tests.integration.e2e._artifact import write_artifact


FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "eval" / "extraction"
REPORT_DIR = Path(__file__).parents[3] / "reports" / "eval"
SYMMETRIC_LABELS = frozenset({"RELATED_VALUE"})
# Endpoints often limit concurrent requests, and a 429 fails the run.
CONCURRENCY = 2

# Minimum exact micro F1 for entities and for relations.
ENTITY_THRESHOLD = 0.45
RELATION_THRESHOLD = 0.15


def _baml_extractor() -> Extractor:
    """Build the LLM extractor, or skip when no endpoint is configured."""
    try:
        settings = ExtractionLLMSettings.from_openai_compatible_env()
    except RuntimeError:
        pytest.skip("LLM endpoint not configured")
    if not settings.clients[0].api_key:
        pytest.skip("LLM API key not configured")
    return BAMLExtractor(settings=settings)


async def test_extractor_scores_meet_thresholds_on_kpi_edgar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The extractor finds entities and relations at or above the gate."""
    extractor = _baml_extractor()
    schema = GraphSchema.model_validate_json((FIXTURE_DIR / "schema.json").read_text())
    lines = (FIXTURE_DIR / "kpi_edgar_test_slice.jsonl").read_text().splitlines()
    items = [ExtractionGold.model_validate_json(line) for line in lines]
    cases = await run_extractor(extractor, items, schema, concurrency=CONCURRENCY)

    metrics = []
    per_type: dict[str, Counter[str]] = {}
    for case in cases:
        entity_metric = entity_quality_metric()
        relation_metric = relation_quality_metric(symmetric_labels=SYMMETRIC_LABELS)
        entity_metric.measure(case)
        relation_metric.measure(case)
        metrics += [entity_metric, relation_metric]
        for label, counts in entity_metric.score_breakdown["per_label"].items():
            per_type.setdefault(label, Counter()).update(counts)
    scores = micro_scores(metrics)

    if "E2E_ARTIFACT_DIR" not in os.environ:
        monkeypatch.setenv("E2E_ARTIFACT_DIR", str(REPORT_DIR))
    report = write_artifact(
        "extraction_quality",
        {
            "items": len(items),
            "scores": scores.model_dump(),
            "entity_counts_by_type": {
                label: dict(counts) for label, counts in sorted(per_type.items())
            },
        },
    )

    assert report["items"] == len(items)
    assert scores.entities_exact.f1 >= ENTITY_THRESHOLD
    assert scores.relations_exact.f1 >= RELATION_THRESHOLD
