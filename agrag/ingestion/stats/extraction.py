"""Extraction-stage stats."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agrag.ingestion.stats.stage_failure import StageFailure


class ExtractionStats(BaseModel):
    """Extraction-stage results.

    Attributes:
        chunks_processed: Chunks the stage ran the extractor on.
        entities_extracted: Entities the extractor returned.
        relations_extracted: Relations the extractor returned.
        failures: Per-item failures, capped per call.
        failures_total: Failures recorded before capping.
        failures_truncated: Whether ``failures`` was cut to the cap.
    """

    chunks_processed: int = 0
    entities_extracted: int = 0
    relations_extracted: int = 0
    failures: list[StageFailure] = Field(default_factory=list)
    failures_total: int = 0
    failures_truncated: bool = False
