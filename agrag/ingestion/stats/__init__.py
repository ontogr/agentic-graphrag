"""Per-stage observability types for the ingestion pipeline.

One class per module under this package; this init re-exports them so
``from agrag.ingestion.stats import ExtractionStats`` keeps working.
``StageFailure``/``CappedFailures``/``cap_failures``/``MAX_FAILURES_PER_STAGE``
live in ``agrag.common.data_models.stage_failure`` -- a shared model used
outside the ingestion pipeline too -- and are not re-exported here.
"""

from agrag.ingestion.stats.chunking import ChunkingStats
from agrag.ingestion.stats.extraction import ExtractionStats
from agrag.ingestion.stats.ingest import IngestStats
from agrag.ingestion.stats.merge import MergeStats
from agrag.ingestion.stats.resolution import ResolutionStats
from agrag.ingestion.stats.storage import StorageStats


__all__ = [
    "ChunkingStats",
    "ExtractionStats",
    "IngestStats",
    "MergeStats",
    "ResolutionStats",
    "StorageStats",
]
