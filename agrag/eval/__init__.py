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
from agrag.eval.answer import (
    CitationAccuracyMetric,
    CitationScoreBreakdown,
    answer_case,
    context_precision,
    context_recall,
    correctness,
    faithfulness,
    final_answer,
)
from agrag.eval.extraction import (
    ExtractionGold,
    MicroScores,
    Scores,
    entity_quality_metric,
    extraction_case,
    micro_scores,
    relation_quality_metric,
    run_extractor,
)
from agrag.eval.judge import ChatModelJudge
from agrag.eval.repeat import MedianOfN
from agrag.eval.settings import EvalJudgeSettings


__all__ = [
    "ChatModelJudge",
    "CitationAccuracyMetric",
    "CitationScoreBreakdown",
    "EvalJudgeSettings",
    "ExtractionGold",
    "MedianOfN",
    "MicroScores",
    "ScoreMetric",
    "ScoreResult",
    "Scores",
    "answer_case",
    "context_precision",
    "context_recall",
    "correctness",
    "faithfulness",
    "final_answer",
    "entity_quality_metric",
    "extraction_case",
    "micro_scores",
    "parse_json_case",
    "relation_quality_metric",
    "run_extractor",
    "to_json_case",
]
