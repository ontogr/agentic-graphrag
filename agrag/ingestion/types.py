"""Graph.add()'s result and per-stage observability types."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from agrag.common.data_models.chunk import Chunk


if TYPE_CHECKING:
    from agrag.ingestion.merge import MergePlan
else:
    MergePlan = Any


class StageFailure(BaseModel):
    """One item's failure within a pipeline stage.

    Attributes:
        item_id: The chunk id, mention id, or batch id — whichever unit
            the stage failed on.
        error_type: The exception's class name.
        error_message: The exception's message.
        trace_id: The OTel trace id correlating to the full span detail,
            when tracing is configured.
        span_id: The OTel span id within that trace.
    """

    item_id: str
    error_type: str
    error_message: str
    trace_id: str | None = None
    span_id: str | None = None


_MAX_FAILURES_PER_STAGE = 200


class IngestStats(BaseModel):
    """Ingestion-stage results. Renamed from IngestResult (ADR 0031)."""

    documents: int = 0
    sources: int = 0
    skipped: int = 0
    quarantined: int = 0
    quarantined_items: list[StageFailure] = Field(default_factory=list)


class ExtractionStats(BaseModel):
    """Extraction-stage results."""

    chunks_processed: int = 0
    entities_extracted: int = 0
    relations_extracted: int = 0
    failures: list[StageFailure] = Field(default_factory=list)


class ResolutionStats(BaseModel):
    """Resolution-stage results.

    Attributes:
        exact_match_hits: Mentions that matched an already-persisted
            entity via the global exact-match tier.
        in_batch_groups: Resolution groups the in-batch fuzzy/LLM tier
            found.
        ambiguous_count: Comparisons no comparator could confidently
            decide (ADR 0013's fail-safe: never merged).
    """

    exact_match_hits: int = 0
    in_batch_groups: int = 0
    ambiguous_count: int = 0


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
            summarization (ADR 0033's fallback-to-concatenation path still
            records one here, even though it didn't block the merge).
    """

    nodes_created: int = 0
    nodes_updated: int = 0
    nodes_merged: int = 0
    conflicts_resolved: int = 0
    failures: list[StageFailure] = Field(default_factory=list)


class StorageStats(BaseModel):
    """Storage-write-stage results.

    Attributes:
        nodes_written: Chunk and Entity nodes together, one aggregate
            count rather than a sub-count per kind — both are written in
            the same final phase, so there is one natural accounting
            point.
        relationships_written: Domain Relation and MENTIONED_IN edges
            together, for the same reason.
        failures: One record per batch write that failed, capped per
            call. A GraphStore write is a single managed transaction, so
            a failure here means the whole batch did not land, not a
            partial subset of it.
    """

    nodes_written: int = 0
    relationships_written: int = 0
    failures: list[StageFailure] = Field(default_factory=list)


class AddResult(BaseModel):
    """Graph.add()'s return type — one summary per pipeline stage.

    Attributes:
        ingestion: What today's IngestResult covered.
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

    # Back-compat proxies for code still reading IngestResult shape directly.
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


def _capped(failures: list[StageFailure]) -> list[StageFailure]:
    """Return failures truncated to _MAX_FAILURES_PER_STAGE entries."""
    return failures[:_MAX_FAILURES_PER_STAGE]
