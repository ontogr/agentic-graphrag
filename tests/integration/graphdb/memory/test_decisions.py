"""Decision writes, source supports, project scope and precedent reads."""

import asyncio

import pytest

from agrag.common.data_models.decision import (
    DecisionSupportInput,
    DocumentSupport,
    DocumentSupportInput,
    EventSupportInput,
    ReviewState,
)
from agrag.common.data_models.evidence import EvidenceSearchMode, FetchStatus
from agrag.common.data_models.memory_result import MemoryErrorCode
from agrag.common.data_models.task import EventKind
from agrag.evidence import fetch_evidence, search_evidence
from agrag.memory.decisions import DecisionMemory
from agrag.memory.tasks import TaskMemory
from tests.integration.retrieval.evidence._corpus import (
    BagOfWordsEmbedder,
    make_document,
)


@pytest.mark.parametrize(
    "support_case", ["no_support", "not_fetched", "malformed", "foreign_event"]
)
async def test_refuses_decisions_without_project_scoped_fetched_support(
    store, project, other_project, support_case
):
    """A decision cannot cite absent or out-of-project evidence."""
    task_memory = TaskMemory(store, project_id=project, agent_id="agent")
    await task_memory.create_task("task", "goal")
    decisions = DecisionMemory(store, project_id=project, agent_id="agent")
    if support_case == "no_support":
        supports, fetched = [], []
    elif support_case == "malformed":
        supports, fetched = [DocumentSupportInput(evidence_id="ev1:s:bad")], []
    elif support_case == "not_fetched":
        supports = [
            DocumentSupportInput(
                evidence_id="ev1:s:00000000-0000-0000-0000-000000000001:"
                "0123456789abcdef:1-2"
            )
        ]
        fetched = []
    else:
        foreign = TaskMemory(store, project_id=other_project, agent_id="agent")
        await foreign.create_task("foreign", "goal")
        event = await foreign.record_event("foreign", EventKind.NOTE, payload="source")
        supports = [EventSupportInput(task_name="foreign", seq=event.event.seq)]
        fetched = []

    result = await decisions.record_decision(
        "task",
        "choice",
        "answer",
        "reason",
        supports=supports,
        fetched_evidence=fetched,
    )

    expected = {
        "no_support": MemoryErrorCode.SUPPORT_REQUIRED,
        "not_fetched": MemoryErrorCode.SUPPORT_NOT_FETCHED,
        "malformed": MemoryErrorCode.SUPPORT_MALFORMED,
        "foreign_event": MemoryErrorCode.SUPPORT_EVENT_NOT_FOUND,
    }[support_case]
    assert not result.recorded
    assert result.error is expected


async def test_decisions_require_fetched_documents_and_support_events(
    store, project, documents
):
    """Stored records retain typed source links and currency at write time."""
    task = TaskMemory(store, project_id=project, agent_id="agent")
    await task.create_task("analysis", "choose a harbor")
    event = await task.record_event("analysis", EventKind.NOTE, payload="checked log")
    found = await search_evidence(
        store,
        BagOfWordsEmbedder(),
        "harbor",
        mode=EvidenceSearchMode.LEXICAL,
        scope=frozenset({documents.harbor}),
        limit=5,
    )
    evidence_id = found.hits[0].evidence_id
    fetched = await fetch_evidence(
        store, [evidence_id], scope=frozenset({documents.harbor}), max_chars=500
    )
    assert fetched[0].status is FetchStatus.OK
    memory = DecisionMemory(store, project_id=project, agent_id="agent")

    recorded = await memory.record_decision(
        "analysis",
        "port",
        "Use the north harbor",
        "The log names it.",
        supports=[
            DocumentSupportInput(evidence_id=evidence_id),
            EventSupportInput(task_name="analysis", seq=event.event.seq),
        ],
        fetched_evidence=fetched,
        assumptions=["The log is current"],
        open_questions=["Is access still open?"],
    )

    assert recorded.recorded
    assert recorded.decision.author == "agent"
    assert recorded.decision.assumptions == ["The log is current"]
    assert [support.kind.value for support in recorded.decision.supports] == [
        "document",
        "event",
    ]
    assert recorded.decision.review_state is ReviewState.CLEAR


