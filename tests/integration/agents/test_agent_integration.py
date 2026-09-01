"""Integration tests for agent components against real stores.

Tests the Ledger, tools, and agent build with real SearchEngine and
GraphStore. The agent-invocation test needs a real OpenAI-compatible
LLM endpoint; like the LLM ingestion tests, it reads its config from
``AGENT_LLM_*`` (or the shared ``LLM_*``) env vars and skips when none
is configured.
"""

import importlib.util
import os
from collections.abc import AsyncGenerator, Sequence
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from agrag.agents.build import build_agent
from agrag.agents.ledger import Ledger
from agrag.agents.settings import AgentLLMSettings
from agrag.agents.tools import make_tools
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.llm.client_config import LLMClientConfig
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings


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


class _FixedEmbedder(Embedder):
    """Embedder returning deterministic vectors."""

    model = "fixed"

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return deterministic vectors."""
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


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
class TestToolsIntegration:
    """Agent tools work with real SearchEngine."""

    @pytest.fixture(autouse=True)
    async def setup_engine(self) -> AsyncGenerator[None, None]:
        """Set up a SearchEngine with real stores."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        self.embedder = _FixedEmbedder()
        self.settings = RetrievalSettings(entity_labels=[self.label])
        self.engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        yield
        await self.store.execute_write(f"MATCH (n:{self.label}) DETACH DELETE n")
        await self.store.close()

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    async def test_make_tools_returns_five(self) -> None:
        """make_tools returns 5 tools."""
        ledger = Ledger()
        tools = make_tools(self.engine, ledger)
        assert len(tools) == 5

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    async def test_tool_names(self) -> None:
        """Tools have the expected names."""
        ledger = Ledger()
        tools = make_tools(self.engine, ledger)
        names = {t.name for t in tools}
        assert "search_source_text" in names
        assert "look_up_entity" in names
        assert "find_connection" in names
        assert "explore_related" in names
        assert "answer_from_graph_structure" in names


@pytest.mark.integration
@pytest.mark.enable_socket
class TestAgentBuildIntegration:
    """Agent build with real stores and mocked LLM."""

    @pytest.fixture(autouse=True)
    async def setup_engine(self) -> AsyncGenerator[None, None]:
        """Set up a SearchEngine."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        self.embedder = _FixedEmbedder()
        self.settings = RetrievalSettings(entity_labels=[self.label])
        self.engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        yield
        await self.store.execute_write(f"MATCH (n:{self.label}) DETACH DELETE n")
        await self.store.close()

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    def test_build_agent_returns_compiled_graph(self) -> None:
        """build_agent returns a compiled graph or _SimpleAgent."""
        settings = AgentLLMSettings(
            clients=[
                LLMClientConfig(
                    name="test",
                    provider="openai",
                    model="gpt-4o-mini",
                    api_key="test-key",
                )
            ]
        )
        agent = build_agent(engine=self.engine, llm_settings=settings)
        assert agent is not None
        assert hasattr(agent, "ainvoke")

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.skipif(
        not _agent_llm_configured(), reason="LLM endpoint not configured"
    )
    async def test_simple_agent_ainvoke(self) -> None:
        """The agent graph returns a response via the configured LLM."""
        settings = AgentLLMSettings.from_openai_compatible_env()
        agent = build_agent(engine=self.engine, llm_settings=settings)
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "test"}]}
        )
        assert "messages" in result
        assert len(result["messages"]) >= 1
