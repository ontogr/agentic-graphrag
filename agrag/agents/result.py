"""Typed result returned after a task-scoped agent run."""

from typing import Any, Literal, TypedDict

from agrag.common.data_models.evidence import FetchOutcome


class AgentTaskRef(TypedDict):
    """The task identity and latest persisted event sequence."""

    name: str
    last_event_seq: int


class AgentRunResult(TypedDict):
    """Outcome, answer, evidence references and conversation for one run.

    Attributes:
        answer: Final answer text.
        status: Outcome after evidence, write and budget checks.
        citations: Complete fetched evidence supporting the answer.
        invalid_citations: Cited evidence ids that did not pass validation.
        recording_failures: Descriptions of task writes that did not complete.
        task: Task name and latest persisted event sequence.
        messages: Messages produced by the agent.
    """

    answer: str
    status: Literal[
        "answered",
        "insufficient_evidence",
        "partial_retrieval",
        "partial",
        "recording_failed",
        "budget_exhausted",
    ]
    citations: list[FetchOutcome]
    invalid_citations: list[str]
    recording_failures: list[str]
    task: AgentTaskRef
    messages: list[Any]
