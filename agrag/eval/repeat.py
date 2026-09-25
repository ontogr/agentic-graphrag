"""Repeat a metric and report the median score."""

import asyncio
import copy
import statistics
from typing import Any

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase


class MedianOfN(BaseMetric):
    """Run a metric ``n`` times and report the median score.

    One noisy judge call cannot flip the result. ``success`` compares the
    median with the wrapped metric's threshold. ``reason`` comes from the run
    closest to the median, and ``score_breakdown`` lists every score.

    Under ``a_measure`` the runs execute concurrently, each on its own copy of
    the metric, because metrics keep their result in ``self``. The copies share
    the judge model.

    Attributes:
        metric: The wrapped metric.
        n: The number of runs. Must be odd.
    """

    def __init__(self, metric: BaseMetric, n: int = 3) -> None:
        """Wrap ``metric`` and copy its threshold.

        Raises:
            ValueError: ``n`` is not a positive odd number.
        """
        if n < 1 or n % 2 == 0:
            raise ValueError(f"n must be a positive odd number, got {n}")
        self.metric = metric
        self.n = n
        self.threshold = 0.5 if metric.threshold is None else metric.threshold

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        """Run the wrapped metric ``n`` times in turn."""
        runs = []
        for _ in range(self.n):
            score = self.metric.measure(test_case, *args, **kwargs)
            runs.append((score, self.metric.reason))
        return self._aggregate(runs)

    async def a_measure(
        self, test_case: LLMTestCase, *args: Any, **kwargs: Any
    ) -> float:
        """Run the wrapped metric ``n`` times at once."""
        # The judge holds a live client that deepcopy cannot copy, so the memo
        # makes every copy share it. Each copy needs a fresh memo, or deepcopy
        # returns the first copy again.
        model = self.metric.model
        copies = [copy.deepcopy(self.metric, {id(model): model}) for _ in range(self.n)]
        scores = await asyncio.gather(
            *(m.a_measure(test_case, *args, **kwargs) for m in copies)
        )
        return self._aggregate(
            [(score, m.reason) for score, m in zip(scores, copies, strict=True)]
        )

    @property
    def __name__(self) -> str:
        """The metric name shown in reports."""
        return f"Median of {self.n} {self.metric.__name__}"

    def _aggregate(self, runs: list[tuple[float, str | None]]) -> float:
        scores = [score for score, _ in runs]
        median = statistics.median(scores)
        self.score = median
        self.reason = min(runs, key=lambda run: abs(run[0] - median))[1]
        self.score_breakdown = {"scores": scores}
        self.success = self.is_successful()
        return median
