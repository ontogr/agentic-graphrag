"""Models for project-scoped event redaction and task deletion."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RetentionErrorCode(StrEnum):
    """Fixed error codes returned by retention operations."""

    EVENT_NOT_FOUND = "event_not_found"
    TASK_NOT_FOUND = "task_not_found"
    REQUEST_ID_REUSED = "request_id_reused"
    INVALID_REQUEST_ID = "invalid_request_id"


class RetentionResult(BaseModel):
    """Outcome of a retention operation."""

    model_config = ConfigDict(frozen=True)
    recorded: bool
    error: RetentionErrorCode | None = None
    affected_decision_ids: list[str] = Field(default_factory=list)
