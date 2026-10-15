"""Checks that the agent loop records task events and flags writes it cannot keep."""

import json
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from agrag.agents.middleware import (
    RunState,
    TaskEventMiddleware,
    record_event_or_flag,
)
from agrag.common.data_models.task import EventKind, RecordEventResult


class _ScriptedModel(BaseChatModel):
    """Chat model that replays scripted replies and counts its calls."""

    replies: list[AIMessage] = []
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        """Name the fake model type."""
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_ScriptedModel":
        """Accept the agent's tools without changing the replies."""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Return the next scripted reply and count the call."""
        reply = self.replies[self.calls]
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=reply)])


class _FakeMemory:
    """Task memory stand-in that keeps events in a list and can fail writes."""

    def __init__(self, failures: int = 0) -> None:
        """Fail the first ``failures`` writes with a store error."""
        self.events: list[tuple[EventKind, str | None, str]] = []
        self.request_ids: list[str | None] = []
        self._failures = failures

    async def record_event(
        self,
        task_name: str,
        kind: EventKind,
        *,
        role: str | None = None,
        name: str | None = None,
        payload: str,
        request_id: str | None = None,
    ) -> RecordEventResult:
        """Store the event, or raise while failures remain."""
        self.request_ids.append(request_id)
        if self._failures:
            self._failures -= 1
            raise RuntimeError("store unavailable")
        self.events.append((kind, name, payload))
        return RecordEventResult(recorded=True)


@tool
def lookup(query: str) -> str:
    """Look up a passage by query."""
    return f"found {query}"


class TestTaskEventCapture:
    """The agent loop records its own messages and tool outcomes as events."""

    async def test_records_each_message_and_tool_outcome_in_order(self) -> None:
        """A tool round trip adds four events and no extra model call."""
        memory = _FakeMemory()
        model = _ScriptedModel(
            replies=[
                AIMessage(
                    content="",
                    tool_calls=[{"name": "lookup", "args": {"query": "a"}, "id": "c1"}],
                ),
                AIMessage(content="done"),
            ]
        )
        run_state = RunState(max_tool_calls=5)
        agent = create_agent(
            model=model,
            tools=[lookup],
            middleware=[TaskEventMiddleware(memory, "task", run_state)],
        )

        await agent.ainvoke({"messages": [{"role": "user", "content": "question"}]})

        assert [(kind, name) for kind, name, _ in memory.events] == [
            (EventKind.MESSAGE, None),
            (EventKind.TOOL_CALL, "lookup"),
            (EventKind.TOOL_RESULT, "lookup"),
            (EventKind.MESSAGE, None),
        ]
        assert json.loads(memory.events[1][2]) == {"query": "a"}
        assert memory.events[2][2] == "found a"
        assert model.calls == 2
        assert not run_state.recording_failed


class TestRecordEventOrFlag:
    """A lasting write failure is flagged on the run, never dropped silently."""

    async def test_a_failed_write_is_retried_once_with_the_same_request_id(
        self,
    ) -> None:
        """One transient error is absorbed and the run is not flagged."""
        memory = _FakeMemory(failures=1)
        run_state = RunState(max_tool_calls=5)

        await record_event_or_flag(
            memory, "task", run_state, EventKind.NOTE, payload="result"
        )

        assert len(memory.request_ids) == 2
        assert len(set(memory.request_ids)) == 1
        assert not run_state.recording_failed
        assert run_state.recording_failures == []

    async def test_a_write_that_fails_twice_flags_the_run(self) -> None:
        """Two failed attempts set the flag and keep the event's description."""
        memory = _FakeMemory(failures=2)
        run_state = RunState(max_tool_calls=5)

        await record_event_or_flag(
            memory, "task", run_state, EventKind.NOTE, name="step", payload="result"
        )

        assert len(memory.request_ids) == 2
        assert run_state.recording_failed
        assert len(run_state.recording_failures) == 1
        assert "step" in run_state.recording_failures[0]
