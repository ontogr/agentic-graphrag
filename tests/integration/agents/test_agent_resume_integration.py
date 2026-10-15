"""Integration test for resuming a task after the agent run stops.

The agent runs against a real Neo4j store with a scripted model. The first run
completes one step with a long result and starts a second step, then stops.
The second run uses the same task name. It must reuse the stored result, must
not repeat the completed step, and must leave a gapless, truncation-aware
event log.
"""

import hashlib
import importlib.util
import json
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pytest import MonkeyPatch

from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.common.data_models.task import EventKind, StepState
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.memory import TaskMemory
from agrag.memory.tasks import MAX_PAYLOAD_CHARACTERS


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _ScriptedModel(BaseChatModel):
    """Chat model that replays scripted replies and records every input."""

    replies: list[Any] = []
    calls: int = 0
    seen: list[list[BaseMessage]] = []

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
        """Record the input, then return the next reply or raise it."""
        self.seen.append(list(messages))
        reply = self.replies[self.calls]
        self.calls += 1
        if isinstance(reply, BaseException):
            raise reply
        return ChatResult(generations=[ChatGeneration(message=reply)])


class _ZeroEmbedder(Embedder):
    """Embedder for agents whose run does not search evidence."""

    model = "resume-test"

    async def dimensions(self) -> int:
        """Return the vector size."""
        return 2

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a fixed vector per text."""
        return [[0.0, 1.0] for _ in texts]


def _call(name: str, args: dict[str, Any]) -> AIMessage:
    """Build a model reply that calls one tool."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


def _text(messages: list[BaseMessage]) -> str:
    """Join the text of every message in one model input."""
    return "\n".join(str(message.content) for message in messages)


def _build(
    monkeypatch: MonkeyPatch,
    store: GraphStore,
    project_id: str,
    model: _ScriptedModel,
) -> Any:
    """Build the agent with the scripted model in place of a configured LLM."""
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
    """Delete the task memory nodes of one project."""
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
class TestResumeAfterInterruption:
    """A stopped run resumes under the same task name without repeating work."""

    async def test_second_run_reuses_the_completed_step_and_finishes_the_rest(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Reuse completed work, rerun interrupted work, and keep events exact."""
        store = build_graph_store("neo4j")
        await store.connect()
        project_id = f"resume-{uuid4().hex[:8]}"
        task_name = "quarterly memo"
        long_result = "filing text " * 4_000
        fetch_args = {
            "name": "fetch filing",
            "state_name": "completed",
            "kind": "read",
            "result": long_result,
        }
        try:
            first_model = _ScriptedModel(
                replies=[
                    _call("set_step", fetch_args),
                    _call(
                        "set_step",
                        {
                            "name": "draft summary",
                            "state_name": "in_progress",
                            "kind": "analysis",
                        },
                    ),
                    RuntimeError("process stopped"),
                ]
            )
            first_agent = _build(monkeypatch, store, project_id, first_model)
            with pytest.raises(RuntimeError, match="process stopped"):
                await first_agent.ainvoke(
                    {"task_name": task_name, "question": "Write the memo."}
                )

            memory = TaskMemory(store, project_id=project_id, agent_id="resume-test")
            before = await memory.list_events(task_name, limit=200)
            seq_before = before.events[-1].seq

            second_model = _ScriptedModel(
                replies=[
                    _call(
                        "set_step",
                        {
                            "name": "draft summary",
                            "state_name": "completed",
                            "kind": "analysis",
                            "result": "draft text",
                        },
                    ),
                    AIMessage(content="The memo is drafted."),
                ]
            )
            second_agent = _build(monkeypatch, store, project_id, second_model)
            result = await second_agent.ainvoke(
                {"task_name": task_name, "question": "Write the memo."}
            )

            assert result["status"] == "answered"
            assert result["recording_failures"] == []
            assert second_model.calls == 2
            first_input = _text(second_model.seen[0])
            assert "fetch filing" in first_input
            assert "filing text" in first_input

            lookup = await memory.get_task(task_name)
            assert lookup.view is not None
            view = lookup.view
            assert view.step_counts[StepState.COMPLETED] == 2
            assert view.step_counts[StepState.IN_PROGRESS] == 0
            assert view.step_counts[StepState.UNKNOWN] == 0

            events = (await memory.list_events(task_name, limit=200)).events
            assert [event.seq for event in events] == list(range(1, len(events) + 1))
            new_events = [event for event in events if event.seq > seq_before]
            repeated_fetch = [
                event
                for event in new_events
                if event.kind is EventKind.TOOL_CALL and "fetch filing" in event.payload
            ]
            assert repeated_fetch == []

            fetch_call = next(
                event
                for event in events
                if event.kind is EventKind.TOOL_CALL
                and event.name == "set_step"
                and "fetch filing" in event.payload
            )
            expected_hash = hashlib.sha256(
                json.dumps(fetch_args, default=str).encode("utf-8")
            ).hexdigest()
            assert fetch_call.truncated
            assert len(fetch_call.payload) == MAX_PAYLOAD_CHARACTERS
            assert fetch_call.payload_sha256 == expected_hash
        finally:
            await _delete_project_memory(store, project_id)
            await store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestResumePastTheStepViewCap:
    """Resume sees every completed and interrupted step, not only the shown ones."""

    async def test_steps_beyond_the_view_cap_are_reused_and_marked(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """With 60 completed and 60 in-progress steps, none is missed on resume."""
        store = build_graph_store("neo4j")
        await store.connect()
        project_id = f"resume-cap-{uuid4().hex[:8]}"
        task_name = "long task"
        try:
            memory = TaskMemory(store, project_id=project_id, agent_id="resume-test")
            created = await memory.create_task(task_name, "Finish the long task.")
            assert created.recorded
            for index in range(60):
                name = f"done-{index:02d}"
                noted = await memory.record_event(
                    task_name,
                    EventKind.NOTE,
                    name=f"step:{name}",
                    payload=f"result for {name}",
                )
                assert noted.event is not None
                await memory.set_step(
                    task_name,
                    name,
                    StepState.COMPLETED,
                    result_event_seq=noted.event.seq,
                )
            for index in range(60):
                await memory.set_step(
                    task_name, f"open-{index:02d}", StepState.IN_PROGRESS
                )

            model = _ScriptedModel(
                replies=[AIMessage(content="The long task is finished.")]
            )
            agent = _build(monkeypatch, store, project_id, model)
            result = await agent.ainvoke(
                {"task_name": task_name, "question": "Finish the long task."}
            )

            assert result["status"] == "answered"
            reused = _text(model.seen[0])
            assert "result for done-00" in reused
            assert "result for done-59" in reused
            assert "(omitted" not in reused

            lookup = await memory.get_task(task_name)
            assert lookup.view is not None
            assert lookup.view.step_counts[StepState.COMPLETED] == 60
            assert lookup.view.step_counts[StepState.IN_PROGRESS] == 0
            assert lookup.view.step_counts[StepState.UNKNOWN] == 60
        finally:
            await _delete_project_memory(store, project_id)
            await store.close()
