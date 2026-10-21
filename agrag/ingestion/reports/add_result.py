"""Graph.add()'s result type."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agrag.common.data_models.chunk import Chunk
from agrag.ingestion.reports.escalation_report import EscalationReport
from agrag.ingestion.stats import (
    ChunkingStats,
    ExtractionStats,
    IngestStats,
    MergeStats,
    ResolutionStats,
    StorageStats,
)


class AddResult(BaseModel):
    """Return type of Graph.add(). One summary per pipeline stage.

    Attributes:
        ingestion: Ingestion-stage results.
        chunking: The chunker each document got and the chunks it made.
        extraction: Extractor output across every chunk this call
            processed.
        escalation: How many chunks the LLM extractor read, how many the
            budget left to the first extractor, how many escalations failed,
            and the wall time of each phase. Only the chunk count and the
            first-phase time are set when the graph has no LLM extractor.
        resolution: Resolution's match counts and resolver batch progress.
        merge: What merge mechanics did with resolution's groups.
        storage: What made it to GraphStore, and what didn't.
        chunks: Every Chunk this call produced. Empty unless
            return_chunks=True — holding full chunk text for a large
            corpus is a real memory cost most callers don't need paid
            for.
    """

    ingestion: IngestStats = Field(default_factory=IngestStats)
    chunking: ChunkingStats = Field(default_factory=ChunkingStats)
    extraction: ExtractionStats = Field(default_factory=ExtractionStats)
    escalation: EscalationReport = Field(default_factory=EscalationReport)
    resolution: ResolutionStats = Field(default_factory=ResolutionStats)
    merge: MergeStats = Field(default_factory=MergeStats)
    storage: StorageStats = Field(default_factory=StorageStats)
    chunks: list[Chunk] = Field(default_factory=list)
