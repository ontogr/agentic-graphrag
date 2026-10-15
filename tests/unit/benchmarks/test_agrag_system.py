"""Tests how the agrag system turns an agent run into a benchmark answer.

The agent is replaced at the ``build_agent`` boundary with one that returns a
canned run and a real ledger. Nothing calls a model or a database.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.errors import GraphRecursionError

from agrag.chunking import Chunker
from agrag.common.data_models.document import Document
from agrag.common.data_models.evidence import (
    EvidenceKind,
    EvidenceReference,
    FetchOutcome,
    FetchStatus,
)
from benchmarks.datasets.base import text_document
from benchmarks.models import BenchmarkQuestion
from benchmarks.systems import agrag as agrag_system
from benchmarks.systems.agrag import AgragSystem
from benchmarks.systems.base import AgentFailureError
from tests.unit.benchmarks.fakes import SCHEMA


QUESTION = BenchmarkQuestion(
    id="q",
    corpus_id="c",
    messages=[
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "second"},
    ],
    group="g",
)


def _system(document: Document) -> AgragSystem:
    return AgragSystem(
        store=AsyncMock(),
        schema=SCHEMA,
        chunking=Chunker(size=100),
        documents=[document],
        settings=MagicMock(),
        tracer=MagicMock(),
        embedder=MagicMock(),
    )


def _agent_returning(run):
    seen = {}

    class Agent:
        async def ainvoke(self, payload):
            seen["payload"] = payload
            if isinstance(run, Exception):
                raise run
            return run

    return Agent(), seen


class TestAgragSystem:
    """Citation resolution, failures and the messages the agent gets."""

    async def test_cited_chunks_carry_document_uri_and_offsets(self, monkeypatch):
        """A cited chunk names its document and offsets, and others count apart."""
        document = text_document("hello " * 50, uri="corpus/doc.txt")
        system = _system(document)
        document_id = Document.node_id_for(document_key=document.resolved_document_key)
        evidence_id = f"ev1:s:{document_id}:0123456789abcdef:6-11"
        run = {
            "answer": f"It says hello [{evidence_id}].",
            "status": "answered",
            "citations": [
                FetchOutcome(
                    evidence_id=evidence_id,
                    status=FetchStatus.OK,
                    text="hello",
                    reference=EvidenceReference(
                        kind=EvidenceKind.SPAN,
                        document_node_id=document_id,
                        content_hash_prefix="0123456789abcdef",
                        char_start=6,
                        char_end=11,
                    ),
                )
            ],
            "invalid_citations": [],
            "task": {"name": "q", "last_event_seq": 0},
            "messages": [],
        }
        agent, seen = _agent_returning(run)
        monkeypatch.setattr(agrag_system, "build_agent", lambda **_: agent)

        answer = await system.answer(QUESTION)

        assert answer.cited_chunks[0].uri == "corpus/doc.txt"
        assert (answer.cited_chunks[0].char_start, answer.cited_chunks[0].char_end) == (
            6,
            11,
        )
        assert answer.non_chunk_citations == 0
        assert answer.source_chunks == []
        assert evidence_id in answer.text
        assert seen["payload"] == {"task_name": "q", "question": "second"}
        assert QUESTION.query == "second"
        assert all(isinstance(m, dict) for m in QUESTION.messages)

    async def test_recursion_limit_and_empty_answer_are_agent_failures(
        self, monkeypatch
    ):
        """The runner scores these 0, so the system must raise its own error."""
        system = _system(text_document("hello " * 50, uri="d"))

        for run in (
            GraphRecursionError("limit"),
            {
                "answer": "  ",
                "status": "answered",
                "citations": [],
                "invalid_citations": [],
                "task": {"name": "q", "last_event_seq": 0},
                "messages": [],
            },
            {
                "answer": "Incomplete",
                "status": "budget_exhausted",
                "citations": [],
                "invalid_citations": [],
                "task": {"name": "q", "last_event_seq": 0},
                "messages": [],
            },
        ):
            agent, _ = _agent_returning(run)
            monkeypatch.setattr(
                agrag_system, "build_agent", lambda agent=agent, **_: agent
            )

            with pytest.raises(AgentFailureError):
                await system.answer(QUESTION)

    async def test_other_agent_errors_are_not_agent_failures(self, monkeypatch):
        """A connection error must abort the run, not score 0."""
        system = _system(text_document("hello " * 50, uri="d"))
        agent, _ = _agent_returning(ConnectionError("reset"))
        monkeypatch.setattr(agrag_system, "build_agent", lambda **_: agent)

        with pytest.raises(ConnectionError):
            await system.answer(QUESTION)

    def test_refuses_to_run_without_deepagents(self, monkeypatch):
        """The fallback agent reads only the last message."""
        monkeypatch.setattr(agrag_system.importlib.util, "find_spec", lambda name: None)

        with pytest.raises(RuntimeError, match="deepagents"):
            agrag_system.require_deepagents()
