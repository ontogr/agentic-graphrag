"""Integration coverage for typed, evidence-checked agent answers."""

import importlib.util
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr
from pytest import MonkeyPatch

from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.common.data_models.agent_answer import AgentAnswer
from agrag.common.data_models.task import EventKind
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.history import ConversationHistory
from tests.integration._backend import build_test_store
from tests.integration.retrieval.evidence._corpus import (
    KEEP_TEXT,
    make_document,
    span_evidence_id,
)
from tests.integration.retrieval.evidence.conftest import EvidenceEnv


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _FinalModel(BaseChatModel):
    """Return one structured final answer through the agent tool contract."""

    answer: AgentAnswer | None
    repair_answer: AgentAnswer | None = None
    fetch_ids: list[str] = []
    calls: int = 0
    _tool_name: str = PrivateAttr(default="AgentAnswer")

    @property
    def _llm_type(self) -> str:
        """Return the scripted model type."""
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_FinalModel":
        """Return the structured-output tool call requested by the agent."""
        schema = tools[-1]
        if isinstance(schema, dict):
            self._tool_name = schema.get("function", {}).get("name", "AgentAnswer")
        else:
            self._tool_name = schema.name
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Return the typed answer as a tool call."""
        if self.fetch_ids and not self.calls:
            self.calls += 1
            return ChatResult(
                generations=[
                    ChatGeneration(
                        message=AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "name": "fetch_evidence",
                                    "args": {"evidence_ids": self.fetch_ids},
                                    "id": "fetch-source",
                                }
                            ],
                        )
                    )
                ]
            )
        answer = (
            self.repair_answer if self.calls > bool(self.fetch_ids) else self.answer
        )
        self.calls += 1
        if answer is None:
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content="Plain text."))]
            )
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": self._tool_name,
                                "args": answer.model_dump(),
                                "id": "final-answer",
                            }
                        ],
                    )
                )
            ]
        )


class _ZeroEmbedder(Embedder):
    """Embedder used when the answer requires no document search."""

    model = "answer-test"

    async def dimensions(self) -> int:
        """Return the vector size."""
        return 2

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one fixed vector per input."""
        return [[0.0, 1.0] for _ in texts]


def _build(
    monkeypatch: MonkeyPatch,
    store: GraphStore,
    project_id: str,
    model: _FinalModel,
    settings: AgentSettings | None = None,
    *,
    scope: frozenset[str] = frozenset(),
) -> Any:
    """Build an agent with the supplied model."""
    monkeypatch.setattr("agrag.agents.build.build_chat_model", lambda _config: model)
    return build_agent(
        graph_store=store,
        embedder=_ZeroEmbedder(),
        scope=scope,
        project_id=project_id,
        agent_id="answer-test",
        llm_settings=AgentLLMSettings(
            clients=[{"name": "test", "provider": "openai-generic", "model": "test"}]
        ),
        agent_settings=settings or AgentSettings(),
    )


