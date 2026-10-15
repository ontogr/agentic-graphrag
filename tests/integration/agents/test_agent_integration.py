"""Integration tests for agent builds and ledger behavior against real stores.

The agent-invocation test needs a real OpenAI-compatible
LLM endpoint; like the LLM ingestion tests, it reads its config from
``AGENT_LLM_*`` (or the shared ``LLM_*``) env vars and skips when none
is configured.
"""

import importlib.util
import os
import re
from collections.abc import AsyncGenerator, Sequence
from uuid import UUID, uuid4

import pytest
from dotenv import load_dotenv

from agrag.agents.build import build_agent
from agrag.agents.ledger import Ledger
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.chunking import Chunker
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.search_result import SearchResult
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion.graph import Graph
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration.retrieval.evidence._corpus import (
    NoEntityExtractor,
    make_document,
)


neo4j_missing = importlib.util.find_spec("neo4j") is None


def _agent_llm_configured() -> bool:
    """Return True when an agent LLM endpoint is configured.

    Checks ``AGENT_LLM_*`` then the shared ``LLM_*`` vars after loading
    ``.env``, matching ``AgentLLMSettings.from_openai_compatible_env``.
    """
    load_dotenv()
    base_url = os.environ.get("AGENT_LLM_BASE_URL") or os.environ.get("LLM_BASE_URL")
    api_key = os.environ.get("AGENT_LLM_API_KEY") or os.environ.get("LLM_API_KEY")
    return bool(base_url and api_key)


