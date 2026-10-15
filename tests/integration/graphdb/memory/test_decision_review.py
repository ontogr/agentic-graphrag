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
    assert peer.decision.review_state is ReviewState.UNKNOWN
    await memory.continue_review_propagation(limit=10)
    peer = await memory.get_decision(second_decision.id)
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
    assert child.decision.review_state is ReviewState.UNKNOWN
    await tasks.create_task("late-child", "depend during review propagation")
    late_event = await tasks.record_event(
        "late-child", EventKind.NOTE, payload="fixture"
    )
    late_result = await memory.record_decision(
        "late-child",
        "late-child-choice",
        "follow parent",
        "created during propagation",
        supports=[
            DecisionSupportInput(decision_id=str(parent.id)),
            EventSupportInput(task_name="late-child", seq=late_event.event.seq),
        ],
    )
    assert late_result.recorded
    assert late_result.decision.review_state is ReviewState.NEEDS_REVIEW
    await memory.continue_review_propagation(limit=10)
    child = await memory.get_decision(child_result.decision.id)
    assert child.decision.review_state is ReviewState.NEEDS_REVIEW
    assert child.decision.review_reason.value == "dependency_review"


async def test_review_propagation_is_bounded_restartable_and_cycle_safe(
    store, project, documents
):
    """A ten-decision chain resumes in bounded batches and terminates on cycles."""
    memory, parent = await _record_document_decision(
        store, project, documents, "chain-0"
    )
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    chain = [parent]
    for index in range(1, 10):
        name = f"chain-{index}"
        await tasks.create_task(name, "depend on previous decision")
        event = await tasks.record_event(name, EventKind.NOTE, payload="fixture")
        result = await memory.record_decision(
            name,
            f"chain-choice-{index}",
            f"follow {index - 1}",
            "explicit dependency",
            supports=[
                DecisionSupportInput(decision_id=str(chain[-1].id)),
                EventSupportInput(task_name=name, seq=event.event.seq),
            ],
        )
        assert result.recorded and result.decision is not None
        chain.append(result.decision)

    await documents.graph.add(
        documents=[make_document(documents.harbor, "Harbor chain replacement.")]
    )
    assert await memory.continue_review_propagation(limit=3) == 3
    fourth = await memory.get_decision(chain[4].id)
    assert fourth.decision.review_state is ReviewState.UNKNOWN
    assert await memory.continue_review_propagation(limit=3) == 3
    assert await memory.continue_review_propagation(limit=3) == 3
    assert await memory.continue_review_propagation(limit=3) == 1

    await store.execute_write(
        "MATCH (last:MemoryDecision {id: $last_id}), "
        "(first:MemoryDecision {id: $first_id}) "
        "CREATE (last)-[:DEPENDS_ON]->(first)",
        {"last_id": str(chain[-1].id), "first_id": str(chain[0].id)},
    )
    await store.execute_write(
        "MATCH (p:MemoryProject {project_id: $project_id}) "
        "MATCH (d:MemoryDecision) WHERE d.id IN $ids "
        "SET d.review_state = 'clear', d.review_reason = null, "
        "d.review_pending = false "
        "WITH p "
        "MATCH (first:MemoryDecision {id: $first_id}) "
        "SET first.review_state = 'needs_review', first.review_pending = true, "
        "p.review_incomplete = true",
        {
            "project_id": project,
            "ids": [str(decision.id) for decision in chain],
            "first_id": str(chain[0].id),
        },
    )
    assert await memory.continue_review_propagation(limit=3) == 3
    assert await memory.continue_review_propagation(limit=3) == 3
    assert await memory.continue_review_propagation(limit=3) == 3
    assert await memory.continue_review_propagation(limit=3) == 1
    assert await memory.continue_review_propagation(limit=3) == 0
    for decision in chain:
        assert (
            await memory.get_decision(decision.id)
        ).decision.review_state is ReviewState.NEEDS_REVIEW


async def test_review_lists_are_project_scoped_and_bounded(store, project, documents):
    """Review listing reports only the configured project's changed support."""
    memory, decision = await _record_document_decision(
        store, project, documents, "review-list"
    )
    assert decision.review_state is ReviewState.CLEAR
    result = await memory.list_review(limit=1)
    assert result.count == 0
    assert result.decisions == []
