"""Storage-write-stage stats."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agrag.ingestion.stats.stage_failure import StageFailure


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
        failures_total: Failures recorded before capping.
        failures_truncated: Whether ``failures`` was cut to the cap.
    """

    nodes_written: int = 0
    relationships_written: int = 0
    failures: list[StageFailure] = Field(default_factory=list)
    failures_total: int = 0
    failures_truncated: bool = False
