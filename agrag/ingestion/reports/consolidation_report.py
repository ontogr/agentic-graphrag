"""Graph.consolidate()'s result type."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.ingestion.stats import StageFailure


class ConsolidationReport(BaseModel):
    """Report from Graph.consolidate().

    Attributes:
        would_merge: The resolved components found, whether applied or not.
        applied: Whether the plans were applied.
        failures: Failures re-embedding an applied survivor's final text.
            Always empty when apply is False.
    """

    would_merge: list[ResolvedEntity] = Field(default_factory=list)
    applied: bool = False
    failures: list[StageFailure] = Field(default_factory=list)
