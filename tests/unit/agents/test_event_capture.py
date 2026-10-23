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
from agrag.common.data_models.evidence import EvidenceSearchResult, EvidenceSearchStatus
from agrag.common.data_models.task import (
    EventKind,
    SetStepResult,
    StepKind,
    StepState,
)
from agrag.retrieval import RetrievalSettings


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


class _FakeHistory:
    """Conversation history stand-in that stores events and steps."""

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
        history = _FakeHistory()
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
            middleware=[TaskEventMiddleware(history, "task", run_state)],
        )

        await agent.ainvoke({"messages": [{"role": "user", "content": "question"}]})

        assert [(kind, name) for kind, name, _ in history.events] == [
            (EventKind.MESSAGE, None),
            (EventKind.TOOL_CALL, "lookup"),
            (EventKind.TOOL_RESULT, "lookup"),
            (EventKind.MESSAGE, None),
        ]
        assert history.events[0][2] == "checking"
        assert json.loads(history.events[1][2]) == {
            "tool_call_id": "c1",
            "arguments": {"query": "a"},
        }
        assert json.loads(history.events[2][2]) == {
            "tool_call_id": "c1",
            "content": "found a",
        }
        assert history.events[3][2] == "done"
        assert model.calls == 2
        assert not run_state.recording_failed

    async def test_repeated_tool_calls_keep_distinct_ids_and_obey_shared_budget(
        self,
    ) -> None:
        """The agent runs two calls, then returns an error for the third."""
        history = _FakeHistory()
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
            middleware=[TaskEventMiddleware(history, "task", run_state)],
        )

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "question"}]}
        )

        calls = [
            json.loads(payload)
            for kind, _, payload in history.events
            if kind == EventKind.TOOL_CALL
        ]
        tool_results = [
            json.loads(payload)
            for kind, _, payload in history.events
            if kind == EventKind.TOOL_RESULT
        ]
        tool_messages = [
            message
            for message in result["messages"]
            if isinstance(message, ToolMessage)
        ]
        assert {call["tool_call_id"] for call in calls} == {"c1", "c2", "c3"}
        results_by_id = {item["tool_call_id"]: item["content"] for item in tool_results}
        assert set(results_by_id) == {"c1", "c2", "c3"}
        calls_by_id = {call["tool_call_id"]: call for call in calls}
        successful_ids = {
            tool_call_id
            for tool_call_id, content in results_by_id.items()
            if content != "Tool budget exhausted."
        }
        assert len(successful_ids) == 2
        assert all(
            results_by_id[tool_call_id]
            == f"found {calls_by_id[tool_call_id]['arguments']['query']}"
            for tool_call_id in successful_ids
        )
        assert (
            sum(
                content == "Tool budget exhausted."
                for content in results_by_id.values()
            )
            == 1
        )
        assert {message.tool_call_id: message.status for message in tool_messages} == {
            tool_call_id: "success" if tool_call_id in successful_ids else "error"
            for tool_call_id in ("c1", "c2", "c3")
        }
        assert run_state.tool_calls == 2
        assert run_state.budget_exhausted


class TestToolErrors:
    """A raising tool becomes an error result and fails open steps."""

    async def test_error_result_fails_open_step_with_result_sequence(self) -> None:
        """The model gets an error message and the failed step links its event."""
        history = _FakeHistory()
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
            middleware=[TaskEventMiddleware(history, "task", run_state)],
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
        assert history.events[2][:2] == (EventKind.TOOL_RESULT, "flaky")
        assert json.loads(history.events[2][2]) == {
            "tool_call_id": "c1",
            "content": "error: RuntimeError: index unavailable",
        }
        assert history.steps == {"draft": (StepState.FAILED, 3)}
        assert run_state.open_steps == {}

    async def test_control_signals_propagate(self) -> None:
        """Graph interrupts are not converted into ordinary tool errors."""
        middleware = TaskEventMiddleware(
            _FakeHistory(), "task", RunState(max_tool_calls=5)
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
        history = _FakeHistory(failures=1)
        run_state = RunState(max_tool_calls=5)

        await record_event_or_flag(
            history, "task", run_state, EventKind.NOTE, payload="note"
        )

        assert len(history.request_ids) == 2
        assert history.request_ids[0] == history.request_ids[1]
        assert not run_state.recording_failed

    @pytest.mark.parametrize(
        ("history",),
        [(_FakeHistory(failures=2),), (_FakeHistory(record=False),)],
    )
    async def test_agent_run_flags_unrecorded_event(
        self, history: _FakeHistory
    ) -> None:
        """A rejected or raising event write marks the run as failed."""
        model = _ScriptedModel(replies=[AIMessage(content="done")])
        run_state = RunState(max_tool_calls=2)
        agent = create_agent(
            model=model,
            tools=[lookup],
            middleware=[TaskEventMiddleware(history, "task", run_state)],
        )

        await agent.ainvoke({"messages": [{"role": "user", "content": "question"}]})

        assert run_state.recording_failed


class TestToolBudgetAdmission:
    """TaskEventMiddleware alone admits calls against the run budget."""

    async def test_core_tool_does_not_admit_or_record_its_own_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Direct core-tool invocation leaves admission and events to middleware."""

        async def fake_search_evidence(
            *args: object, **kwargs: object
        ) -> EvidenceSearchResult:
            return EvidenceSearchResult(status=EvidenceSearchStatus.NO_MATCH)

        monkeypatch.setattr(
            "agrag.agents.tools.core.search_evidence", fake_search_evidence
        )
        history = _FakeHistory()
        tools, run_state = make_core_tools(
            graph_store=object(),
            embedder=object(),
            scope=frozenset({"doc"}),
            task_name="task",
            history=history,
            decisions=object(),
            fetched_ids=[],
            fetched_outcomes=[],
            max_chars=1_000,
            max_tool_calls=1,
            retrieval_settings=RetrievalSettings(),
        )

        result = await next(
            tool for tool in tools if tool.name == "search_evidence"
        ).ainvoke({"query": "q"})

        assert result
        assert run_state.tool_calls == 0
        assert history.events == []
        assert not run_state.budget_exhausted
