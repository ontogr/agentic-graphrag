"""Reports returned by Graph pipeline operations.

One class per module under this package; this init re-exports them so
``from agrag.ingestion.reports import AddResult`` keeps working.
"""

from agrag.ingestion.reports.add_result import AddResult
from agrag.ingestion.reports.community_detection_report import CommunityDetectionReport
from agrag.ingestion.reports.consolidation_report import ConsolidationReport


__all__ = [
    "AddResult",
    "CommunityDetectionReport",
    "ConsolidationReport",
]
