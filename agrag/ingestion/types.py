"""Compatibility shim for the pre-split ingestion types.

``agrag.ingestion.types`` previously housed every ingestion result and
per-stage stats type. They now live in ``agrag.ingestion.stats`` and
``agrag.ingestion.reports``. This module re-exports them so
``from agrag.ingestion.types import AddResult`` keeps working while
callers migrate. New code should import from the new locations directly.
"""

from agrag.ingestion.reports import (
    AddResult,
    CommunityDetectionReport,
    ConsolidationReport,
)
from agrag.ingestion.stats import (
    MAX_FAILURES_PER_STAGE,
    CappedFailures,
    ExtractionStats,
    IngestStats,
    MergeStats,
    ResolutionStats,
    StageFailure,
    StorageStats,
    cap_failures,
)


__all__ = [
    "AddResult",
    "CappedFailures",
    "CommunityDetectionReport",
    "ConsolidationReport",
    "ExtractionStats",
    "IngestStats",
    "MAX_FAILURES_PER_STAGE",
    "MergeStats",
    "ResolutionStats",
    "StageFailure",
    "StorageStats",
    "cap_failures",
]
