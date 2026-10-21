"""Integration tests for restoring task steps with a scripted model.

These tests use a private Neo4j database and verify both the model's resumed
context and the task state persisted by the agent.
"""

import importlib.util
import json
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pytest import MonkeyPatch

from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.common.data_models.decision import EventSupportInput
from agrag.common.data_models.task import (
    EventKind,
    StepResultBasis,
    StepResultValidity,
    StepState,
)
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.memory import TaskMemory
from agrag.memory.retention import RetentionMemory


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _ScriptedModel(BaseChatModel):
    """Chat model that replays replies and records each input it receives."""

    replies: list[Any] = []
    calls: int = 0
    seen: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        """Return the scripted model type."""
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_ScriptedModel":
        """Accept agent tools without changing the scripted replies."""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Record an input and return its scripted reply."""
        self.seen.append(list(messages))
        reply = self.replies[self.calls]
        self.calls += 1
        if isinstance(reply, BaseException):
            raise reply
        return ChatResult(generations=[ChatGeneration(message=reply)])


class _ZeroEmbedder(Embedder):
    """Embedder for runs that do not search evidence."""

    model = "resume-test"

    async def dimensions(self) -> int:
        """Return the vector size."""
        return 2

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one fixed vector per input text."""
        return [[0.0, 1.0] for _ in texts]


