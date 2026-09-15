"""Graph.consolidate()'s result type."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from agrag.ingestion.stats import StageFailure


if TYPE_CHECKING:
    from agrag.ingestion.merge import MergePlan
else:
    MergePlan = Any


class ConsolidationReport(BaseModel):
    """Report from Graph.consolidate().

    Attributes:
        would_merge: The merge plans found, whether applied or not.
        applied: Whether the plans were applied.
        failures: Failures re-embedding an applied survivor's final text.
            Always empty when apply is False.
    """

    would_merge: list[MergePlan] = Field(default_factory=list)
    applied: bool = False
    failures: list[StageFailure] = Field(default_factory=list)
