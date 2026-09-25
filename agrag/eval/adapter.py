"""Adapters that let plain scoring functions report through DeepEval."""

from collections.abc import Callable
from typing import Any, NamedTuple, TypeVar

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase
from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


class ScoreResult(NamedTuple):
    """The outcome of one scoring function call.

    Attributes:
        score: The score, normally between 0 and 1.
        reason: A short explanation shown in DeepEval reports.
        breakdown: Extra numbers behind the score, such as per-class values.
    """

    score: float
    reason: str
    breakdown: dict[str, Any]


class ScoreMetric(BaseMetric):
    """A DeepEval metric backed by a plain scoring function.

    Use it for scores that DeepEval does not compute, such as F1 from
    scikit-learn, so they report through the same ``evaluate()`` call.
    If the scorer raises, the error is stored in ``error`` and raised again.

    Attributes:
        name: The metric name shown in reports.
        scorer: The function that turns a test case into a ``ScoreResult``.
        threshold: The minimum score that counts as success.
    """

    def __init__(
        self,
        name: str,
        scorer: Callable[[LLMTestCase], ScoreResult],
        threshold: float = 0.5,
    ) -> None:
        """Bind the name, scorer and threshold."""
        self.name = name
        self.scorer = scorer
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        """Run the scorer and record its score, reason and breakdown."""
        try:
            result = self.scorer(test_case)
        except Exception as error:
            self.error = str(error)
            self.success = False
            raise
        self.error = None
        self.score = result.score
        self.reason = result.reason
        self.score_breakdown = result.breakdown
        self.success = self.is_successful()
        return self.score

    async def a_measure(
        self, test_case: LLMTestCase, *args: Any, **kwargs: Any
    ) -> float:
        """Run ``measure``; scoring functions are synchronous."""
        return self.measure(test_case, *args, **kwargs)

    @property
    def __name__(self) -> str:
        """The metric name shown in reports."""
        return self.name


def to_json_case(input: str, actual: BaseModel, expected: BaseModel) -> LLMTestCase:  # noqa: A002
    """Build a test case that carries structured data as JSON.

    ``LLMTestCase`` has no field for structured gold data, so both models are
    serialized to JSON in ``actual_output`` and ``expected_output``. The JSON
    also shows in DeepEval reports.

    Args:
        input: The input text, such as a question or a chunk.
        actual: The system output.
        expected: The gold data.
    """
    return LLMTestCase(
        input=input,
        actual_output=actual.model_dump_json(),
        expected_output=expected.model_dump_json(),
    )


def parse_json_case(
    test_case: LLMTestCase, model: type[ModelT]
) -> tuple[ModelT, ModelT]:
    """Read the ``(actual, expected)`` models back from a JSON test case.

    Args:
        test_case: A case built by ``to_json_case``.
        model: The pydantic model both outputs were serialized from.
    """
    if test_case.actual_output is None or test_case.expected_output is None:
        raise ValueError("test case needs actual_output and expected_output")
    return (
        model.model_validate_json(test_case.actual_output),
        model.model_validate_json(test_case.expected_output),
    )
