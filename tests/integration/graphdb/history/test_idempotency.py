"""Integration tests for request ids on task history writes.

A write with a request id can be retried safely. The same id with the same
arguments returns the stored result. The same id with other arguments is refused.
A write that fails partway through leaves no partial state.
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, TypeVar
from uuid import UUID

import pytest

from agrag.common.data_models.graph_record import (
    DeferredWrites,
    NodeRecord,
    RelationRecord,
    UpsertResult,
)
from agrag.common.data_models.task import EventKind, StepState, WriteErrorCode
from agrag.graphdb.base import GraphStoreTransaction
from agrag.graphdb.neo4j import Neo4jGraphStore
from agrag.history import ConversationHistory


_T = TypeVar("_T")


class _FailingTransaction(GraphStoreTransaction):
    """A transaction handle that raises on one chosen write.

    The write counter starts at zero for each transaction. Reads and the
    other write methods pass through unchanged.
    """

    def __init__(self, tx: GraphStoreTransaction, *, fail_on_write: int | None) -> None:
        """Wrap a transaction and choose the write that fails.

        Args:
            tx: The real transaction handle.
            fail_on_write: The 1-based number of the execute_write call that
                raises, or None for no failure.
        """
        self._tx = tx
        self._fail_on_write = fail_on_write
        self._writes = 0

    async def execute_read(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Pass the read through to the real transaction."""
        return await self._tx.execute_read(query, parameters)

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Pass the write through, or raise when it is the chosen write."""
        self._writes += 1
        if self._writes == self._fail_on_write:
            raise RuntimeError("simulated failure after earlier writes")
        return await self._tx.execute_write(query, parameters)

    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult | None:
        """Pass the upsert through to the real transaction."""
        return await self._tx.upsert_nodes(
            label,
            nodes,
            batch_size=batch_size,
            pending_job_id=pending_job_id,
            deferred=deferred,
        )

    async def upsert_relations(
        self,
        relations: Sequence[RelationRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult | None:
        """Pass the upsert through to the real transaction."""
        return await self._tx.upsert_relations(
            relations,
            batch_size=batch_size,
            pending_job_id=pending_job_id,
            deferred=deferred,
        )


class _FailingStore(Neo4jGraphStore):
    """A Neo4j store whose transactions fail on a chosen write.

    The failure is a plain RuntimeError, which the driver does not retry, so it
    rolls the whole transaction back and reaches the caller.
    """

    def __init__(self, *, fail_on_write: int) -> None:
        """Build the store with the connection settings from the environment.

        Args:
            fail_on_write: The 1-based write, within each transaction, that
                raises.
        """
        super().__init__()
        self._fail_on_write = fail_on_write

    async def run_in_transaction(
        self, work: Callable[[GraphStoreTransaction], Awaitable[_T]]
    ) -> _T:
        """Run the work inside a transaction whose chosen write raises."""
        fail_on_write = self._fail_on_write

        async def faulty_work(tx: GraphStoreTransaction) -> _T:
            return await work(_FailingTransaction(tx, fail_on_write=fail_on_write))

        return await super().run_in_transaction(faulty_work)


class TestRequestIds:
    """Writes with a request id are recorded once and refuse reuse."""

    async def test_same_request_twice_creates_one_task(
        self, store: Neo4jGraphStore, project: str
    ) -> None:
        """The second create with the same id returns the stored task."""
        history = ConversationHistory(store, project_id=project, agent_id="agent-a")

        first = await history.create_task("plan", "Write the plan", request_id="req-1")
        second = await history.create_task("plan", "Write the plan", request_id="req-1")

        assert first.recorded is True
        assert second == first

    async def test_same_request_twice_appends_one_event(
        self, store: Neo4jGraphStore, project: str
    ) -> None:
        """A retried append keeps one event and one sequence number."""
        history = ConversationHistory(store, project_id=project, agent_id="agent-a")
        await history.create_task("notes", "Keep notes")

        first = await history.record_event(
            "notes", EventKind.NOTE, payload="once", request_id="ev-1"
        )
        second = await history.record_event(
            "notes", EventKind.NOTE, payload="once", request_id="ev-1"
        )
        page = await history.list_events("notes")

        assert second == first
        assert [event.seq for event in page.events] == [1]

    async def test_same_request_id_with_other_arguments_is_refused(
        self, store: Neo4jGraphStore, project: str
    ) -> None:
        """Reusing an id for a different payload is refused and writes nothing."""
        history = ConversationHistory(store, project_id=project, agent_id="agent-a")
        await history.create_task("reuse", "Check reuse")
        await history.record_event(
            "reuse", EventKind.NOTE, payload="first", request_id="ev-2"
        )

        result = await history.record_event(
            "reuse", EventKind.NOTE, payload="second", request_id="ev-2"
        )
        page = await history.list_events("reuse")

        assert result.recorded is False
        assert result.error == WriteErrorCode.REQUEST_ID_REUSED
        assert [event.payload for event in page.events] == ["first"]

    async def test_request_id_used_by_another_operation_is_refused(
        self, store: Neo4jGraphStore, project: str
    ) -> None:
        """An id used for a task cannot be reused for a step write."""
        history = ConversationHistory(store, project_id=project, agent_id="agent-a")
        await history.create_task("shared id", "Goal", request_id="req-x")

        result = await history.set_step(
            "shared id", "step", StepState.COMPLETED, request_id="req-x"
        )

        assert result.recorded is False
        assert result.error == WriteErrorCode.REQUEST_ID_REUSED

    async def test_request_id_longer_than_64_characters_is_refused(
        self, store: Neo4jGraphStore, project: str
    ) -> None:
        """An id over 64 characters is refused before any write."""
        history = ConversationHistory(store, project_id=project, agent_id="agent-a")

        result = await history.create_task("long id", "Goal", request_id="x" * 65)
        lookup = await history.get_task("long id")

        assert result.recorded is False
        assert result.error == WriteErrorCode.INVALID_REQUEST_ID
        assert lookup.found is False


@pytest.mark.neo4j_only
class TestFailureInsideTransaction:
    """A failed write leaves nothing behind, and a retry records it once."""

    async def test_retry_after_failure_after_request_and_event_writes(
        self, store: Neo4jGraphStore, project: str
    ) -> None:
        """A failure after the request and event writes rolls both back.

        The failing store raises on the third write of the transaction, which is
        after the request claim and the event insert and before the transaction
        commits. The test then checks that no event exists and the sequence is
        still zero. The same request id, retried on a normal store, must record
        exactly one event with sequence 1.
        """
        normal = ConversationHistory(store, project_id=project, agent_id="agent-a")
        await normal.create_task("durable", "Survive a failure")

        async with _FailingStore(fail_on_write=3) as failing_store:
            failing = ConversationHistory(
                failing_store, project_id=project, agent_id="agent-a"
            )
            raised = False
            try:
                await failing.record_event(
                    "durable", EventKind.NOTE, payload="x", request_id="retry-1"
                )
            except RuntimeError:
                raised = True
        assert raised is True

        before = await normal.get_task("durable")
        assert before.view is not None
        assert before.view.last_event_seq == 0
        assert (await normal.list_events("durable")).events == []

        retried = await normal.record_event(
            "durable", EventKind.NOTE, payload="x", request_id="retry-1"
        )
        page = await normal.list_events("durable")

        assert retried.recorded is True
        assert [event.seq for event in page.events] == [1]
