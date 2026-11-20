"""Check that decision recording observes activations committed concurrently."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agrag.common.data_models.decision import EventSupportInput
from agrag.common.data_models.evidence import EvidenceSearchMode, FetchStatus
from agrag.common.data_models.task import EventKind
from agrag.cypher.documents import record_activation_query
from agrag.decisions import DecisionTraces
from agrag.evidence import fetch_evidence, search_evidence
from agrag.history.tasks import ConversationHistory
from tests.integration.retrieval.evidence._corpus import BagOfWordsEmbedder


pytestmark = pytest.mark.neo4j_only


async def _activate_after_lock_is_observed(
    store,
    *,
    document_id: str,
    document_key: str,
    content_hash: str,
    locked: asyncio.Event,
    release: asyncio.Event,
) -> None:
    """Hold the document lock, then commit an activation after the recorder starts."""
    async with store.session() as session:
        transaction = await session.begin_transaction()
        try:
            result = await transaction.run(
                "MATCH (doc:Document {id: $id}) "
                "SET doc._agrag_decision_lock = true RETURN doc.id AS id",
                {"id": document_id},
            )
            assert await result.data()
            locked.set()
            await release.wait()
            result = await transaction.run(
                record_activation_query(),
                {
                    "document_node_id": document_id,
                    "id": f"decision-race-{uuid4().hex}",
                    "document_key": document_key,
                    "verb": "update",
                    "content_hash": content_hash,
                    "previous_content_hash": "old-hash",
                    "version_id": None,
                    "activated_at": datetime.now(UTC).isoformat(),
                    "job_id": None,
                },
            )
            assert await result.data()
            await transaction.commit()
        except BaseException:
            await transaction.rollback()
            raise


async def test_recording_marks_consulted_source_stale_after_concurrent_activation(
    store, project, documents
):
    """A concurrent activation marks a consulted source stale.

    The activation cannot commit between the consulted read and its decision.
    """
    tasks = ConversationHistory(store, project_id=project, agent_id="agent")
    await tasks.create_task("concurrent-source", "decide from sources")
    event = await tasks.record_event(
        "concurrent-source", EventKind.NOTE, payload="source checked"
    )
    found = await search_evidence(
        store,
        BagOfWordsEmbedder(),
        "harbor",
        mode=EvidenceSearchMode.LEXICAL,
        scope=frozenset({documents.harbor}),
        limit=5,
    )
    fetched = await fetch_evidence(
        store,
        [found.hits[0].evidence_id],
        scope=frozenset({documents.harbor}),
        max_chars=500,
    )
    outcome = fetched.outcomes[0]
    assert outcome.status is FetchStatus.OK
    assert outcome.reference is not None
    document_id = str(outcome.reference.document_node_id)
    locked = asyncio.Event()
    release = asyncio.Event()
    activation = asyncio.create_task(
        _activate_after_lock_is_observed(
            store,
            document_id=document_id,
            document_key=outcome.document_key,
            content_hash="new-hash",
            locked=locked,
            release=release,
        )
    )
    await locked.wait()

    history = DecisionTraces(store, project_id=project, agent_id="agent")
    recording = asyncio.create_task(
        history.record_decision(
            "concurrent-source",
            "choice",
            "use source",
            "source was consulted",
            supports=[
                EventSupportInput(task_name="concurrent-source", seq=event.event.seq)
            ],
            consulted=fetched.outcomes,
        )
    )
    await asyncio.sleep(0.1)
    release.set()
    await activation
    result = await recording

    assert result.recorded
    assert result.decision.review_state.value == "needs_review"
    assert result.decision.review_reason.value == "consulted_source_changed"
