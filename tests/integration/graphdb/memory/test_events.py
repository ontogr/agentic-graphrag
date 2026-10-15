"""Integration tests for appending raw events to a task.

Events are written with no model call. These tests check ordering, gapless
sequence numbers under concurrent appends, and payload bounding against a real
Neo4j database.
"""

import asyncio
import hashlib

import pytest

from agrag.common.data_models.task import EventKind, MemoryErrorCode
from agrag.graphdb.base import GraphStore
from agrag.memory import TaskMemory
from agrag.memory.tasks import MAX_PAYLOAD_CHARACTERS


class TestRecordEvent:
    """Appending events keeps order and gapless sequence numbers."""

    async def test_appends_events_in_order_with_sequence_one_to_n(
        self, store: GraphStore, project: str
    ) -> None:
        """Events come back in append order, numbered from 1 without gaps."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")
        await memory.create_task("summarize filings", "Summarize the filings")

        for index in range(3):
            result = await memory.record_event(
                "summarize filings",
                EventKind.MESSAGE,
                role="user",
                payload=f"message {index}",
            )
            assert result.recorded is True

        page = await memory.list_events("summarize filings")

        assert page.found is True
        assert [event.seq for event in page.events] == [1, 2, 3]
        assert [event.payload for event in page.events] == [
            "message 0",
            "message 1",
            "message 2",
        ]

    async def test_concurrent_appends_each_take_one_sequence_number(
        self, store: GraphStore, project: str
    ) -> None:
        """Twenty concurrent appends produce sequence numbers 1 to 20 once each."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")
        await memory.create_task("parallel", "Append from many writers")

        results = await asyncio.gather(
            *(
                memory.record_event("parallel", EventKind.NOTE, payload=f"note {index}")
                for index in range(20)
            )
        )
        page = await memory.list_events("parallel", limit=200)

        assert all(result.recorded for result in results)
        assert [event.seq for event in page.events] == list(range(1, 21))
        assert len({event.id for event in page.events}) == 20

    async def test_cuts_oversized_payload_and_keeps_full_text_hash(
        self, store: GraphStore, project: str
    ) -> None:
        """A payload over the limit is stored cut, flagged, and hashed in full."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")
        await memory.create_task("long output", "Keep a long tool result")
        text = "tool output " * (MAX_PAYLOAD_CHARACTERS // 4)
        assert len(text) > MAX_PAYLOAD_CHARACTERS

        result = await memory.record_event(
            "long output", EventKind.TOOL_RESULT, name="search", payload=text
        )

        assert result.event is not None
        assert result.event.truncated is True
        assert len(result.event.payload) == MAX_PAYLOAD_CHARACTERS
        assert result.event.payload_sha256 == hashlib.sha256(text.encode()).hexdigest()

    @pytest.mark.parametrize(
        "kind",
        [EventKind.MESSAGE, EventKind.TOOL_CALL, EventKind.TOOL_RESULT, EventKind.NOTE],
    )
    async def test_stores_each_event_kind_with_its_role_and_name(
        self, store: GraphStore, project: str, kind: EventKind
    ) -> None:
        """Each event kind is stored with the role and name it was given."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")
        await memory.create_task("kinds", "Store every kind")

        result = await memory.record_event(
            "kinds", kind, role="tool", name="lookup", payload="body"
        )
        page = await memory.list_events("kinds")

        assert result.event is not None
        assert page.events[0].kind == kind
        assert page.events[0].role == "tool"
        assert page.events[0].name == "lookup"
        assert page.events[0].truncated is False

    async def test_refuses_event_for_unknown_task_without_writing(
        self, store: GraphStore, project: str
    ) -> None:
        """An event for a task that does not exist is refused with a fixed code."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")

        result = await memory.record_event("missing", EventKind.NOTE, payload="x")
        page = await memory.list_events("missing")

        assert result.recorded is False
        assert result.error == MemoryErrorCode.TASK_NOT_FOUND
        assert page.found is False
        assert page.events == []
