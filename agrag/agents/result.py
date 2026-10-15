"""Typed result returned after a task-scoped agent run."""

from typing import Any, Literal, TypedDict

from agrag.common.data_models.evidence import FetchOutcome


class AgentTaskRef(TypedDict):
    """The task identity and latest persisted event sequence."""

    name: str
    last_event_seq: int


class AgentRunResult(TypedDict):
    """Outcome, answer, evidence references and conversation for one run."""

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
    task: AgentTaskRef
    messages: list[Any]
