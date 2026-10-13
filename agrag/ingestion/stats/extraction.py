"""Extraction-stage stats."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agrag.common.data_models.stage_failure import StageFailure
from agrag.ingestion.stats.dropped import DroppedCount


class ExtractionStats(BaseModel):
    """Extraction-stage results.

    Attributes:
        chunks_processed: Chunks the stage read. In ``llm`` mode this counts
            every chunk, including chunks skipped for having fewer than
            ``min_escalation_words`` words. ``EscalationReport.skipped_short``
            gives that skipped count.
        entities_extracted: Entities the extractor returned.
        relations_extracted: Relations the extractor returned.
        dropped: Extractor discards counted by kind, label and reason. Always
            filled, whether candidates are on or off.
        candidates_written: Candidates this run wrote to the graph.
        candidates_skipped: Discarded items not written because a reviewer
            settled the key or both relation ends merged into one entity.
        failures: Per-item failures, capped per call.
        failures_total: Failures recorded before capping.
        failures_truncated: Whether ``failures`` was cut to the cap.
    """

    chunks_processed: int = 0
    entities_extracted: int = 0
    relations_extracted: int = 0
    dropped: list[DroppedCount] = Field(default_factory=list)
    candidates_written: int = 0
    candidates_skipped: int = 0
    failures: list[StageFailure] = Field(default_factory=list)
    failures_total: int = 0
    failures_truncated: bool = False
