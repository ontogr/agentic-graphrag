"""Per-stage failure record and its per-call cap."""

from __future__ import annotations

from pydantic import BaseModel


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


def _capped(failures: list[StageFailure]) -> list[StageFailure]:
    """Return failures truncated to _MAX_FAILURES_PER_STAGE entries."""
    return failures[:_MAX_FAILURES_PER_STAGE]
