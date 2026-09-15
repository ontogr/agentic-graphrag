"""Extraction-stage stats."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agrag.ingestion.stats.stage_failure import StageFailure


class ExtractionStats(BaseModel):
    """Extraction-stage results."""

    chunks_processed: int = 0
    entities_extracted: int = 0
    relations_extracted: int = 0
    failures: list[StageFailure] = Field(default_factory=list)
