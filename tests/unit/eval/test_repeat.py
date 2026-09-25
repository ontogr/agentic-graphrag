"""Tests for MedianOfN.

Uses a scripted metric whose scores come from a shared function, so the median
logic runs with no judge. One test wraps a real GEval over a judge that holds a
live ChatOpenAI client, to check the copies MedianOfN makes under a_measure.
"""

import asyncio
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from deepeval import evaluate
from deepeval.metrics import BaseMetric, GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams
from langchain_openai import ChatOpenAI

from agrag.eval.adapter import ScoreMetric, ScoreResult
from agrag.eval.judge import ChatModelJudge
from agrag.eval.repeat import MedianOfN


def _offline_chat_model() -> ChatOpenAI:
    """Build a live chat client whose transport fails without a socket."""

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    return ChatOpenAI(
        api_key="x",
        base_url="http://x",
        max_retries=0,
        http_async_client=httpx.AsyncClient(transport=httpx.MockTransport(refuse)),
        http_client=httpx.Client(transport=httpx.MockTransport(refuse)),
    )


_CASE = LLMTestCase(input="q", actual_output="a")


class _ScriptedMetric(BaseMetric):
    """Return scores from ``script`` in call order, then keep the last state.

    ``script`` is a function, so deepcopy shares it and every copy of the
    metric draws from the same sequence. Each run sleeps after it sets its
    score, so runs that share one instance would overwrite each other.
    """

    def __init__(
        self,
        script: Callable[[], tuple[float, float]],
        threshold: float = 0.5,
    ) -> None:
        self.script = script
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        self.score, _ = self.script()
        self.reason = f"score {self.score}"
        return self.score

    async def a_measure(
        self, test_case: LLMTestCase, *args: Any, **kwargs: Any
    ) -> float:
        self.score, delay = self.script()
        self.reason = f"score {self.score}"
        await asyncio.sleep(delay)
        return self.score

    @property
    def __name__(self) -> str:
        return "Scripted"


def _script(*scores: float, delays: tuple[float, ...] = (0, 0, 0)) -> Callable:
    pairs: Iterator[tuple[float, float]] = iter(zip(scores, delays, strict=False))
    return lambda: next(pairs)


class TestMedianOfN:
    """MedianOfN reports the median of n runs of the wrapped metric."""

    def test_median_ignores_one_outlier(self) -> None:
        """Scores 0.2, 0.9, 0.8 give 0.8, and the low outlier does not fail it."""
        metric = MedianOfN(_ScriptedMetric(_script(0.2, 0.9, 0.8), threshold=0.7))

        score = metric.measure(_CASE)

        assert score == 0.8
        assert metric.score_breakdown == {"scores": [0.2, 0.9, 0.8]}
        assert metric.is_successful()

    def test_success_uses_median_not_mean(self) -> None:
        """Mean 0.7 would pass a 0.6 threshold, but the median 0.5 must fail."""
        metric = MedianOfN(_ScriptedMetric(_script(0.5, 0.5, 1.0), threshold=0.6))

        metric.measure(_CASE)

        assert metric.score == 0.5
        assert not metric.is_successful()

    def test_reason_comes_from_run_closest_to_median(self) -> None:
        """The reason describes the median run."""
        metric = MedianOfN(_ScriptedMetric(_script(0.2, 0.9, 0.8)))

        metric.measure(_CASE)

        assert metric.reason == "score 0.8"

    @pytest.mark.parametrize("n", [2, 4, 0, -1])
    def test_rejects_even_or_non_positive_n(self, n: int) -> None:
        """Only odd n has a single median."""
        with pytest.raises(ValueError, match="odd"):
            MedianOfN(_ScriptedMetric(_script(0.1)), n=n)

    def test_single_run_matches_bare_metric(self) -> None:
        """n=1 returns the wrapped metric's own result."""
        metric = MedianOfN(_ScriptedMetric(_script(0.3), threshold=0.5), n=1)

        assert metric.measure(_CASE) == 0.3
        assert not metric.is_successful()

    async def test_concurrent_runs_do_not_share_state(self) -> None:
        """Each run keeps its own score, even when the runs finish out of order."""
        script = _script(0.2, 0.9, 0.8, delays=(0.03, 0.02, 0.01))
        metric = MedianOfN(_ScriptedMetric(script))

        score = await metric.a_measure(_CASE)

        assert sorted(metric.score_breakdown["scores"]) == [0.2, 0.8, 0.9]
        assert score == 0.8

    async def test_a_measure_forwards_keyword_arguments(self) -> None:
        """evaluate() passes extra keywords such as _show_indicator."""
        metric = MedianOfN(_ScriptedMetric(_script(0.5, 0.5, 0.5)))

        assert await metric.a_measure(_CASE, _show_indicator=False) == 0.5

    async def test_copies_a_geval_that_holds_a_live_client(self) -> None:
        """A judge over a live ChatOpenAI does not break the per-run copies."""
        geval = GEval(
            name="Correctness",
            criteria="Is the answer correct?",
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            model=ChatModelJudge(_offline_chat_model(), "test-judge"),
        )
        metric = MedianOfN(geval)

        # Sockets are blocked, so the judge call fails. The copies are built
        # before that call, so the failure must not be a copy error.
        with pytest.raises(Exception) as raised:
            await metric.a_measure(_CASE)
        assert "RLock" not in str(raised.value)

    def test_runs_through_evaluate_offline(self) -> None:
        """evaluate() copies and runs MedianOfN beside a ScoreMetric."""
        metrics = [
            MedianOfN(_ScriptedMetric(_script(0.2, 0.9, 0.8))),
            ScoreMetric("plain", lambda _: ScoreResult(1.0, "ok", {})),
        ]

        result = evaluate([_CASE], metrics)

        data = {m.name: m for m in result.test_results[0].metrics_data or []}
        assert data["Median of 3 Scripted"].score == 0.8
        assert data["plain"].score == 1.0
