"""Graph.consolidate()'s result type."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agrag.ingestion.materialize import MatchDecision
from agrag.ingestion.stats import StageFailure


class ConsolidationReport(BaseModel):
    """Report from Graph.consolidate().

    Attributes:
        would_match: Confirmed non-exact matches found, whether applied or not.
        applied: Whether the matches were materialized.
        failures: Failures writing a match graph or resolved materialization.
            Always empty when apply is False.
        ambiguous_count: LLM verdicts that came back uncertain. These
            pairs never merge.
    """

    would_match: list[MatchDecision] = Field(default_factory=list)
    applied: bool = False
    failures: list[StageFailure] = Field(default_factory=list)
    ambiguous_count: int = 0
