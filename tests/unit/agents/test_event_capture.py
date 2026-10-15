"""Checks task event capture and admission through the agent middleware."""

import json
from types import SimpleNamespace
from typing import Any

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.errors import GraphBubbleUp

from agrag.agents.middleware import RunState, TaskEventMiddleware, record_event_or_flag
from agrag.agents.tools.core import make_core_tools
from agrag.common.data_models.evidence import DiscoveryResult, DiscoveryStatus
from agrag.common.data_models.task import (
    EventKind,
    SetStepResult,
    StepKind,
    StepState,
)


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
        """Return the next scripted reply and count the model call."""
        reply = self.replies[self.calls]
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=reply)])


class _FakeMemory:
    """Task memory stand-in that keeps events and steps in memory."""

    def __init__(self, failures: int = 0, record: bool = True) -> None:
        """Fail the first ``failures`` writes with a store error."""
        self.events: list[tuple[EventKind, str | None, str]] = []
        self.request_ids: list[str | None] = []
        self.steps: dict[str, tuple[StepState, int | None]] = {}
        self._failures = failures
        self._record = record

    async def record_event(
        self,
        task_name: str,
        kind: EventKind,
        *,
        role: str | None = None,
        name: str | None = None,
        payload: str,
        request_id: str | None = None,
    ) -> Any:
        """Store an event or raise while failures remain."""
        self.request_ids.append(request_id)
        if self._failures:
            self._failures -= 1
            raise RuntimeError("store unavailable")
        if not self._record:
            return SimpleNamespace(recorded=False, error="store rejected event")
        self.events.append((kind, name, payload))
        return SimpleNamespace(
            recorded=True, event=SimpleNamespace(seq=len(self.events))
        )

    async def set_step(
        self,
        task_name: str,
        name: str,
        state: StepState,
        *,
        kind: StepKind = StepKind.OTHER,
        result_event_seq: int | None = None,
        request_id: str | None = None,
    ) -> SetStepResult:
        """Keep the latest state and result event of each step."""
        self.steps[name] = (state, result_event_seq)
        return SetStepResult(recorded=True)


@tool
def lookup(query: str) -> str:
    """Look up a passage by query."""
    return f"found {query}"


@tool
def flaky(query: str) -> str:
    """Look up a passage, but the index is down."""
    raise RuntimeError("index unavailable")


class TestTaskEventCapture:
    """The agent loop records assistant messages and each tool outcome."""

    async def test_records_tool_call_and_result_payloads(self) -> None:
        """A tool round trip records call identity, arguments, and content."""
        memory = _FakeMemory()
        model = _ScriptedModel(
            replies=[
                AIMessage(
                    content="checking",
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
        assert memory.events[0][2] == "checking"
        assert json.loads(memory.events[1][2]) == {
            "tool_call_id": "c1",
            "arguments": {"query": "a"},
        }
        assert json.loads(memory.events[2][2]) == {
            "tool_call_id": "c1",
            "content": "found a",
        }
        assert memory.events[3][2] == "done"
        assert model.calls == 2
        assert not run_state.recording_failed

    async def test_repeated_tool_calls_keep_distinct_ids_and_obey_shared_budget(
        self,
    ) -> None:
        """The agent runs two calls, then returns an error for the third."""
        memory = _FakeMemory()
        model = _ScriptedModel(
            replies=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "lookup", "args": {"query": "a"}, "id": "c1"},
                        {"name": "lookup", "args": {"query": "b"}, "id": "c2"},
                        {"name": "lookup", "args": {"query": "c"}, "id": "c3"},
                    ],
                ),
                AIMessage(content="done"),
            ]
        )
        run_state = RunState(max_tool_calls=2)
        agent = create_agent(
            model=model,
            tools=[lookup],
            middleware=[TaskEventMiddleware(memory, "task", run_state)],
        )

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "question"}]}
        )

        calls = [
            json.loads(payload)
            for kind, _, payload in memory.events
            if kind == EventKind.TOOL_CALL
        ]
        tool_results = [
            json.loads(payload)
            for kind, _, payload in memory.events
            if kind == EventKind.TOOL_RESULT
        ]
        tool_messages = [
            message
            for message in result["messages"]
            if isinstance(message, ToolMessage)
        ]
        assert [call["tool_call_id"] for call in calls] == ["c1", "c2", "c3"]
        assert {item["tool_call_id"]: item["content"] for item in tool_results} == {
            "c1": "found a",
            "c2": "found b",
            "c3": "Tool budget exhausted.",
        }
        assert {message.tool_call_id: message.status for message in tool_messages} == {
            "c1": "success",
            "c2": "success",
            "c3": "error",
        }
        assert run_state.tool_calls == 2
        assert run_state.budget_exhausted


