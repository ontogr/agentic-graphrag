"""Tests how the agrag system turns an agent run into a benchmark answer.

The agent is replaced at the ``build_agent`` boundary with one that returns a
canned run and a real ledger. Nothing calls a model or a database.
"""

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import GraphRecursionError

from agrag.agents.ledger import Ledger
from agrag.chunking import Chunking, RecursiveChunker
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.query_value import QueryValue
from agrag.common.data_models.search_result import SearchResult
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
        chunking=Chunking(fallback=RecursiveChunker(chunk_size=100)),
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
            # The real agent rewrites the list it gets, dicts to message objects.
            payload["messages"][:] = [
                HumanMessage(content=m["content"]) for m in payload["messages"]
            ]
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
        source = uuid4()
        system._store.execute_read.return_value = [
            {
                "n": {
                    "id": str(source),
                    "document_id": str(document_id),
                    "provenance": json.dumps(
                        {"kind": "text", "char_start": 20, "char_end": 40}
                    ),
                }
            }
        ]
        ledger = Ledger()
        cited = ledger.cite(
            SearchResult(
                item=Chunk(
                    document_id=document_id,
                    text="hello",
                    provenance=TextProvenance(char_start=6, char_end=11),
                ),
                score=1.0,
                method="chunk",
            )
        )
        entity = ledger.cite(
            SearchResult(
                item=Entity(
                    id=uuid4(), label="Thing", name="a", source_chunk_ids=[source]
                ),
                score=1.0,
                method="entity",
            )
        )
        ledger.cite(SearchResult(item=QueryValue(value=1), score=1.0, method="q"))
        uncited = ledger.keys[-1]
        run = {
            "messages": [AIMessage(content=f"It says hello [{cited}] and [{entity}].")],
            "ledger": ledger,
        }
        agent, seen = _agent_returning(run)
        monkeypatch.setattr(agrag_system, "build_agent", lambda **_: agent)

        answer = await system.answer(QUESTION)

        assert answer.cited_chunks[0].uri == "corpus/doc.txt"
        assert (answer.cited_chunks[0].char_start, answer.cited_chunks[0].char_end) == (
            6,
            11,
        )
        assert answer.non_chunk_citations == 1
        assert [(c.uri, c.char_start, c.char_end) for c in answer.source_chunks] == [
            ("corpus/doc.txt", 20, 40)
        ]
        assert uncited not in answer.text
        assert [m.content for m in seen["payload"]["messages"]] == [
            m["content"] for m in QUESTION.messages
        ]
        assert QUESTION.query == "second"
        assert all(isinstance(m, dict) for m in QUESTION.messages)

    async def test_recursion_limit_and_empty_answer_are_agent_failures(
        self, monkeypatch
    ):
        """The runner scores these 0, so the system must raise its own error."""
        system = _system(text_document("hello " * 50, uri="d"))

        for run in (
            GraphRecursionError("limit"),
            {"messages": [AIMessage(content="  ")], "ledger": Ledger()},
            {"messages": [], "ledger": Ledger()},
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
