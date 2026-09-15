"""Removed: the ingestion result types moved to their own modules.

Per-stage stats live in ``agrag.ingestion.stats`` and pipeline reports
in ``agrag.ingestion.reports``. Importing this module raises
``ImportError`` with the new paths.
"""

raise ImportError(
    "agrag.ingestion.types was removed. Import per-stage stats from "
    "agrag.ingestion.stats and pipeline reports from "
    "agrag.ingestion.reports."
)