async def _delete_project_history(store: GraphStore, project_id: str) -> None:
    """Delete task history rows created by this test."""
    params = {"project_id": project_id}
    await store.execute_write(
        "MATCH (t:Task {project_id: $project_id}) "
        "OPTIONAL MATCH (t)-[:HAS_EVENT|HAS_STEP]->(child) DETACH DELETE child, t",
        params,
    )
    await store.execute_write(
        "MATCH (r:Request {project_id: $project_id}) DETACH DELETE r", params
    )
    await store.execute_write(
        "MATCH (p:Project {project_id: $project_id}) DETACH DELETE p", params
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestAgentAnswerIntegration:
    """Final status comes from the answer schema, not its wording."""

    async def test_validated_answer_renders_sources_after_repair(
        self, monkeypatch: MonkeyPatch, evidence_env: EvidenceEnv, tmp_path: Path
    ) -> None:
        """The real agent fetches, repairs, then links validated contained spans."""
        env = evidence_env
        text = KEEP_TEXT + "\nCitation edition."
        await env.graph.add(
            documents=[
                make_document(env.keep, text).model_copy(
                    update={
                        "title": "Privacy notice",
                        "uri": "https://example.org/privacy",
                    }
                )
            ]
        )
        parent = span_evidence_id(env.keep, text, 0, 30)
        narrower = span_evidence_id(env.keep, text, 0, 10)
        unfetched = span_evidence_id(env.keep, text, 0, 40)
        final_text = f"Claim [{narrower}; {parent}]. Unverified [{unfetched}]."
        model = _FinalModel(
            fetch_ids=[parent],
            answer=AgentAnswer(
                answer=f"Claim [{unfetched}].",
                support_status="supported",
                citations=[unfetched],
            ),
            repair_answer=AgentAnswer(
                answer=final_text, support_status="supported", citations=[narrower]
            ),
        )
        project_id = f"citation-answer-{uuid4().hex}"
        try:
            result = await _build(
                monkeypatch, env.store, project_id, model, scope=frozenset({env.keep})
            ).ainvoke({"task_name": "source-citations", "question": "Cite the source."})

            assert result["answer"] == (
                "Claim [[1]](https://example.org/privacy). "
                f"Unverified [{unfetched}]."
                "\n\n### Sources\n\n"
                "[1] [Privacy notice](https://example.org/privacy)"
            )
            assert result["status"] == "partial"
            assert result["invalid_citations"] == [unfetched]
            assert [source.evidence_id for source in result["citations"]] == [parent]
            assert result["citations"][0].text == text[:30]
            assert model.calls == 3
            (tmp_path / "agent-citations.json").write_text(
                json.dumps(
                    {
                        "answer": result["answer"],
                        "status": result["status"],
                        "invalid_citations": result["invalid_citations"],
                        "citations": [
                            item.model_dump(mode="json") for item in result["citations"]
                        ],
                    },
                    indent=2,
                )
            )
        finally:
            await _delete_project_history(env.store, project_id)

    async def test_insufficient_evidence_status_is_structured(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """A clear answer remains insufficient when the model says so."""
        store = build_test_store()
        await store.connect()
        project_id = f"answer-{uuid4().hex}"
        task_name = f"task-{uuid4().hex}"
        history = ConversationHistory(
            store, project_id=project_id, agent_id="answer-test"
        )
        try:
            model = _FinalModel(
                answer=AgentAnswer(
                    answer="I cannot establish the date from available sources.",
                    support_status="insufficient_evidence",
                    citations=[],
                )
            )
            result = await _build(monkeypatch, store, project_id, model).ainvoke(
                {"task_name": task_name, "question": "What is the date?"}
            )

            assert result["status"] == "insufficient_evidence"
            assert result["answer"].startswith("I cannot establish")
            events = await history.list_events(task_name, limit=20)
            assert any(event.kind is EventKind.MESSAGE for event in events.events)
        finally:
            await _delete_project_history(store, project_id)
            await store.close()

    async def test_missing_structured_answer_is_partial(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Plain text without the answer schema is not accepted as a final answer."""
        store = build_test_store()
        await store.connect()
        project_id = f"answer-missing-{uuid4().hex}"
        task_name = f"task-{uuid4().hex}"
        try:
            result = await _build(
                monkeypatch,
                store,
                project_id,
                _FinalModel(answer=None),
                AgentSettings(recursion_limit=4),
            ).ainvoke({"task_name": task_name, "question": "What is the date?"})

            assert result["status"] == "partial"
            assert result["answer"] == ""
        finally:
            await _delete_project_history(store, project_id)
            await store.close()

    async def test_grouped_and_malformed_citations_are_repaired_once(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """An invalid grouped citation set gets one structured repair attempt."""
        store = build_test_store()
        await store.connect()
        project_id = f"answer-repair-{uuid4().hex}"
        task_name = f"task-{uuid4().hex}"
        first_id = f"ev1:s:{uuid4()}:0123456789abcdef:1-2"
        second_id = f"ev1:s:{uuid4()}:fedcba9876543210:3-4"
        model = _FinalModel(
            answer=AgentAnswer(
                answer=f"Claim [{first_id}, {second_id}] and [ev1:s:invalid].",
                support_status="supported",
                citations=[first_id, second_id, "ev1:s:invalid"],
            ),
            repair_answer=AgentAnswer(
                answer="I removed the unsupported citations.",
                support_status="supported",
                citations=[],
            ),
        )
        try:
            result = await _build(monkeypatch, store, project_id, model).ainvoke(
                {"task_name": task_name, "question": "Answer with citations."}
            )

            assert result["status"] == "answered"
            assert result["answer"] == "I removed the unsupported citations."
            assert result["invalid_citations"] == []
            assert model.calls == 2
        finally:
            await _delete_project_history(store, project_id)
            await store.close()
