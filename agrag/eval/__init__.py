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
from agrag.eval.resolution import (
    ClusterAssignment,
    cluster_quality_metric,
    resolution_case,
    run_resolver,
    run_resolver_detailed,
)
from agrag.eval.settings import EvalJudgeSettings
from agrag.eval.trajectory import (
    SpanCapture,
    Trajectory,
    expected_tools_metric,
    read_trajectory,
    retry_budget_metric,
    trajectory_case,
    verifier_before_answer_metric,
)
from agrag.eval.verifier import (
    VerdictItem,
    VerdictReport,
    run_verifier,
    verdict_case,
    verdict_match_metric,
    verdict_report,
)


__all__ = [
    "ChatModelJudge",
    "CitationAccuracyMetric",
    "CitationScoreBreakdown",
    "ClusterAssignment",
    "EvalJudgeSettings",
    "ExtractionGold",
    "MedianOfN",
    "MicroScores",
    "ScoreMetric",
    "ScoreResult",
    "Scores",
    "SpanCapture",
    "Trajectory",
    "VerdictItem",
    "VerdictReport",
    "answer_case",
    "cluster_quality_metric",
    "context_precision",
    "context_recall",
    "correctness",
    "entity_quality_metric",
    "expected_tools_metric",
    "extraction_case",
    "faithfulness",
    "final_answer",
    "micro_scores",
    "parse_json_case",
    "read_trajectory",
    "relation_quality_metric",
    "resolution_case",
    "retry_budget_metric",
    "run_extractor",
    "run_resolver",
    "run_resolver_detailed",
    "run_verifier",
    "to_json_case",
    "trajectory_case",
    "verdict_case",
    "verdict_match_metric",
    "verdict_report",
    "verifier_before_answer_metric",
]
