"""Exercise source-change review through Neo4j-backed public memory operations."""

from agrag.common.data_models.decision import (
    DecisionSupportInput,
    DocumentSupportInput,
    EventSupportInput,
    ReviewState,
)
from agrag.common.data_models.evidence import DiscoveryMode, FetchStatus
from agrag.common.data_models.task import EventKind
from agrag.evidence import discover, fetch
from agrag.memory.decisions import DecisionMemory
from agrag.memory.tasks import TaskMemory
from tests.integration.retrieval.evidence._corpus import (
    BagOfWordsEmbedder,
    make_document,
)


async def _record_document_decision(
    store, project, documents, task_name: str, document_key: str | None = None
):
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    await tasks.create_task(task_name, "decide from a document")
    await tasks.record_event(task_name, EventKind.NOTE, payload="review fixture")
    found = await discover(
        store,
        BagOfWordsEmbedder(),
        "privacy" if document_key == documents.keep else "harbor",
        mode=DiscoveryMode.LEXICAL,
        scope=frozenset({document_key or documents.harbor}),
        limit=5,
    )
    evidence_id = found.hits[0].evidence_id
    fetched = await fetch(
        store,
        [evidence_id],
        scope=frozenset({document_key or documents.harbor}),
        max_chars=500,
    )
    assert fetched[0].status is FetchStatus.OK
    memory = DecisionMemory(store, project_id=project, agent_id="agent")
    result = await memory.record_decision(
        task_name,
        f"choice-{task_name}",
        "use harbor",
        "document support",
        supports=[DocumentSupportInput(evidence_id=evidence_id)],
        fetched_evidence=fetched,
    )
    assert result.recorded and result.decision is not None
    return memory, result.decision


async def test_activation_flags_decisions_supported_by_changed_document(
    store, project, documents
):
    """Committed source changes flag every decision supporting that document."""
    memory, affected = await _record_document_decision(
        store, project, documents, "affected"
    )
    _, second_decision = await _record_document_decision(
        store, project, documents, "unrelated", documents.keep
    )
    await documents.graph.add(
        documents=[
            make_document(documents.harbor, "Harbor lighthouse replacement record.")
        ]
    )

    changed = await memory.get_decision(affected.id)
    peer = await memory.get_decision(second_decision.id)
    assert changed.decision.review_state is ReviewState.NEEDS_REVIEW
    assert changed.decision.review_reason.value == "source_changed"
    assert peer.decision.review_state is ReviewState.CLEAR


async def test_review_propagates_to_explicitly_dependent_decisions(
    store, project, documents
):
    """A source change also flags a decision that explicitly depends on it."""
    memory, parent = await _record_document_decision(
        store, project, documents, "parent"
    )
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    await tasks.create_task("child", "depend on a decision")
    event = await tasks.record_event("child", EventKind.NOTE, payload="fixture")
    child_result = await memory.record_decision(
        "child",
        "child-choice",
        "follow parent",
        "explicit dependency",
        supports=[
            DecisionSupportInput(decision_id=str(parent.id)),
            EventSupportInput(task_name="child", seq=event.event.seq),
        ],
    )
    assert child_result.recorded
    await documents.graph.add(
        documents=[make_document(documents.harbor, "Harbor replacement source.")]
    )
    child = await memory.get_decision(child_result.decision.id)
    assert child.decision.review_state is ReviewState.NEEDS_REVIEW
    assert child.decision.review_reason.value == "dependency_review"


async def test_review_lists_are_project_scoped_and_bounded(store, project, documents):
    """Review listing reports only the configured project's changed support."""
    memory, decision = await _record_document_decision(
        store, project, documents, "review-list"
    )
    assert decision.review_state is ReviewState.CLEAR
    result = await memory.list_review(limit=1)
    assert result.count == 0
    assert result.decisions == []
