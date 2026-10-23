"""Models for decision records: choices, their evidence supports and reads."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from agrag.common.data_models.evidence import EvidenceKind
from agrag.common.data_models.write_result import WriteResult


DECISION_LABEL = "Decision"
SUPPORT_LABEL = "DecisionSupport"
MADE = "MADE"
HAS_SUPPORT = "HAS_SUPPORT"
DEPENDS_ON = "DEPENDS_ON"
SUPERSEDES = "SUPERSEDES"
PRECEDENT_MARKER = "precedent"


class DecisionStatus(StrEnum):
    """Lifecycle state of a decision. Only active decisions are reused."""

    ACTIVE = "active"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ReviewState(StrEnum):
    """Whether a decision's supports still hold.

    ``needs_review`` means a source changed and someone should look again. It
    does not mean the decision is false. ``unknown`` means the review state
    could not be established, so the decision is treated as needing review.
    """

    CLEAR = "clear"
    NEEDS_REVIEW = "needs_review"
    UNKNOWN = "unknown"


class ReviewReason(StrEnum):
    """Why a decision needs review."""

    SOURCE_CHANGED_DURING_RECORDING = "source_changed_during_recording"
    SOURCE_CHANGED = "source_changed"
    SOURCE_REMOVED = "source_removed"
    DEPENDENCY_REVIEW = "dependency_review"


class SupportKind(StrEnum):
    """Kind of a support that a decision cites."""

    DOCUMENT = "document"
    EVENT = "event"
    DECISION = "decision"


class DocumentSupportInput(BaseModel):
    """A passage the caller fetched, named by its evidence id.

    Attributes:
        evidence_id: An evidence id returned by search or fetch.
    """

    model_config = ConfigDict(frozen=True)
    evidence_id: str


class EventSupportInput(BaseModel):
    """An existing event of a task in the same project.

    Attributes:
        task_name: The task that holds the event.
        seq: The sequence number of the event in that task.
    """

    model_config = ConfigDict(frozen=True)
    task_name: str
    seq: int


class DecisionSupportInput(BaseModel):
    """An active decision that this decision depends on.

    Attributes:
        decision_id: The id of the active decision in the same project.
    """

    model_config = ConfigDict(frozen=True)
    decision_id: str


SupportInput = DocumentSupportInput | EventSupportInput | DecisionSupportInput


class DocumentSupport(BaseModel):
    """A stored document support, with the passage it names.

    Attributes:
        kind: Always ``document``.
        evidence_id: The evidence id the caller cited.
        document_key: The stable key of the cited document.
        document_node_id: The id of the Document node.
        content_hash_prefix: The first 16 hex characters of the cited version.
        reference_kind: Whether the id names a span or a chunk.
        char_start: Start offset of a span, or None for a chunk.
        char_end: End offset of a span, or None for a chunk.
        chunk_id: The chunk id of a chunk reference, or None for a span.
        recorded_activation_seq: The document's activation sequence number
            when the decision was recorded.
    """

    model_config = ConfigDict(frozen=True)
    kind: Literal[SupportKind.DOCUMENT]
    evidence_id: str
    document_key: str
    document_node_id: UUID
    content_hash_prefix: str
    content_hash: str
    reference_kind: EvidenceKind
    char_start: int | None = None
    char_end: int | None = None
    chunk_id: UUID | None = None
    recorded_activation_seq: int | None = None
    current: bool = True
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_explanation: str | None = None


class EventSupport(BaseModel):
    """A stored event support.

    Attributes:
        kind: Always ``event``.
        event_id: The id of the event node.
        task_name: The task that holds the event.
        seq: The sequence number of the event in that task.
    """

    model_config = ConfigDict(frozen=True)
    kind: Literal[SupportKind.EVENT]
    event_id: UUID
    task_name: str
    seq: int
    current: bool = True
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_explanation: str | None = None


class DecisionSupport(BaseModel):
    """A stored dependency on another decision.

    Attributes:
        kind: Always ``decision``.
        decision_id: The id of the decision depended on.
    """

    model_config = ConfigDict(frozen=True)
    kind: Literal[SupportKind.DECISION]
    decision_id: UUID
    current: bool = True
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_explanation: str | None = None


Support = Annotated[
    DocumentSupport | EventSupport | DecisionSupport, Field(discriminator="kind")
]


class Decision(BaseModel):
    """One recorded decision of a task.

    Attributes:
        id: Identifier derived from the task id, choice key and revision.
        task_id: The task the decision belongs to.
        task_name: The name of that task.
        choice_key: The choice inside the task that this decision settles.
        revision: 1 for the first decision of a choice, and one more for each
            supersession.
        conclusion: The conclusion. Never changed after recording.
        rationale: The stated reasoning.
        assumptions: Assumptions the decision relies on.
        open_questions: Questions left open.
        author: The agent that recorded the decision.
        status: Lifecycle state.
        review_state: Whether the supports still hold.
        review_reason: Why the decision needs review, or None.
        rejection_reason: The reason given when the decision was rejected.
        rejected_by: Who rejected the decision.
        created_at: When the decision was recorded.
        supports: The stored supports, in the order they were given.
    """

    model_config = ConfigDict(frozen=True)
    id: UUID
    task_id: UUID
    task_name: str
    choice_key: str
    revision: int
    conclusion: str
    rationale: str
    assumptions: list[str]
    open_questions: list[str]
    author: str
    status: DecisionStatus
    review_state: ReviewState
    review_reason: ReviewReason | None = None
    rejection_reason: str | None = None
    rejected_by: str | None = None
    created_at: datetime
    supports: list[Support] = Field(default_factory=list)


class DecisionReviewList(BaseModel):
    """A bounded project-scoped page of decisions requiring review."""

    model_config = ConfigDict(frozen=True)
    decisions: list[Decision] = Field(default_factory=list)
    count: int = 0
    truncated: bool = False


class SupportHistoryPage(BaseModel):
    """A bounded page of immutable support references and review transitions."""

    model_config = ConfigDict(frozen=True)
    supports: list[Support] = Field(default_factory=list)
    truncated: bool = False
    next_after_ordinal: int | None = None


class DecisionPage(BaseModel):
    """A capped list of decisions with the total that matched.

    Attributes:
        decisions: The first decisions in the page order, at most the cap.
        count: The number of decisions that matched, including hidden ones.
        truncated: Whether some matching decisions are not in ``decisions``.
    """

    model_config = ConfigDict(frozen=True)
    decisions: list[Decision] = Field(default_factory=list)
    count: int = 0
    truncated: bool = False


class DecisionPageLookup(BaseModel):
    """The result of listing a task's decisions by name.

    Attributes:
        found: Whether a task with that name exists in the project.
        page: The decisions of the task, or an empty page when not found.
    """

    model_config = ConfigDict(frozen=True)
    found: bool
    page: DecisionPage = Field(default_factory=DecisionPage)


class DecisionLookup(BaseModel):
    """The result of reading one decision by id.

    Attributes:
        found: Whether a decision with that id exists in the project.
        decision: The decision with its supports, or None when not found.
    """

    model_config = ConfigDict(frozen=True)
    found: bool
    decision: Decision | None = None


class RecordDecisionResult(WriteResult):
    """The outcome of recording a decision.

    Attributes:
        decision: The stored decision when ``recorded`` is true.
        warnings: Notes for the caller, such as a source that changed while
            the decision was recorded.
    """

    decision: Decision | None = None
    warnings: list[str] = Field(default_factory=list)


class RejectDecisionResult(WriteResult):
    """The outcome of rejecting a decision.

    Attributes:
        decision: The rejected decision when ``recorded`` is true.
    """

    decision: Decision | None = None


class ReaffirmDecisionResult(WriteResult):
    """The outcome of reaffirming a flagged decision.

    Attributes:
        decision: The reaffirmed decision when ``recorded`` is true.
    """

    decision: Decision | None = None


class DecisionHit(BaseModel):
    """A decision returned by precedent search.

    The marker says the decision is a precedent to read. The model has no field
    that says the decision applies to the current task.

    Attributes:
        decision: The decision, with its task name, status and review state.
        task_goal: The goal of the task that recorded the decision.
        marker: Always ``precedent``.
    """

    model_config = ConfigDict(frozen=True)
    decision: Decision
    task_goal: str
    marker: Literal["precedent"] = PRECEDENT_MARKER


class ConflictGroup(BaseModel):
    """Active decisions of one choice key that disagree across tasks.

    Attributes:
        choice_key: The shared choice key.
        decisions: At most the group cap of active decisions, by task name.
        truncated: Whether some decisions of the group are not shown.
    """

    model_config = ConfigDict(frozen=True)
    choice_key: str
    decisions: list[Decision]
    truncated: bool


class ConflictList(BaseModel):
    """Choice keys whose active decisions disagree across tasks.

    Attributes:
        groups: At most the group cap of conflict groups.
        truncated: Whether some conflict groups are not shown.
    """

    model_config = ConfigDict(frozen=True)
    groups: list[ConflictGroup]
    truncated: bool