class _KeywordEmbedder(Embedder):
    """Embedder that separates texts by their first keyword.

    Two keyword dimensions, one per keyword, padded to four to match
    the vector indexes the fixtures create, so texts containing
    different keywords land far apart and no two fixtures tie in
    similarity. The all-equal vectors a fixed embedder produces make
    every candidate equally near the query, leaving the returned order
    to the backend. A text with no keyword gets a neutral uniform
    vector, since Neo4j rejects an all-zero query vector.
    """

    model = "keyword"
    _KEYWORDS = ("alice", "acme")

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return FAKE_EMBEDDING_DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one padded keyword vector per text over the keywords."""
        vectors = []
        for text in texts:
            lowered = text.lower()
            keyword = [0.0, 0.0]
            for index, word in enumerate(self._KEYWORDS):
                if word in lowered:
                    keyword[index] = 1.0
            if not any(keyword):
                keyword = [0.5, 0.5]
            vectors.append([*keyword, 0.0, 0.0])
        return vectors


@pytest.mark.integration
@pytest.mark.enable_socket
class TestLedgerIntegration:
    """Ledger citation tracking with real SearchResults."""

    def test_cite_assigns_stable_keys(self) -> None:
        """Same entity always gets the same citation key."""
        ledger = Ledger()
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        r1 = SearchResult(item=ent, score=0.9, method="entity")
        r2 = SearchResult(item=ent, score=0.8, method="chunk")

        k1 = ledger.cite(r1)
        k2 = ledger.cite(r2)
        assert k1 == k2
        assert k1.startswith("E")

    def test_different_entities_get_different_keys(self) -> None:
        """Different entities get different citation keys."""
        ledger = Ledger()
        r1 = SearchResult(
            item=Entity(id=uuid4(), label="Person", name="Alice"),
            score=0.9,
            method="entity",
        )
        r2 = SearchResult(
            item=Entity(id=uuid4(), label="Person", name="Bob"),
            score=0.8,
            method="entity",
        )
        k1 = ledger.cite(r1)
        k2 = ledger.cite(r2)
        assert k1 != k2

    def test_resolve_returns_correct_result(self) -> None:
        """resolve() returns the SearchResult behind a key."""
        ledger = Ledger()
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        r = SearchResult(item=ent, score=0.9, method="test")
        key = ledger.cite(r)
        resolved = ledger.resolve(key)
        assert resolved is not None
        assert resolved.item.id == ent.id

    def test_render_includes_citation_key(self) -> None:
        """render() includes the citation key in output."""
        ledger = Ledger()
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        r = SearchResult(item=ent, score=0.9, method="test")
        text = ledger.render(r)
        assert "[E1]" in text
        assert "Alice" in text


@pytest.mark.integration
@pytest.mark.enable_socket
class TestAgentBuildIntegration:
    """Agent build with real stores and mocked LLM."""

    @pytest.fixture(autouse=True)
    async def setup_engine(self) -> AsyncGenerator[None, None]:
        """Set up a graph store and isolated labels for this test."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        self.other_label = validate_identifier(f"Organization_{uuid4().hex[:8]}")
        self.embedder = _KeywordEmbedder()
        self.document_one = f"agent-integration-one-{uuid4().hex[:8]}"
        self.document_two = f"agent-integration-two-{uuid4().hex[:8]}"
        yield
        for label in (self.label, self.other_label):
            await self.store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
        await self.store.close()

    async def _seed_entity(self, label: str, name: str) -> UUID:
        """Write one searchable entity carrying the fixture's properties."""
        entity_id = uuid4()
        await self.store.upsert_nodes(
            label,
            [
                NodeRecord(
                    id=entity_id,
                    labels=[label],
                    properties={
                        "name": name,
                        "merge_key": f"{label}:{name.lower()}",
                        "merge_count": 1,
                        "source_chunk_ids": [],
                        "embedding": await self.embedder.embed_one(name),
                        "created_at": "2024-01-01T00:00:00",
                    },
                )
            ],
        )
        await self.store.ensure_vector_index(
            label=label,
            vector_property="embedding",
            dimensions=4,
            distance=Distance.COSINE,
        )
        return entity_id

    async def _seed_relation(self, rel_type: str, start_id: UUID, end_id: UUID) -> None:
        """Write one directed relationship."""
        await self.store.upsert_relations(
            [
                RelationRecord(
                    id=uuid4(),
                    type=rel_type,
                    start_id=start_id,
                    end_id=end_id,
                    properties={},
                )
            ]
        )

    async def _seed_chunk(self, text: str) -> None:
        """Add a document holding the text, as ingestion would write it."""
        graph = await Graph.open(
            schema=GraphSchema(
                name="agent_seed", version="1", entities=[], relations=[]
            ),
            graph_store=self.store,
            embedder=self.embedder,
            extractor=NoEntityExtractor(),
            chunker=Chunker(size=2000),
        )
        await graph.add(documents=[make_document(self.document_one, text)])
        await self.store.execute_read("CALL db.awaitIndexes(60)")

    @staticmethod
    def _message_text(result: dict) -> str:
        """Return the final message's text, whatever shape it arrived in."""
        messages = result.get("messages", [])
        if not messages:
            return ""
        last = messages[-1]
        if isinstance(last, dict):
            return str(last.get("content", ""))
        return str(getattr(last, "content", ""))

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    def test_build_agent_returns_compiled_graph(self) -> None:
        """build_agent returns an agent that exposes ainvoke."""
        settings = AgentLLMSettings.from_openai_compatible_env()
        agent = build_agent(
            graph_store=self.store,
            embedder=self.embedder,
            scope=frozenset({self.document_one, self.document_two}),
            project_id="agent-integration",
            agent_id="integration-agent",
            llm_settings=settings,
        )
        assert agent is not None
        assert hasattr(agent, "ainvoke")

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.skipif(
        not _agent_llm_configured(), reason="LLM endpoint not configured"
    )
    async def test_agent_ainvoke_returns_a_run_result(self) -> None:
        """A run returns the typed result through the configured LLM."""
        settings = AgentLLMSettings.from_openai_compatible_env()
        agent = build_agent(
            graph_store=self.store,
            embedder=self.embedder,
            scope=frozenset({self.document_one, self.document_two}),
            project_id="agent-integration",
            agent_id="integration-agent",
            llm_settings=settings,
        )
        task_name = f"run-result-{uuid4().hex[:8]}"
        result = await agent.ainvoke({"task_name": task_name, "question": "test"})
        assert result["task"]["name"] == task_name
        assert result["status"] in {
            "answered",
            "insufficient_evidence",
            "partial_retrieval",
            "partial",
            "recording_failed",
            "budget_exhausted",
        }

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.skipif(
        not _agent_llm_configured(), reason="LLM endpoint not configured"
    )
    async def test_multi_hop_question_cites_evidence(self) -> None:
        """A multi-hop answer cites evidence from its research transcript."""
        alice = await self._seed_entity(self.label, "Alice")
        acme = await self._seed_entity(self.other_label, "Acme")
        await self._seed_relation("WORKS_FOR", alice, acme)
        await self._seed_chunk(
            "Alice works at Acme, where she founded the engines team."
        )

        settings = AgentLLMSettings.from_openai_compatible_env()
        agent = build_agent(
            graph_store=self.store,
            embedder=self.embedder,
            scope=frozenset({self.document_one, self.document_two}),
            project_id="agent-integration",
            agent_id="integration-agent",
            llm_settings=settings,
        )
        result = await agent.ainvoke(
            {
                "task_name": f"multi-hop-question-{uuid4().hex[:8]}",
                "question": (
                    "Where does Alice work, and what does the source "
                    "text say about her time there?"
                ),
            }
        )

        # The model chooses its own decomposition and synthesis style, so
        # the number of tool results is not deterministic run to run. The
        # final answer must still cite evidence from the transcript.
        # Exclude the final answer message itself, so a citation only
        # counts as evidence when it also appears in the research messages
        # that produced the answer.
        transcript = "\n".join(
            self._message_text({"messages": [message]})
            for message in result.get("messages", [])[:-1]
        )
        citation_pattern = r"ev1:[sc]:[0-9a-f-]+:[0-9a-f-]+:[0-9a-f-]+"
        transcript_keys = set(re.findall(citation_pattern, transcript))
        assert transcript_keys, "research findings contain no citation keys"
        answer = self._message_text(result)
        answer_keys = set(re.findall(citation_pattern, answer))
        assert answer_keys & transcript_keys, "final answer cites no research evidence"

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.skipif(
        not _agent_llm_configured(), reason="LLM endpoint not configured"
    )
    async def test_under_evidenced_question_does_not_fabricate_a_year(self) -> None:
        """A question the graph cannot answer does not invent a year."""
        await self._seed_entity(self.label, "Alice")

        settings = AgentLLMSettings.from_openai_compatible_env()
        agent = build_agent(
            graph_store=self.store,
            embedder=self.embedder,
            scope=frozenset({self.document_one, self.document_two}),
            project_id="agent-integration",
            agent_id="integration-agent",
            llm_settings=settings,
        )
        result = await agent.ainvoke(
            {
                "task_name": f"under-evidenced-question-{uuid4().hex[:8]}",
                "question": "What year did Alice found the engines team?",
            }
        )

        answer = self._message_text(result)
        assert not re.search(r"\b(?:1\d{3}|20\d{2})\b", answer)

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.skipif(
        not _agent_llm_configured(), reason="LLM endpoint not configured"
    )
    async def test_tool_budget_ends_the_run_as_budget_exhausted(
        self,
    ) -> None:
        """A one-call tool budget ends the run with the budget_exhausted status."""
        alice = await self._seed_entity(self.label, "Alice")
        acme = await self._seed_entity(self.other_label, "Acme")
        await self._seed_relation("WORKS_FOR", alice, acme)
        await self._seed_chunk(
            "Alice works at Acme, where she founded the engines team."
        )

        settings = AgentLLMSettings.from_openai_compatible_env()
        agent = build_agent(
            graph_store=self.store,
            embedder=self.embedder,
            scope=frozenset({self.document_one, self.document_two}),
            project_id="agent-integration",
            agent_id="integration-agent",
            llm_settings=settings,
            agent_settings=AgentSettings(max_tool_calls=1),
        )
        result = await agent.ainvoke(
            {
                "task_name": f"tool-budget-question-{uuid4().hex[:8]}",
                "question": (
                    "Where does Alice work, and what does the source "
                    "text say about her time there?"
                ),
            }
        )

        # The run ends with an answer and the events recorded so far, not a
        # GraphRecursionError. One call is enough to discover but not to fetch,
        # so the answer must not cite evidence that was never checked.
        assert result["status"] == "budget_exhausted"
        assert result["answer"]
        assert result["citations"] == []
        assert result["task"]["last_event_seq"] > 0
