"""Checks that the agent loop records task events and flags writes it cannot keep."""

import json
from typing import Any

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.errors import GraphBubbleUp

from agrag.agents.middleware import (
    RunState,
    TaskEventMiddleware,
    record_event_or_flag,
)
from agrag.agents.tools.core import make_core_tools
from agrag.common.data_models.task import (
    EventKind,
    RecordEventResult,
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
        self.steps: dict[str, StepState] = {}
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
        """Keep the latest state of each step."""
        self.steps[name] = state
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


class TestToolErrors:
    """A raising tool ends its call with an error result, not the whole run."""

    async def test_error_is_recorded_flagged_and_the_run_continues(self) -> None:
        """The model sees an error tool message, the open step fails, and it answers."""
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

        assert model.calls == 2
        tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert [m.status for m in tool_messages] == ["error"]
        assert tool_messages[0].tool_call_id == "c1"
        assert result["messages"][-1].content == "I could not look it up."
        assert (
            EventKind.TOOL_RESULT,
            "flaky",
            "error: RuntimeError: index unavailable",
        ) in memory.events
        assert memory.steps == {"draft": StepState.FAILED}
        assert run_state.open_steps == {}
        assert not run_state.recording_failed

    async def test_a_control_signal_is_not_swallowed(self) -> None:
        """A graph interrupt or parent command propagates out of the tool call."""
        middleware = TaskEventMiddleware(
            _FakeMemory(), "task", RunState(max_tool_calls=5)
        )

        async def interrupted(_request: object) -> object:
            raise GraphBubbleUp

        request = _Request({"name": "lookup", "args": {}, "id": "c1"})
        with pytest.raises(GraphBubbleUp):
            await middleware.awrap_tool_call(request, interrupted)

    async def test_a_failed_step_write_flags_the_run(self) -> None:
        """A step that cannot be marked failed is named in the run's failures."""

        class _RefusingMemory(_FakeMemory):
            async def set_step(self, *args: object, **kwargs: object) -> SetStepResult:
                raise RuntimeError("store unavailable")

        run_state = RunState(max_tool_calls=5)
        run_state.open_steps["draft"] = StepKind.ANALYSIS
        middleware = TaskEventMiddleware(_RefusingMemory(), "task", run_state)

        async def broken(_request: object) -> object:
            raise ValueError("bad input")

        request = _Request({"name": "lookup", "args": {}, "id": "c1"})
        reply = await middleware.awrap_tool_call(request, broken)

        assert reply.status == "error"
        assert run_state.recording_failed
        assert "draft" in run_state.recording_failures[0]
        assert run_state.open_steps == {}


class _Request:
    """The part of a tool request the middleware reads."""

    def __init__(self, tool_call: dict[str, object]) -> None:
        """Hold one tool call."""
        self.tool_call = tool_call


class TestToolBudgetBoundsErrors:
    """A tool that keeps failing spends the budget and then stops being called."""

    async def test_failing_tool_is_called_at_most_the_budget(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Retries end at the tool-call budget, and every error is recorded."""
        calls: list[str] = []

        async def failing_discover(*args: object, **kwargs: object) -> object:
            calls.append("discover")
            raise RuntimeError("vector index missing")

        monkeypatch.setattr("agrag.agents.tools.core.discover", failing_discover)
        memory = _FakeMemory()
        tools, run_state = make_core_tools(
            graph_store=object(),  # type: ignore[arg-type]
            embedder=object(),  # type: ignore[arg-type]
            scope=frozenset({"doc"}),
            task_name="task",
            memory=memory,  # type: ignore[arg-type]
            decisions=object(),  # type: ignore[arg-type]
            fetched_ids=[],
            fetched_outcomes=[],
            max_chars=1_000,
            max_tool_calls=3,
        )
        model = _ScriptedModel(
            replies=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "discover_evidence",
                            "args": {"query": "q"},
                            "id": f"c{index}",
                        }
                    ],
                )
                for index in range(5)
            ]
            + [AIMessage(content="No evidence.")]
        )
        agent = create_agent(
            model=model,
            tools=tools,
            middleware=[TaskEventMiddleware(memory, "task", run_state)],
        )

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "question"}]},
            config={"recursion_limit": 30},
        )

        assert calls == ["discover"] * 3
        assert model.calls == 6
        assert result["messages"][-1].content == "No evidence."
        results = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert [m.status for m in results] == ["error"] * 3 + ["success"] * 2
        assert results[-1].content == "Tool budget exhausted."
        assert run_state.budget_exhausted
