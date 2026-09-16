"""Per-stage failure record and its per-call cap."""

from __future__ import annotations

import logging
from typing import NamedTuple

from pydantic import BaseModel


logger = logging.getLogger(__name__)


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


MAX_FAILURES_PER_STAGE = 200


class CappedFailures(NamedTuple):
    """A capped failure list plus the true count it was built from.

    Attributes:
        items: The failure records, truncated to the per-stage cap.
        total: How many failures the stage actually recorded, before any
            truncation.
        truncated: Whether ``items`` was cut to the per-stage cap.
    """

    items: list[StageFailure]
    total: int
    truncated: bool


def cap_failures(failures: list[StageFailure]) -> CappedFailures:
    """Return failures capped per stage, with the untruncated true count.

    Logs a warning when truncation occurs, since the capped list alone no
    longer reflects how many items actually failed.

    Args:
        failures: Every failure the stage recorded.

    Returns:
        The capped list, the true failure count, and whether the list was
        truncated.
    """
    total = len(failures)
    if total > MAX_FAILURES_PER_STAGE:
        logger.warning(
            "Stage reported %d failures; truncating to %d in the report.",
            total,
            MAX_FAILURES_PER_STAGE,
        )
        return CappedFailures(
            items=failures[:MAX_FAILURES_PER_STAGE], total=total, truncated=True
        )
    return CappedFailures(items=failures, total=total, truncated=False)
