"""Ingestion-stage stats."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agrag.ingestion.stats.stage_failure import StageFailure


class IngestStats(BaseModel):
    """Ingestion-stage results."""

    documents: int = 0
    sources: int = 0
    skipped: int = 0
    quarantined: int = 0
    quarantined_items: list[StageFailure] = Field(default_factory=list)