def _call(name: str, args: dict[str, Any]) -> AIMessage:
    """Build a model response that calls one tool."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


def _answer(text: str) -> AIMessage:
    """Build the final answer using the structured-output tool contract."""
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "AgentAnswer",
                "args": {
                    "answer": text,
                    "support_status": "supported",
                    "citations": [],
                },
                "id": "final-answer",
            }
        ],
    )


def _text(messages: list[BaseMessage]) -> str:
    """Join message contents for assertions about model context."""
    return "\n".join(str(message.content) for message in messages)


def _build(
    monkeypatch: MonkeyPatch,
    store: GraphStore,
    project_id: str,
    model: _ScriptedModel,
) -> Any:
    """Build an agent with the supplied scripted chat model."""
    monkeypatch.setattr("agrag.agents.build.build_chat_model", lambda _config: model)
    return build_agent(
        graph_store=store,
        embedder=_ZeroEmbedder(),
        scope=frozenset(),
        project_id=project_id,
        agent_id="resume-test",
        llm_settings=AgentLLMSettings(
            clients=[
                {"name": "test", "provider": "openai-generic", "model": "test-model"}
            ]
        ),
        agent_settings=AgentSettings(),
    )


async def _delete_project_memory(store: GraphStore, project_id: str) -> None:
    """Delete all task memory nodes belonging to a project."""
    params = {"project_id": project_id}
    await store.execute_write(
        "MATCH (t:MemoryTask {project_id: $project_id}) "
        "OPTIONAL MATCH (t)-[:HAS_EVENT|HAS_STEP]->(child) "
        "DETACH DELETE child, t",
        params,
    )
    await store.execute_write(
        "MATCH (r:MemoryRequest {project_id: $project_id}) DETACH DELETE r", params
    )
    await store.execute_write(
        "MATCH (p:MemoryProject {project_id: $project_id}) DETACH DELETE p", params
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestAgentResumeIntegration:
    """Resume task work from persisted Neo4j step state."""

    async def test_tool_result_exposes_its_persisted_event_reference(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """The model can address a tool result as typed event support."""
        store = build_graph_store("neo4j")
        await store.connect()
        project_id = f"event-reference-{uuid4().hex}"
        task_name = f"task-{uuid4().hex}"
        memory = TaskMemory(store, project_id=project_id, agent_id="resume-test")
        try:
            model = _ScriptedModel(
                replies=[_call("get_task", {}), _answer("Task inspected.")]
            )
            result = await _build(monkeypatch, store, project_id, model).ainvoke(
                {"task_name": task_name, "question": "Inspect the task."}
            )
            assert result["status"] == "answered"
            events = await memory.list_events(task_name)
            saved = next(
                event for event in events.events if event.kind is EventKind.TOOL_RESULT
            )
            context = _text(model.seen[1])
            assert f'"task_name": "{task_name}", "seq": {saved.seq}' in context
            lookup = await memory.fetch_event(task_name, saved.seq)
            assert lookup.event is not None
            content = json.loads(lookup.event.payload)["content"]
            assert json.loads(content)["found"] is True
        finally:
            await _delete_project_memory(store, project_id)
            await store.close()

    async def test_unknown_result_basis_is_not_reused(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """A completed result with unknown support is omitted from model context."""
        store = build_graph_store("neo4j")
        await store.connect()
        project_id = f"resume-unknown-{uuid4().hex}"
        task_name = f"unknown-task-{uuid4().hex}"
        memory = TaskMemory(store, project_id=project_id, agent_id="resume-test")
        try:
            assert (
                await memory.create_task(task_name, "Review current inputs.")
            ).recorded
            event = await memory.record_event(
                task_name,
                EventKind.NOTE,
                name="private-result",
                payload="unknown-basis-payload",
            )
            assert event.event is not None
            assert (
                await memory.set_step(
                    task_name,
                    "uncertain review",
                    StepState.COMPLETED,
                    result_event_seq=event.event.seq,
                )
            ).recorded

            model = _ScriptedModel(replies=[_answer("I reviewed the current inputs.")])
            result = await _build(monkeypatch, store, project_id, model).ainvoke(
                {"task_name": task_name, "question": "Review current inputs."}
            )

            assert result["status"] == "answered"
            context = _text(model.seen[0])
            assert "unknown-basis-payload" not in context
            assert "uncertain review: (not reusable" in context
        finally:
            await _delete_project_memory(store, project_id)
            await store.close()

    async def test_redacted_event_support_invalidates_completed_result(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """A result is not reused after its supporting event is redacted."""
        store = build_graph_store("neo4j")
        await store.connect()
        project_id = f"resume-redacted-{uuid4().hex}"
        task_name = f"redacted-task-{uuid4().hex}"
        memory = TaskMemory(store, project_id=project_id, agent_id="resume-test")
        result_text = "Result based on private source material."
        try:
            assert (await memory.create_task(task_name, "Review the source.")).recorded
            source = await memory.record_event(
                task_name,
                EventKind.NOTE,
                name="source",
                payload="private-source-payload",
            )
            assert source.event is not None
            result_event = await memory.record_event(
                task_name,
                EventKind.NOTE,
                name="result:source review",
                payload=result_text,
            )
            assert result_event.event is not None
            assert (
                await memory.set_step(
                    task_name,
                    "source review",
                    StepState.COMPLETED,
                    result_event_seq=result_event.event.seq,
                    result_basis=StepResultBasis.SUPPORTED,
                    supports=[
                        EventSupportInput(task_name=task_name, seq=source.event.seq)
                    ],
                )
            ).recorded

            assert (
                await RetentionMemory(
                    store, project_id=project_id, agent_id="resume-test"
                ).redact_event(str(source.event.id))
            ).recorded

            persisted = await memory.get_task(task_name)
            assert persisted.view is not None
            completed = persisted.view.steps[StepState.COMPLETED][0]
            assert completed.result_validity is StepResultValidity.UNAVAILABLE

            model = _ScriptedModel(replies=[_answer("I will review the source again.")])
            response = await _build(monkeypatch, store, project_id, model).ainvoke(
                {"task_name": task_name, "question": "Review the source."}
            )

            assert response["status"] == "answered"
            context = _text(model.seen[0])
            assert "private-source-payload" not in context
            assert result_text not in context
            assert "source review: (not reusable" in context
        finally:
            await _delete_project_memory(store, project_id)
            await store.close()

    async def test_completed_result_survives_more_than_200_later_events(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """A completed result remains available after old events leave the page."""
        store = build_graph_store("neo4j")
        await store.connect()
        project_id = f"resume-{uuid4().hex}"
        task_name = f"memo-{uuid4().hex}"
        result_text = "Persisted result for the completed filing review."
        memory = TaskMemory(store, project_id=project_id, agent_id="resume-test")
        try:
            assert (await memory.create_task(task_name, "Finish the memo.")).recorded
            for index in range(205):
                assert (
                    await memory.record_event(
                        task_name,
                        EventKind.NOTE,
                        name=f"later-{index}",
                        payload="later",
                    )
                ).recorded
            saved = await memory.record_event(
                task_name,
                EventKind.NOTE,
                name="result:filing review",
                payload=result_text,
            )
            assert saved.event is not None
            assert (
                await memory.set_step(
                    task_name,
                    "filing review",
                    StepState.COMPLETED,
                    result_event_seq=saved.event.seq,
                    result_basis=StepResultBasis.INDEPENDENT,
                )
            ).recorded

            model = _ScriptedModel(replies=[_answer("The memo is finished.")])
            result = await _build(monkeypatch, store, project_id, model).ainvoke(
                {"task_name": task_name, "question": "Finish the memo."}
            )

            assert result["status"] == "answered"
            assert model.calls == 1
            assert result_text in _text(model.seen[0])
            persisted = await memory.get_task(task_name)
            assert persisted.view is not None
            assert persisted.view.step_counts[StepState.COMPLETED] == 1
        finally:
            await _delete_project_memory(store, project_id)
            await store.close()

    async def test_resume_handles_more_than_50_completed_and_interrupted_steps(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """The model receives old results and can complete an interrupted step."""
        store = build_graph_store("neo4j")
        await store.connect()
        project_id = f"resume-steps-{uuid4().hex}"
        task_name = f"long-task-{uuid4().hex}"
        memory = TaskMemory(store, project_id=project_id, agent_id="resume-test")
        try:
            assert (
                await memory.create_task(task_name, "Finish the long task.")
            ).recorded
            for index in range(55):
                name = f"completed-{index:02d}"
                event = await memory.record_event(
                    task_name,
                    EventKind.NOTE,
                    name=f"result:{name}",
                    payload=f"stored-{name}",
                )
                assert event.event is not None
                assert (
                    await memory.set_step(
                        task_name,
                        name,
                        StepState.COMPLETED,
                        result_event_seq=event.event.seq,
                        result_basis=StepResultBasis.INDEPENDENT,
                    )
                ).recorded
            for index in range(6):
                assert (
                    await memory.set_step(
                        task_name, f"interrupted-{index}", StepState.IN_PROGRESS
                    )
                ).recorded

            model = _ScriptedModel(
                replies=[
                    _call(
                        "set_step",
                        {
                            "name": "interrupted-0",
                            "state": "completed",
                            "kind": "other",
                            "result": "Finished interrupted-0.",
                            "result_basis": "independent",
                        },
                    ),
                    _answer("The long task is finished."),
                ]
            )
            result = await _build(monkeypatch, store, project_id, model).ainvoke(
                {"task_name": task_name, "question": "Finish the long task."}
            )

            assert result["status"] == "answered"
            assert model.calls == 2
            context = _text(model.seen[0])
            assert "stored-completed-00" in context
            assert "stored-completed-54" in context
            assert "interrupted-0" in context
            persisted = await memory.get_task(task_name)
            assert persisted.view is not None
            assert persisted.view.step_counts[StepState.COMPLETED] == 56
            assert persisted.view.step_counts[StepState.UNKNOWN] == 5
        finally:
            await _delete_project_memory(store, project_id)
            await store.close()

    async def test_raising_tool_returns_error_and_agent_continues(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """A failed tool step is persisted and the model produces a final answer."""
        store = build_graph_store("neo4j")
        await store.connect()
        project_id = f"resume-error-{uuid4().hex}"
        task_name = f"error-task-{uuid4().hex}"
        memory = TaskMemory(store, project_id=project_id, agent_id="resume-test")

        async def fail_search(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("search unavailable")

        monkeypatch.setattr("agrag.agents.tools.core.search_evidence", fail_search)
        try:
            model = _ScriptedModel(
                replies=[
                    _call(
                        "set_step",
                        {
                            "name": "failing step",
                            "state": "in_progress",
                            "kind": "analysis",
                        },
                    ),
                    _call("search_evidence", {"query": "trigger failure"}),
                    _answer("I recovered and completed the task."),
                ]
            )
            result = await _build(monkeypatch, store, project_id, model).ainvoke(
                {"task_name": task_name, "question": "Complete this task."}
            )

            assert result["status"] == "answered"
            assert model.calls == 3
            error_responses = [
                message
                for message in model.seen[2]
                if isinstance(message, ToolMessage) and message.status == "error"
            ]
            assert len(error_responses) == 1
            assert error_responses[0].status == "error"
            assert "search unavailable" in str(error_responses[0].content)
            persisted = await memory.get_task(task_name)
            assert persisted.view is not None
            assert persisted.view.step_counts[StepState.FAILED] == 1
            failed_step = persisted.view.steps[StepState.FAILED][0]
            assert failed_step.name == "failing step"
            assert failed_step.result_event_seq is not None
            events = await memory.list_events(task_name, limit=200)
            error_result = next(
                event
                for event in events.events
                if event.seq == failed_step.result_event_seq
            )
            assert "search unavailable" in error_result.payload
        finally:
            await _delete_project_memory(store, project_id)
            await store.close()
