"""Models for durable task state: tasks, raw events, steps and resume views."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from agrag.common.data_models.decision import ConflictGroup, Decision


TASK_LABEL = "MemoryTask"
EVENT_LABEL = "MemoryEvent"
STEP_LABEL = "MemoryStep"
REQUEST_LABEL = "MemoryRequest"
PROJECT_LABEL = "MemoryProject"
HAS_EVENT = "HAS_EVENT"
HAS_STEP = "HAS_STEP"


class TaskStatus(StrEnum):
    """Lifecycle state of a task."""

    OPEN = "open"
    DONE = "done"


class EventKind(StrEnum):
    """Kind of a raw event appended to a task."""

    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    NOTE = "note"


class StepState(StrEnum):
    """State of a step. Resume reruns every step that is not completed."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class StepKind(StrEnum):
    """Broad category of a step."""

    READ = "read"
    ANALYSIS = "analysis"
    OTHER = "other"


class MemoryErrorCode(StrEnum):
    """Fixed error codes returned by task memory operations."""

    TASK_EXISTS = "task_exists"
    TASK_NOT_FOUND = "task_not_found"
    EVENT_NOT_FOUND = "event_not_found"
    REQUEST_ID_REUSED = "request_id_reused"
    INVALID_REQUEST_ID = "invalid_request_id"


class Task(BaseModel):
    """A named unit of work inside one project.

    Attributes:
        id: Identifier derived from the project id and the task name.
        project_id: The project that owns the task.
        name: Task name, unique within the project.
        goal: The goal given when the task was created.
        status: Lifecycle state.
        event_seq: The sequence number of the last event appended, or 0.
        author: The agent that created the task.
        created_at: When the task was created.
    """

    model_config = ConfigDict(frozen=True)
    id: UUID
    project_id: str
    name: str
    goal: str
    status: TaskStatus
    event_seq: int
    author: str
    created_at: datetime


class Event(BaseModel):
    """One raw event appended to a task.

    Attributes:
        id: Identifier derived from the task id and the sequence number.
        task_id: The task the event belongs to.
        seq: Gapless position of the event in its task, starting at 1.
        kind: Kind of event.
        role: Speaker role for a message, or None.
        name: Tool or source name for a tool event, or None.
        payload: Stored event text. Cut to the payload limit when
            ``truncated`` is true.
        payload_sha256: SHA-256 of the full text, before any cut.
        truncated: Whether the stored payload is shorter than the full text.
        author: The agent that recorded the event.
        at: When the event was recorded.
    """

    model_config = ConfigDict(frozen=True)
    id: UUID
    task_id: UUID
    seq: int
    kind: EventKind
    role: str | None
    name: str | None
    payload: str
    payload_sha256: str
    truncated: bool
    author: str
    at: datetime


class Step(BaseModel):
    """A named step of a task with an explicit state.

    Attributes:
        id: Identifier derived from the task id and the step name.
        task_id: The task the step belongs to.
        name: Step name, unique within the task.
        kind: Broad category of the step.
        state: Current state.
        result_event_seq: Sequence number of the event that holds the step's
            result, or None.
        updated_seq: The task's event sequence number when the step was last
            set.
    """

    model_config = ConfigDict(frozen=True)
    id: UUID
    task_id: UUID
    name: str
    kind: StepKind
    state: StepState
    result_event_seq: int | None
    updated_seq: int


class StepSummary(BaseModel):
    """The fields of a step that a resume view shows.

    Attributes:
        name: Step name.
        kind: Broad category of the step.
        state: Current state.
        result_event_seq: Sequence number of the result event, or None.
    """

    model_config = ConfigDict(frozen=True)
    name: str
    kind: StepKind
    state: StepState
    result_event_seq: int | None


class TaskView(BaseModel):
    """A bounded resume view of one task. It never includes event bodies.

    Attributes:
        task_name: Task name.
        goal: The task goal.
        status: Lifecycle state.
        last_event_seq: The sequence number of the last event, or 0.
        steps: Shown steps grouped by state. Every state is a key, in the
            order of ``STEP_STATE_ORDER``. The shown steps are capped across
            all states.
        step_counts: Number of steps in each state, including steps that the
            cap hides. Every state is a key.
        steps_truncated: Whether some steps are hidden by the cap.
        decisions: Active decisions, newest first, capped at 20.
        review_decisions: Active decisions needing review, capped at 20.
        conflicts: Conflicting choices that include this task, capped at 10.
    """

    model_config = ConfigDict(frozen=True)
    task_name: str
    goal: str
    status: TaskStatus
    last_event_seq: int
    steps: dict[StepState, list[StepSummary]]
    step_counts: dict[StepState, int]
    steps_truncated: bool
    decisions: list[Decision] = Field(default_factory=list)
    decision_count: int = 0
    decisions_truncated: bool = False
    review_decisions: list[Decision] = Field(default_factory=list)
    conflicts: list[ConflictGroup] = Field(default_factory=list)
    conflicts_truncated: bool = False


class TaskLookup(BaseModel):
    """The result of reading a task view by name.

    Attributes:
        found: Whether a task with that name exists in the project.
        view: The resume view, or None when the task is not found.
    """

    model_config = ConfigDict(frozen=True)
    found: bool
    view: TaskView | None = None


class EventPage(BaseModel):
    """One page of events of a task, in sequence order.

    Attributes:
        found: Whether the task exists in the project.
        events: The events after the requested sequence number.
        truncated: Whether more events follow this page.
        next_after_seq: The ``after_seq`` value that fetches the next page,
            or None when no events follow.
    """

    model_config = ConfigDict(frozen=True)
    found: bool
    events: list[Event]
    truncated: bool
    next_after_seq: int | None = None


class WriteResult(BaseModel):
    """Base outcome of a task memory write.

    Attributes:
        recorded: Whether the write is in effect. A retry with the same request
            id reports the stored outcome of the first call.
        error: The fixed error code when ``recorded`` is false.
    """

    model_config = ConfigDict(frozen=True)
    recorded: bool
    error: MemoryErrorCode | None = None


class CreateTaskResult(WriteResult):
    """The outcome of creating or reusing a task.

    Attributes:
        task: The task when ``recorded`` is true.
    """

    task: Task | None = None


class RecordEventResult(WriteResult):
    """The outcome of appending one event.

    Attributes:
        event: The appended event when ``recorded`` is true.
    """

    event: Event | None = None


class SetStepResult(WriteResult):
    """The outcome of creating or updating a step.

    Attributes:
        step: The step when ``recorded`` is true.
    """

    step: Step | None = None


# The order in which resume views list steps. Steps that still need work come
# first, so a cap on the shown steps hides completed steps before open ones.
STEP_STATE_ORDER: tuple[StepState, ...] = (
    StepState.IN_PROGRESS,
    StepState.FAILED,
    StepState.UNKNOWN,
    StepState.NOT_STARTED,
    StepState.COMPLETED,
)