async def test_supersede_reject_search_conflicts_and_task_view(
    store, project, other_project
):
    """Supersession keeps history; searches expose precedents, not applicability."""
    task = TaskMemory(store, project_id=project, agent_id="agent")
    await task.create_task("first", "choose a route")
    await task.create_task("second", "choose a route")
    first_event = await task.record_event("first", EventKind.NOTE, payload="checked")
    second_event = await task.record_event("second", EventKind.NOTE, payload="checked")
    memory = DecisionMemory(store, project_id=project, agent_id="agent")

    def supports(seq: int, name: str) -> list[EventSupportInput]:
        return [EventSupportInput(task_name=name, seq=seq)]

    original = await memory.record_decision(
        "first",
        "route",
        "north",
        "reason",
        supports=supports(first_event.event.seq, "first"),
    )
    refused = await memory.record_decision(
        "first",
        "route",
        "south",
        "reason",
        supports=supports(first_event.event.seq, "first"),
    )
    assert refused.error is MemoryErrorCode.CHOICE_EXISTS
    empty_replacement = await memory.supersede_decision(
        original.decision.id,
        "south",
        "new evidence",
        explanation="route closed",
        supports=[],
    )
    assert empty_replacement.error is MemoryErrorCode.SUPPORT_REQUIRED
    assert (
        await memory.get_decision(original.decision.id)
    ).decision.status.value == "active"
    replacement = await memory.supersede_decision(
        original.decision.id,
        "south",
        "new evidence",
        explanation="route closed",
        supports=supports(first_event.event.seq, "first"),
    )
    other = await memory.record_decision(
        "second",
        "route",
        "north",
        "reason",
        supports=supports(second_event.event.seq, "second"),
    )
    search = await memory.search_decisions("north")
    conflicts = await memory.list_conflicts()
    view = await task.get_task("first")
    rejected = await memory.reject_decision(other.decision.id, "withdrawn")

    assert replacement.decision.revision == 2
    assert (
        await memory.get_decision(original.decision.id)
    ).decision.status.value == "superseded"
    assert {hit.decision.task_name for hit in search} == {"second"}
    assert search[0].task_goal == "choose a route"
    assert all(hit.marker == "precedent" for hit in search)
    assert conflicts.groups[0].choice_key == "route"
    assert [d.id for d in view.view.decisions] == [replacement.decision.id]
    assert rejected.decision.status.value == "rejected"
    assert other_project != project


async def test_concurrent_same_choice_records_only_one_active_decision(store, project):
    """Concurrent first writes serialize on the task before checking choices."""
    task = TaskMemory(store, project_id=project, agent_id="agent")
    await task.create_task("choice", "choose")
    event = await task.record_event("choice", EventKind.NOTE, payload="source")
    memory = DecisionMemory(store, project_id=project, agent_id="agent")
    support = [EventSupportInput(task_name="choice", seq=event.event.seq)]

    results = await asyncio.gather(
        memory.record_decision("choice", "route", "north", "reason", supports=support),
        memory.record_decision("choice", "route", "south", "reason", supports=support),
    )

    assert sum(result.recorded for result in results) == 1
    assert [result.error for result in results if not result.recorded] == [
        MemoryErrorCode.CHOICE_EXISTS
    ]


async def test_request_replay_returns_same_record_and_rejects_changed_payload(
    store, project
):
    """A request id replays its result but cannot name another payload."""
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    await tasks.create_task("replay", "choose")
    event = await tasks.record_event("replay", EventKind.NOTE, payload="source")
    memory = DecisionMemory(store, project_id=project, agent_id="agent")
    kwargs = {
        "supports": [EventSupportInput(task_name="replay", seq=event.event.seq)],
        "request_id": "record-once",
    }

    first = await memory.record_decision("replay", "route", "north", "why", **kwargs)
    replay = await memory.record_decision("replay", "route", "north", "why", **kwargs)
    changed = await memory.record_decision("replay", "route", "south", "why", **kwargs)

    assert replay == first
    assert not changed.recorded
    assert changed.error is MemoryErrorCode.REQUEST_ID_REUSED
    assert (await memory.list_decisions("replay")).page.count == 1


