"""Exercise source-change review through Neo4j-backed public memory operations."""

from agrag.common.data_models.decision import (
    DecisionSupport,
    DecisionSupportInput,
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
    HARBOR_TEXT,
    BagOfWordsEmbedder,
    make_document,
)


async def _record_document_decision(
    store, project, documents, task_name: str, document_key: str | None = None
):
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    await tasks.create_task(task_name, "decide from a document")
    await tasks.record_event(task_name, EventKind.NOTE, payload="review fixture")
    found = await search_evidence(
        store,
        BagOfWordsEmbedder(),
        "privacy" if document_key == documents.keep else "harbor",
        mode=EvidenceSearchMode.LEXICAL,
        scope=frozenset({document_key or documents.harbor}),
        limit=5,
    )
    evidence_id = found.hits[0].evidence_id
    fetched = await fetch_evidence(
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
    await memory.continue_decision_review(limit=10)
    peer = await memory.get_decision(second_decision.id)
    assert peer.decision.review_state is ReviewState.CLEAR


async def test_purge_flags_decisions_supported_by_removed_document(
    store, project, documents
):
    """Purging a document flags its supported decisions and their dependents."""
    memory, decision = await _record_document_decision(
        store, project, documents, "purged-source"
    )
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    await tasks.create_task("purged-consumer", "depends on the source decision")
    event = await tasks.record_event(
        "purged-consumer", EventKind.NOTE, payload="decision fixture"
    )
    dependent = await memory.record_decision(
        "purged-consumer",
        "choice-purged-consumer",
        "follow the source",
        "explicit dependency",
        supports=[
            DecisionSupportInput(decision_id=str(decision.id)),
            EventSupportInput(task_name="purged-consumer", seq=event.event.seq),
        ],
    )
    assert dependent.recorded and dependent.decision is not None

    await documents.graph.purge_document(documents.harbor)
    await memory.continue_decision_review(limit=10)

    direct = await memory.get_decision(decision.id)
    child = await memory.get_decision(dependent.decision.id)
    assert direct.decision.review_state is ReviewState.NEEDS_REVIEW
    assert direct.decision.review_reason.value == "source_removed"
    assert child.decision.review_state is ReviewState.NEEDS_REVIEW
    assert child.decision.review_reason.value == "dependency_review"


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
    await memory.continue_decision_review(limit=10)
    child = await memory.get_decision(child_result.decision.id)
    assert child.decision.review_state is ReviewState.NEEDS_REVIEW
    assert child.decision.review_reason.value == "dependency_review"


async def test_rejecting_parent_makes_descendants_unknown_until_propagated(
    store, project, documents
):
    """Rejecting a parent queues transitive descendants in the same write."""
    memory, parent = await _record_document_decision(
        store, project, documents, "reject-parent"
    )
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    previous = parent
    descendants = []
    for name in ("reject-child", "reject-grandchild"):
        await tasks.create_task(name, "depend on prior decision")
        event = await tasks.record_event(name, EventKind.NOTE, payload="fixture")
        result = await memory.record_decision(
            name,
            name,
            "follow prior",
            "explicit dependency",
            supports=[
                DecisionSupportInput(decision_id=str(previous.id)),
                EventSupportInput(task_name=name, seq=event.event.seq),
            ],
        )
        assert result.recorded and result.decision is not None
        previous = result.decision
        descendants.append(previous)

    rejected = await memory.reject_decision(parent.id, "no longer accepted")
    assert rejected.recorded
    assert (
        await memory.get_decision(descendants[0].id)
    ).decision.review_state is ReviewState.UNKNOWN
    assert await memory.continue_decision_review(limit=1) == 1
    assert (
        await memory.get_decision(descendants[0].id)
    ).decision.review_state is ReviewState.NEEDS_REVIEW
    assert (
        await memory.get_decision(descendants[1].id)
    ).decision.review_state is ReviewState.UNKNOWN
    await memory.continue_decision_review(limit=10)
    assert (
        await memory.get_decision(descendants[1].id)
    ).decision.review_state is ReviewState.NEEDS_REVIEW


async def test_superseding_parent_queues_dependent_without_migrating_support(
    store, project, documents
):
    """Supersession makes a child unknown and propagates review to it."""
    memory, parent = await _record_document_decision(
        store, project, documents, "supersede-parent"
    )
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    await tasks.create_task("supersede-child", "depend on the parent")
    event = await tasks.record_event(
        "supersede-child", EventKind.NOTE, payload="fixture"
    )
    child = await memory.record_decision(
        "supersede-child",
        "child-choice",
        "follow parent",
        "explicit dependency",
        supports=[
            DecisionSupportInput(decision_id=str(parent.id)),
            EventSupportInput(task_name="supersede-child", seq=event.event.seq),
        ],
    )
    assert child.recorded and child.decision is not None
    evidence_id, fetched = await _current_harbor_support(store, documents)
    replacement = await memory.supersede_decision(
        parent.id,
        "updated conclusion",
        "replacement rationale",
        explanation="The decision changed.",
        supports=[DocumentSupportInput(evidence_id=evidence_id)],
        fetched_evidence=fetched,
    )

    assert replacement.recorded and replacement.decision is not None
    assert (
        await memory.get_decision(child.decision.id)
    ).decision.review_state is ReviewState.UNKNOWN
    assert await memory.continue_decision_review(limit=10) >= 1
    current_child = await memory.get_decision(child.decision.id)
    assert current_child.decision.review_state is ReviewState.NEEDS_REVIEW
    dependencies = [
        support.decision_id
        for support in child.decision.supports
        if isinstance(support, DecisionSupport)
    ]
    assert dependencies == [parent.id]
    assert replacement.decision.id not in dependencies


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
    assert await memory.continue_decision_review(limit=3) == 3
    fourth = await memory.get_decision(chain[4].id)
    assert fourth.decision.review_state is ReviewState.UNKNOWN
    assert await memory.continue_decision_review(limit=3) == 3
    assert await memory.continue_decision_review(limit=3) == 3
    assert await memory.continue_decision_review(limit=3) == 1

    await store.execute_write(
        "MATCH (last:MemoryDecision {id: $last_id}), "
        "(first:MemoryDecision {id: $first_id}) "
        "CREATE (first)-[:DEPENDS_ON]->(last)",
        {"last_id": str(chain[-1].id), "first_id": str(chain[0].id)},
    )
    await store.execute_write(
        "MATCH (p:MemoryProject {project_id: $project_id}) "
        "MATCH (d:MemoryDecision) WHERE d.id IN $ids "
        "SET d.review_state = 'clear', d.review_reason = null, "
        "d.review_pending = false, p.review_epoch = p.review_epoch + 1 "
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
    assert await memory.continue_decision_review(limit=3) == 3
    assert await memory.continue_decision_review(limit=3) == 3
    assert await memory.continue_decision_review(limit=3) == 3
    assert await memory.continue_decision_review(limit=3) == 1
    assert await memory.continue_decision_review(limit=3) == 0
    for decision in chain:
        assert (
            await memory.get_decision(decision.id)
        ).decision.review_state is ReviewState.NEEDS_REVIEW


async def test_review_lists_are_project_scoped_and_bounded(
    store, project, other_project, documents
):
    """Review listing reports flagged decisions of this project only, within limit."""
    memory, decision = await _record_document_decision(
        store, project, documents, "review-list"
    )
    assert decision.review_state is ReviewState.CLEAR
    result = await memory.list_decisions_for_review(limit=1)
    assert result.count == 0
    assert result.decisions == []

    _, second = await _record_document_decision(
        store, project, documents, "review-list-second"
    )
    other_memory, other = await _record_document_decision(
        store, other_project, documents, "review-list-other"
    )
    await documents.graph.add(
        documents=[
            make_document(documents.harbor, "Harbor lighthouse replacement record.")
        ]
    )
    page = await memory.list_decisions_for_review(limit=1)
    assert page.count == 2
    assert page.truncated is True
    assert len(page.decisions) == 1
    assert page.decisions[0].id in {decision.id, second.id}
    full = await memory.list_decisions_for_review(limit=5)
    assert full.count == 2
    assert full.truncated is False
    assert {listed.id for listed in full.decisions} == {decision.id, second.id}
    other_list = await other_memory.list_decisions_for_review(limit=5)
    assert [listed.id for listed in other_list.decisions] == [other.id]


async def _current_harbor_support(store, documents, query: str = "harbor"):
    found = await search_evidence(
        store,
        BagOfWordsEmbedder(),
        query,
        mode=EvidenceSearchMode.LEXICAL,
        scope=frozenset({documents.harbor}),
        limit=5,
    )
    evidence_id = found.hits[0].evidence_id
    fetched = await fetch_evidence(
        store, [evidence_id], scope=frozenset({documents.harbor}), max_chars=500
    )
    assert fetched[0].status is FetchStatus.OK
    return evidence_id, fetched


async def test_reaffirm_without_current_fetch_fails_and_keeps_flag(
    store, project, documents
):
    """Reaffirming a changed document needs a fetch of its current version."""
    memory, decision = await _record_document_decision(
        store, project, documents, "reaffirm-unfetched"
    )
    await documents.graph.add(
        documents=[
            make_document(documents.harbor, "Harbor lighthouse replacement record.")
        ]
    )
    await memory.continue_decision_review(limit=10)
    result = await memory.reaffirm_decision(
        decision.id, [decision.supports[0]], fetched_evidence=[]
    )
    assert result.recorded is False
    assert result.error is MemoryErrorCode.CANNOT_REVALIDATE
    current = await memory.get_decision(decision.id)
    assert current.decision.review_state is ReviewState.NEEDS_REVIEW


async def test_reaffirm_of_removed_document_fails_even_with_ok_fetch(
    store, project, documents
):
    """A soft-deleted document cannot be revalidated from any fetch of its text."""
    memory, decision = await _record_document_decision(
        store, project, documents, "reaffirm-removed"
    )
    earlier = await fetch_evidence(
        store,
        [decision.supports[0].evidence_id],
        scope=frozenset({documents.harbor}),
        max_chars=500,
    )
    assert earlier[0].status is FetchStatus.OK
    await documents.graph.delete_document(documents.harbor)
    later = await fetch_evidence(
        store,
        [decision.supports[0].evidence_id],
        scope=frozenset({documents.harbor}),
        max_chars=500,
    )
    for fetched in (earlier, later):
        result = await memory.reaffirm_decision(
            decision.id, [decision.supports[0]], fetched_evidence=fetched
        )
        assert result.error is MemoryErrorCode.CANNOT_REVALIDATE
    current = await memory.get_decision(decision.id)
    assert current.decision.review_state is ReviewState.NEEDS_REVIEW
    assert current.decision.review_reason.value == "source_removed"


async def test_reaffirm_with_current_fetch_clears_flag_and_records_reviewer(
    store, project, documents
):
    """Reaffirming with the current version clears the flag and keeps the reviewer."""
    memory, decision = await _record_document_decision(
        store, project, documents, "reaffirm-clear"
    )
    await documents.graph.add(
        documents=[
            make_document(documents.harbor, "Harbor lighthouse replacement record.")
        ]
    )
    await memory.continue_decision_review(limit=10)
    evidence_id, fetched = await _current_harbor_support(store, documents)
    reviewer = DecisionMemory(store, project_id=project, agent_id="reviewer")
    result = await reviewer.reaffirm_decision(
        decision.id,
        [DocumentSupportInput(evidence_id=evidence_id)],
        fetched_evidence=fetched,
        request_id="reaffirm-clear-1",
    )
    assert result.recorded
    assert result.decision.review_state is ReviewState.CLEAR
    assert result.decision.review_reason is None
    assert result.decision.supports[0].content_hash == fetched[0].content_hash
    history = await reviewer.list_support_history(decision.id, limit=1)
    assert history.truncated
    assert history.next_after_ordinal is not None
    historical = history.supports[0]
    assert historical.evidence_id == decision.supports[0].evidence_id
    assert not historical.current
    assert historical.reviewed_by == "reviewer"
    assert historical.review_explanation == "Reaffirmed after review."
    next_page = await reviewer.list_support_history(
        decision.id, after_ordinal=history.next_after_ordinal, limit=1
    )
    assert len(next_page.supports) == 1
    assert next_page.supports[0].current
    retry = await reviewer.reaffirm_decision(
        decision.id,
        [DocumentSupportInput(evidence_id=evidence_id)],
        fetched_evidence=fetched,
        request_id="reaffirm-clear-1",
    )
    assert retry == result
    events = await TaskMemory(store, project_id=project, agent_id="agent").list_events(
        "reaffirm-clear"
    )
    assert events.events[-1].kind is EventKind.NOTE
    assert events.events[-1].author == "reviewer"


async def test_reaffirming_parent_leaves_dependent_child_flagged(
    store, project, documents
):
    """Reaffirming a decision leaves the flags of its dependents in place."""
    memory, parent = await _record_document_decision(
        store, project, documents, "parent-reaffirm"
    )
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    await tasks.create_task("child-reaffirm", "depend on a decision")
    event = await tasks.record_event(
        "child-reaffirm", EventKind.NOTE, payload="fixture"
    )
    child = await memory.record_decision(
        "child-reaffirm",
        "child-reaffirm-choice",
        "follow parent",
        "explicit dependency",
        supports=[
            DecisionSupportInput(decision_id=str(parent.id)),
            EventSupportInput(task_name="child-reaffirm", seq=event.event.seq),
        ],
    )
    assert child.recorded
    await documents.graph.add(
        documents=[
            make_document(documents.harbor, "Harbor lighthouse replacement record.")
        ]
    )
    await memory.continue_decision_review(limit=10)
    evidence_id, fetched = await _current_harbor_support(store, documents)
    result = await memory.reaffirm_decision(
        parent.id,
        [DocumentSupportInput(evidence_id=evidence_id)],
        fetched_evidence=fetched,
    )
    assert result.decision.review_state is ReviewState.CLEAR
    await memory.continue_decision_review(limit=10)
    current_child = await memory.get_decision(child.decision.id)
    assert current_child.decision.review_state is ReviewState.NEEDS_REVIEW
    assert current_child.decision.review_reason.value == "dependency_review"


async def test_reaffirm_is_refused_while_a_dependency_needs_review(
    store, project, documents
):
    """A dependent cannot be reaffirmed until the decision it depends on is resolved."""
    memory, parent = await _record_document_decision(
        store, project, documents, "parent-blocked"
    )
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    await tasks.create_task("child-blocked", "depend on a decision")
    event = await tasks.record_event("child-blocked", EventKind.NOTE, payload="fixture")
    child = await memory.record_decision(
        "child-blocked",
        "child-blocked-choice",
        "follow parent",
        "explicit dependency",
        supports=[
            DecisionSupportInput(decision_id=str(parent.id)),
            EventSupportInput(task_name="child-blocked", seq=event.event.seq),
        ],
    )
    assert child.recorded
    await documents.graph.add(
        documents=[
            make_document(documents.harbor, "Harbor lighthouse replacement record.")
        ]
    )
    await memory.continue_decision_review(limit=10)
    blocked = await memory.reaffirm_decision(child.decision.id, [], fetched_evidence=[])
    assert blocked.recorded is False
    assert blocked.error is MemoryErrorCode.CANNOT_REVALIDATE
    current = await memory.get_decision(child.decision.id)
    assert current.decision.review_state is ReviewState.NEEDS_REVIEW

    evidence_id, fetched = await _current_harbor_support(store, documents)
    parent_result = await memory.reaffirm_decision(
        parent.id,
        [DocumentSupportInput(evidence_id=evidence_id)],
        fetched_evidence=fetched,
    )
    assert parent_result.recorded
    child_result = await memory.reaffirm_decision(
        child.decision.id, [], fetched_evidence=[]
    )
    assert child_result.recorded
    assert child_result.decision.review_state is ReviewState.CLEAR


async def test_propagation_reaches_clear_dependents_of_flagged_decisions(
    store, project, documents
):
    """Propagation reaches the dependents of a dependent that is already flagged."""
    memory, parent = await _record_document_decision(
        store, project, documents, "queue-parent"
    )
    tasks = TaskMemory(store, project_id=project, agent_id="agent")
    chain = [parent]
    for name in ("queue-child", "queue-grandchild"):
        await tasks.create_task(name, "depend on previous decision")
        event = await tasks.record_event(name, EventKind.NOTE, payload="fixture")
        result = await memory.record_decision(
            name,
            f"{name}-choice",
            "follow previous",
            "explicit dependency",
            supports=[
                DecisionSupportInput(decision_id=str(chain[-1].id)),
                EventSupportInput(task_name=name, seq=event.event.seq),
            ],
        )
        assert result.recorded and result.decision is not None
        chain.append(result.decision)
    child, grandchild = chain[1], chain[2]
    await documents.graph.add(
        documents=[make_document(documents.harbor, "Harbor queue replacement.")]
    )
    await memory.continue_decision_review(limit=10)
    assert (
        await memory.get_decision(grandchild.id)
    ).decision.review_state is ReviewState.NEEDS_REVIEW

    await store.execute_write(
        "MATCH (d:MemoryDecision {id: $id}) "
        "SET d.review_state = 'clear', d.review_reason = null",
        {"id": str(grandchild.id)},
    )
    await store.execute_write(
        "MATCH (p:MemoryProject {project_id: $project_id}) "
        "MATCH (d:MemoryDecision {id: $id}) "
        "SET d.review_pending = true, p.review_incomplete = true, "
        "p.review_epoch = p.review_epoch + 1",
        {"project_id": project, "id": str(parent.id)},
    )
    assert (
        await memory.get_decision(child.id)
    ).decision.review_state is ReviewState.NEEDS_REVIEW
    assert await memory.continue_decision_review(limit=10) >= 1
    assert (
        await memory.get_decision(grandchild.id)
    ).decision.review_state is ReviewState.NEEDS_REVIEW


async def test_revert_to_recorded_content_keeps_flag(store, project, documents):
    """A document that returns to its recorded hash does not clear the flag."""
    memory, decision = await _record_document_decision(
        store, project, documents, "revert"
    )
    await documents.graph.add(
        documents=[
            make_document(documents.harbor, "Harbor lighthouse replacement record.")
        ]
    )
    await documents.graph.add(documents=[make_document(documents.harbor, HARBOR_TEXT)])
    await memory.continue_decision_review(limit=10)
    current = await memory.get_decision(decision.id)
    assert current.decision.review_state is ReviewState.NEEDS_REVIEW
    assert current.decision.review_reason.value == "source_changed"