class TestToolErrors:
    """A raising tool becomes an error result and fails open steps."""

    async def test_error_result_fails_open_step_with_result_sequence(self) -> None:
        """The model gets an error message and the failed step links its event."""
        memory = _FakeMemory()
        model = _ScriptedModel(
            replies=[
                AIMessage(
                    content="",
                    tool_calls=[{"name": "flaky", "args": {"query": "a"}, "id": "c1"}],
                ),
                AIMessage(content="I could not look it up."),
            ]
        )
        run_state = RunState(max_tool_calls=5)
        run_state.open_steps["draft"] = StepKind.ANALYSIS
        agent = create_agent(
            model=model,
            tools=[flaky],
            middleware=[TaskEventMiddleware(memory, "task", run_state)],
        )

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "question"}]}
        )

        tool_messages = [
            message
            for message in result["messages"]
            if isinstance(message, ToolMessage)
        ]
        assert len(tool_messages) == 1
        assert tool_messages[0].status == "error"
        assert tool_messages[0].tool_call_id == "c1"
        assert result["messages"][-1].content == "I could not look it up."
        assert memory.events[2][:2] == (EventKind.TOOL_RESULT, "flaky")
        assert json.loads(memory.events[2][2]) == {
            "tool_call_id": "c1",
            "content": "error: RuntimeError: index unavailable",
        }
        assert memory.steps == {"draft": (StepState.FAILED, 3)}
        assert run_state.open_steps == {}

    async def test_control_signals_propagate(self) -> None:
        """Graph interrupts are not converted into ordinary tool errors."""
        middleware = TaskEventMiddleware(
            _FakeMemory(), "task", RunState(max_tool_calls=5)
        )

        async def interrupted(_request: object) -> object:
            raise GraphBubbleUp

        request = SimpleNamespace(tool_call={"name": "lookup", "args": {}, "id": "c1"})
        with pytest.raises(GraphBubbleUp):
            await middleware.awrap_tool_call(request, interrupted)


class TestRecordEventOrFlag:
    """Event writes retry once and expose lasting failures on run state."""

    async def test_retry_reuses_request_id(self) -> None:
        """A transient store error does not duplicate the event."""
        memory = _FakeMemory(failures=1)
        run_state = RunState(max_tool_calls=5)

        await record_event_or_flag(
            memory, "task", run_state, EventKind.NOTE, payload="note"
        )

        assert len(memory.request_ids) == 2
        assert memory.request_ids[0] == memory.request_ids[1]
        assert not run_state.recording_failed

    @pytest.mark.parametrize(
        ("memory",),
        [(_FakeMemory(failures=2),), (_FakeMemory(record=False),)],
    )
    async def test_agent_run_flags_unrecorded_event(self, memory: _FakeMemory) -> None:
        """A rejected or raising event write marks the run as failed."""
        model = _ScriptedModel(replies=[AIMessage(content="done")])
        run_state = RunState(max_tool_calls=2)
        agent = create_agent(
            model=model,
            tools=[lookup],
            middleware=[TaskEventMiddleware(memory, "task", run_state)],
        )

        await agent.ainvoke({"messages": [{"role": "user", "content": "question"}]})

        assert run_state.recording_failed


class TestToolBudgetAdmission:
    """TaskEventMiddleware alone admits calls against the run budget."""

    async def test_core_tool_does_not_admit_or_record_its_own_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Direct core-tool invocation leaves admission and events to middleware."""

        async def discover(*args: object, **kwargs: object) -> DiscoveryResult:
            return DiscoveryResult(status=DiscoveryStatus.NO_MATCH)

        monkeypatch.setattr("agrag.agents.tools.core.discover", discover)
        memory = _FakeMemory()
        tools, run_state = make_core_tools(
            graph_store=object(),
            embedder=object(),
            scope=frozenset({"doc"}),
            task_name="task",
            memory=memory,
            decisions=object(),
            fetched_ids=[],
            fetched_outcomes=[],
            max_chars=1_000,
            max_tool_calls=1,
        )

        result = await next(
            tool for tool in tools if tool.name == "discover_evidence"
        ).ainvoke({"query": "q"})

        assert result
        assert run_state.tool_calls == 0
        assert memory.events == []
        assert not run_state.budget_exhausted
