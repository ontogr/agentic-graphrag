"""Public evaluation metrics for agrag, built on DeepEval and AgentEvals.

Needs the ``eval`` extra: ``pip install 'agentic-graphrag[eval]'``.
"""

try:
    import deepeval  # noqa: F401
except ImportError as error:
    raise ImportError(
        "agrag.eval needs the 'eval' extra: pip install 'agentic-graphrag[eval]'"
    ) from error

from agrag.eval.adapter import ScoreMetric, ScoreResult, parse_json_case, to_json_case
from agrag.eval.judge import ChatModelJudge
from agrag.eval.repeat import MedianOfN
from agrag.eval.settings import EvalJudgeSettings


__all__ = [
    "ChatModelJudge",
    "EvalJudgeSettings",
    "MedianOfN",
    "ScoreMetric",
    "ScoreResult",
    "parse_json_case",
    "to_json_case",
]
