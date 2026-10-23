"""Error codes and the base result of task and decision trace writes."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class WriteErrorCode(StrEnum):
    """Fixed error codes returned by decision trace writes."""

    TASK_EXISTS = "task_exists"
    TASK_NOT_FOUND = "task_not_found"
    EVENT_NOT_FOUND = "event_not_found"
    REQUEST_ID_REUSED = "request_id_reused"
    INVALID_REQUEST_ID = "invalid_request_id"
    CHOICE_EXISTS = "choice_exists"
    SUPERSEDE_TARGET_INVALID = "supersede_target_invalid"
    EXPLANATION_REQUIRED = "explanation_required"
    SUPPORT_REQUIRED = "support_required"
    SUPPORT_MALFORMED = "support_malformed"
    SUPPORT_NOT_FETCHED = "support_not_fetched"
    SUPPORT_OUT_OF_SCOPE = "support_out_of_scope"
    SUPPORT_DOCUMENT_NOT_FOUND = "support_document_not_found"
    SUPPORT_EVENT_NOT_FOUND = "support_event_not_found"
    SUPPORT_DECISION_NOT_FOUND = "support_decision_not_found"
    DECISION_NOT_FOUND = "decision_not_found"
    DECISION_NOT_ACTIVE = "decision_not_active"
    SUPPORT_DECISION_NOT_ACTIVE = "support_decision_not_active"
    CANNOT_REVALIDATE = "cannot_revalidate"


class WriteResult(BaseModel):
    """Base outcome of a task or decision trace write.

    Attributes:
        recorded: Whether the write is in effect. A retry with the same request
            id reports the stored outcome of the first call.
        error: The fixed error code when ``recorded`` is false.
    """

    model_config = ConfigDict(frozen=True)
    recorded: bool
    error: WriteErrorCode | None = None
