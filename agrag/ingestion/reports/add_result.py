"""Graph.add()'s result type."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agrag.common.data_models.chunk import Chunk
from agrag.ingestion.stats import (
    ExtractionStats,
    IngestStats,
    MergeStats,
    ResolutionStats,
    StageFailure,
    StorageStats,
)


class AddResult(BaseModel):
    """Graph.add()'s return type — one summary per pipeline stage.

    Attributes:
        ingestion: Ingestion-stage results.
        extraction: Extractor output across every chunk this call
            processed.
        resolution: Resolution's tier-by-tier match counts.
        merge: What merge mechanics did with resolution's groups.
        storage: What made it to GraphStore, and what didn't.
        chunks: Every Chunk this call produced. Empty unless
            return_chunks=True — holding full chunk text for a large
            corpus is a real memory cost most callers don't need paid
            for.
    """

    ingestion: IngestStats = Field(default_factory=IngestStats)
    extraction: ExtractionStats = Field(default_factory=ExtractionStats)
    resolution: ResolutionStats = Field(default_factory=ResolutionStats)
    merge: MergeStats = Field(default_factory=MergeStats)
    storage: StorageStats = Field(default_factory=StorageStats)
    chunks: list[Chunk] = Field(default_factory=list)

    @property
    def documents(self) -> int:
        """Proxy to ingestion.documents for backward compatibility."""
        return self.ingestion.documents

    @property
    def sources(self) -> int:
        """Proxy to ingestion.sources for backward compatibility."""
        return self.ingestion.sources

    @property
    def skipped(self) -> int:
        """Proxy to ingestion.skipped for backward compatibility."""
        return self.ingestion.skipped

    @property
    def quarantined(self) -> int:
        """Proxy to ingestion.quarantined for backward compatibility."""
        return self.ingestion.quarantined

    @property
    def quarantined_items(self) -> list[StageFailure]:
        """Proxy to ingestion.quarantined_items for backward compatibility."""
        return self.ingestion.quarantined_items