async def test_concurrent_reject_and_supersede_have_one_winner(store, project):
    """Reject and supersede serialize through the task before decision state."""
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    await tasks.create_task("lifecycle", "choose")
    event = await tasks.record_event("lifecycle", EventKind.NOTE, payload="source")
    memory = DecisionMemory(store, project_id=project, agent_id="agent")
    support = [EventSupportInput(task_name="lifecycle", seq=event.event.seq)]
    original = await memory.record_decision(
        "lifecycle", "route", "north", "why", supports=support
    )

    rejected, superseded = await asyncio.gather(
        memory.reject_decision(original.decision.id, "withdrawn"),
        memory.supersede_decision(
            original.decision.id,
            "south",
            "new reason",
            explanation="route changed",
            supports=support,
        ),
    )

    assert sum((rejected.recorded, superseded.recorded)) == 1
    history = await memory.list_decisions("lifecycle")
    assert history.page.count == 2 if superseded.recorded else history.page.count == 1


async def test_lists_are_capped_and_resume_keeps_older_active_decision(store, project):
    """History caps report totals while resume finds active older records."""
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    await tasks.create_task("bounded", "choose")
    event = await tasks.record_event("bounded", EventKind.NOTE, payload="source")
    support = [EventSupportInput(task_name="bounded", seq=event.event.seq)]
    memory = DecisionMemory(store, project_id=project, agent_id="agent")
    first = await memory.record_decision(
        "bounded", "choice-0", "v", "r", supports=support
    )
    for index in range(1, 21):
        result = await memory.record_decision(
            "bounded", f"choice-{index}", "v", "r", supports=support
        )
        assert result.recorded
        rejected = await memory.reject_decision(result.decision.id, "closed")
        assert rejected.recorded

    history = await memory.list_decisions("bounded")
    active = await memory.list_decisions("bounded", include_history=False)
    resumed = await tasks.get_task("bounded")

    assert history.page.count == 21
    assert len(history.page.decisions) == 20
    assert history.page.truncated
    assert active.page.count == 1
    assert not active.page.truncated
    assert [decision.id for decision in resumed.view.decisions] == [first.decision.id]
    assert resumed.view.decision_count == 1


async def test_changed_document_support_records_full_old_hash_and_current_activation(
    store, project, documents
):
    """A fetched version superseded before recording needs review."""
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    await tasks.create_task("currency", "choose")
    found = await search_evidence(
        store,
        BagOfWordsEmbedder(),
        "harbor",
        mode=EvidenceSearchMode.LEXICAL,
        scope=frozenset({documents.harbor}),
        limit=5,
    )
    evidence_id = found.hits[0].evidence_id
    fetched = await fetch_evidence(
        store, [evidence_id], scope=frozenset({documents.harbor}), max_chars=500
    )
    old_hash = fetched[0].content_hash
    await documents.graph.add(
        documents=[
            make_document(documents.harbor, "Harbor lighthouse replacement record.")
        ]
    )
    memory = DecisionMemory(store, project_id=project, agent_id="agent")

    recorded = await memory.record_decision(
        "currency",
        "source",
        "use log",
        "fetched before update",
        supports=[DocumentSupportInput(evidence_id=evidence_id)],
        fetched_evidence=fetched,
    )

    assert recorded.recorded
    assert recorded.decision is not None
    support = recorded.decision.supports[0]
    assert isinstance(support, DocumentSupport)
    assert recorded.decision.review_state is ReviewState.NEEDS_REVIEW
    assert recorded.decision.review_reason.value == "source_changed_during_recording"
    assert support.content_hash == old_hash
    assert support.recorded_activation_seq == fetched[0].observed_activation_seq == 1


async def test_refuses_inactive_decision_as_support(store, project):
    """A decision dependency must still be active when its child is recorded."""
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    await tasks.create_task("dependency", "choose")
    event = await tasks.record_event("dependency", EventKind.NOTE, payload="source")
    support = [EventSupportInput(task_name="dependency", seq=event.event.seq)]
    memory = DecisionMemory(store, project_id=project, agent_id="agent")
    parent = await memory.record_decision(
        "dependency", "parent", "north", "why", supports=support
    )
    await memory.reject_decision(parent.decision.id, "withdrawn")

    child = await memory.record_decision(
        "dependency",
        "child",
        "south",
        "why",
        supports=[*support, DecisionSupportInput(decision_id=str(parent.decision.id))],
    )

    assert not child.recorded
    assert child.error is MemoryErrorCode.SUPPORT_DECISION_NOT_ACTIVE
