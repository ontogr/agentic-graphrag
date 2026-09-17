"""Per-stage observability types for the ingestion pipeline.

One class per module under this package; this init re-exports them so
``from agrag.ingestion.stats import StageFailure`` keeps working.
"""

from agrag.ingestion.stats.extraction import ExtractionStats
from agrag.ingestion.stats.ingest import IngestStats
from agrag.ingestion.stats.merge import MergeStats
from agrag.ingestion.stats.resolution import ResolutionStats
from agrag.ingestion.stats.stage_failure import (
    MAX_FAILURES_PER_STAGE,
    CappedFailures,
    StageFailure,
    cap_failures,
)
from agrag.ingestion.stats.storage import StorageStats


__all__ = [
    "CappedFailures",
    "ExtractionStats",
    "IngestStats",
    "MAX_FAILURES_PER_STAGE",
    "MergeStats",
    "ResolutionStats",
    "StageFailure",
    "StorageStats",
    "cap_failures",
]
