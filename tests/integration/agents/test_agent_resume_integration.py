"""Integration tests for restoring task steps with a scripted model.

These tests use a private Neo4j database and verify both the model's resumed
context and the task state persisted by the agent.
"""

import importlib.util
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
from agrag.common.data_models.task import EventKind, StepState
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.memory import TaskMemory


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
                )
            ).recorded

            model = _ScriptedModel(replies=[AIMessage(content="The memo is finished.")])
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
                            "state_name": "completed",
                            "kind": "other",
                            "result": "Finished interrupted-0.",
                        },
                    ),
                    AIMessage(content="The long task is finished."),
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

        async def fail_discovery(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("discovery unavailable")

        monkeypatch.setattr("agrag.agents.tools.core.discover", fail_discovery)
        try:
            model = _ScriptedModel(
                replies=[
                    _call(
                        "set_step",
                        {
                            "name": "failing step",
                            "state_name": "in_progress",
                            "kind": "analysis",
                        },
                    ),
                    _call("discover_evidence", {"query": "trigger failure"}),
                    AIMessage(content="I recovered and completed the task."),
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
            assert "discovery unavailable" in str(error_responses[0].content)
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
            assert "discovery unavailable" in error_result.payload
        finally:
            await _delete_project_memory(store, project_id)
            await store.close()
