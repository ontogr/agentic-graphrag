"""Graph.consolidate()'s result type."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agrag.common.data_models.stage_failure import StageFailure
from agrag.ingestion.resolved_entities import MatchDecision


class ConsolidationReport(BaseModel):
    """Report from Graph.consolidate().

    Attributes:
        would_match: Confirmed non-exact matches found, whether applied or not.
        applied: Whether the matches were applied.
        failures: Failures writing a match graph or rebuilding resolved entities.
            Always empty when apply is False.
        ambiguous_count: LLM verdicts that came back uncertain. These
            pairs never merge.
    """

    would_match: list[MatchDecision] = Field(default_factory=list)
    applied: bool = False
    failures: list[StageFailure] = Field(default_factory=list)
    ambiguous_count: int = 0
