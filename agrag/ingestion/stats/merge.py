"""Merge-stage stats."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agrag.ingestion.stats.stage_failure import StageFailure


class MergeStats(BaseModel):
    """Merge-stage results.

    Attributes:
        nodes_created: Brand-new entities materialized this call.
        nodes_updated: Existing entities that absorbed new mention data
            without tombstoning anything.
        nodes_merged: Entities tombstoned into a survivor this call.
        conflicts_resolved: Total property/description conflicts resolved
            across every merge this call performed.
        failures: Includes an LLM failure during description
            summarization. The merge still falls back to concatenation and
            completes, but the failure is recorded here.
        failures_total: Failures recorded before capping.
        failures_truncated: Whether ``failures`` was cut to the cap.
    """

    nodes_created: int = 0
    nodes_updated: int = 0
    nodes_merged: int = 0
    conflicts_resolved: int = 0
    failures: list[StageFailure] = Field(default_factory=list)
    failures_total: int = 0
    failures_truncated: bool = False
