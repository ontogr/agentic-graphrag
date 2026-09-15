"""Per-stage observability types for the ingestion pipeline.

One class per module under this package; this init re-exports them so
``from agrag.ingestion.stats import StageFailure`` keeps working.
"""

from agrag.ingestion.stats.extraction import ExtractionStats
from agrag.ingestion.stats.ingest import IngestStats
from agrag.ingestion.stats.merge import MergeStats
from agrag.ingestion.stats.resolution import ResolutionStats
from agrag.ingestion.stats.stage_failure import (
    _MAX_FAILURES_PER_STAGE,
    StageFailure,
    _capped,
)
from agrag.ingestion.stats.storage import StorageStats


__all__ = [
    "ExtractionStats",
    "IngestStats",
    "MergeStats",
    "ResolutionStats",
    "StageFailure",
    "StorageStats",
    "_MAX_FAILURES_PER_STAGE",
    "_capped",
]
