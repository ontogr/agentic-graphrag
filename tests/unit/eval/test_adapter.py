"""Tests for ScoreMetric and the JSON test-case helpers.

The evaluate() test runs DeepEval end to end with no network: the metric is a
plain scoring function, so no judge model is involved.
"""

import pytest
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from pydantic import BaseModel

from agrag.eval.adapter import ScoreMetric, ScoreResult, parse_json_case, to_json_case


class _Span(BaseModel):
    label: str
    start: int
    end: int


class _Gold(BaseModel):
    spans: list[_Span]
    note: str | None = None


def _exact(test_case: LLMTestCase) -> ScoreResult:
    actual, expected = parse_json_case(test_case, _Gold)
    hits = sum(span in expected.spans for span in actual.spans)
    return ScoreResult(
        hits / len(expected.spans), f"{hits} of {len(expected.spans)}", {"hits": hits}
    )


class TestScoreMetric:
    """ScoreMetric reports a scorer's result through DeepEval."""

    def test_reports_score_reason_and_breakdown(self) -> None:
        """Measure copies every field of the scorer result."""
        metric = ScoreMetric("span-f1", lambda _: ScoreResult(0.8, "ok", {"tp": 4}))

        score = metric.measure(LLMTestCase(input="x", actual_output="y"))

        assert (score, metric.reason, metric.score_breakdown) == (0.8, "ok", {"tp": 4})
        assert metric.is_successful()

    def test_fails_below_threshold(self) -> None:
        """Success is false when the score is under the threshold."""
        metric = ScoreMetric("m", lambda _: ScoreResult(0.4, "low", {}), threshold=0.5)

        metric.measure(LLMTestCase(input="x", actual_output="y"))

        assert not metric.is_successful()

    def test_reports_scorer_exception(self) -> None:
        """A failing scorer raises and records the error, not a score of 0."""

        def broken(_: LLMTestCase) -> ScoreResult:
            raise RuntimeError("bad gold data")

        metric = ScoreMetric("m", broken)

        with pytest.raises(RuntimeError, match="bad gold data"):
            metric.measure(LLMTestCase(input="x", actual_output="y"))
        assert metric.error == "bad gold data"
        assert not metric.is_successful()

    async def test_a_measure_matches_measure(self) -> None:
        """a_measure returns the same result as measure."""
        metric = ScoreMetric("m", lambda _: ScoreResult(1.0, "r", {}))

        assert await metric.a_measure(LLMTestCase(input="x", actual_output="y")) == 1.0

    def test_runs_through_evaluate_offline(self) -> None:
        """evaluate() runs the metric and reports score, reason and breakdown."""
        span = _Span(label="Org", start=0, end=4)
        case = to_json_case(
            "chunk",
            _Gold(spans=[span, _Span(label="Org", start=9, end=12)]),
            _Gold(spans=[span, span.model_copy(update={"start": 5})]),
        )

        result = evaluate([case], [ScoreMetric("span-hits", _exact)])

        metrics_data = result.test_results[0].metrics_data or []
        data = metrics_data[0]
        assert data.name == "span-hits"
        assert data.score == 0.5
        assert data.reason == "1 of 2"


class TestJsonCase:
    """to_json_case and parse_json_case round trip structured data."""

    def test_round_trip_keeps_every_field(self) -> None:
        """Nested models come back equal."""
        actual = _Gold(spans=[_Span(label="A", start=1, end=2)], note="n")
        expected = _Gold(spans=[_Span(label="B", start=3, end=4)])

        case = to_json_case("q", actual, expected)
        parsed = parse_json_case(case, _Gold)

        assert case.input == "q"
        assert parsed == (actual, expected)

    def test_rejects_case_without_outputs(self) -> None:
        """A plain case has nothing to parse."""
        with pytest.raises(ValueError, match="actual_output"):
            parse_json_case(LLMTestCase(input="q"), _Gold)
