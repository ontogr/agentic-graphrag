"""Integration tests for agent components against real stores.

Tests the Ledger, tools, and agent build with real SearchEngine and
GraphStore. The agent-invocation test needs a real OpenAI-compatible
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
from agrag.agents.tools import make_tools
from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    RelationType,
)
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.search_result import SearchResult
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings


neo4j_missing = importlib.util.find_spec("neo4j") is None


def _tool_named(tools: list, name: str):
    """Return the tool with the given name."""
    return next(tool for tool in tools if tool.name == name)


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
        return 4

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
class TestToolsIntegration:
    """Agent tools work with real SearchEngine."""

    @pytest.fixture(autouse=True)
    async def setup_engine(self) -> AsyncGenerator[None, None]:
        """Set up a SearchEngine with real stores and delete this test's rows."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        suffix = uuid4().hex[:8]
        self.label = validate_identifier(f"Person_{suffix}")
        self.other_label = validate_identifier(f"Organization_{suffix}")
        self.embedder = _FixedEmbedder()
        self.schema = GraphSchema(
            name="agent_integration",
            version="1",
            entities=[
                EntityType(label=self.label, description="A person."),
                EntityType(label=self.other_label, description="An organization."),
            ],
            relations=[],
        )
        self.settings = RetrievalSettings()
        self.engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
            graph_schema=self.schema,
        )
        self.chunk_ids: list = []
        # Chunk parsing requires a real document id, so the two document
        # partitions the filter tests use are UUIDs, not arbitrary strings.
        self.document_one = str(uuid4())
        self.document_two = str(uuid4())
        yield
        for label in (self.label, self.other_label):
            await self.store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
        if self.chunk_ids:
            # Chunk nodes are shared by every suite, and the native index
            # cannot be dropped per test, so teardown deletes only the ids
            # this test wrote.
            await self.store.execute_write(
                f"MATCH (n:{CHUNK_LABEL}) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(chunk_id) for chunk_id in self.chunk_ids]},
            )
        await self.store.close()

    async def _seed_entities(self, label: str, names: list[str]) -> None:
        """Write entities with embeddings so native vector search finds them."""
        records = [
            NodeRecord(
                id=uuid4(),
                labels=[label],
                properties={
                    "name": name,
                    "merge_key": f"{label}:{name.lower()}",
                    "merged_from": [],
                    "merge_count": 1,
                    "source_chunk_ids": [],
                    "embedding": await self.embedder.embed_one(name),
                    "created_at": "2024-01-01T00:00:00",
                },
            )
            for name in names
        ]
        await self.store.upsert_nodes(label, records)
        await self.store.ensure_vector_index(
            label=label,
            vector_property="embedding",
            dimensions=4,
            distance=Distance.COSINE,
        )

    async def _seed_entity_with_properties(
        self, label: str, name: str, properties: dict
    ) -> UUID:
        """Write one searchable entity carrying domain properties."""
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
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                        "embedding": await self.embedder.embed_one(name),
                        "created_at": "2024-01-01T00:00:00",
                        **properties,
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

    async def _seed_document_chunk(self, document_id: str, text: str) -> None:
        """Write one chunk belonging to a named document partition."""
        chunk = Chunk(
            document_id=UUID(document_id),
            index=0,
            text=text,
            provenance=TextProvenance(char_start=0, char_end=len(text)),
        )
        chunk.embedding = await self.embedder.embed_one(text)
        self.chunk_ids.append(chunk.id)
        await self.store.upsert_nodes(
            CHUNK_LABEL,
            [
                NodeRecord(
                    id=chunk.id,
                    labels=[CHUNK_LABEL],
                    properties={
                        "document_id": document_id,
                        "index": 0,
                        "text": text,
                        "provenance": '{"kind":"text","char_start":0,'
                        f'"char_end":{len(text)}}}',
                        "heading_path": [],
                        "content_kind": "text",
                        "embedding": chunk.embedding,
                        "created_at": "2024-01-01T00:00:00",
                    },
                )
            ],
        )
        await self.store.ensure_vector_index(
            label=CHUNK_LABEL,
            vector_property="embedding",
            dimensions=4,
            distance=Distance.COSINE,
        )

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    async def test_tool_count_grows_to_eleven_with_cypher_tool(self) -> None:
        """Five discovery, four traversal, calculator, and generated Cypher."""
        tools = make_tools(self.engine, Ledger())
        assert len(tools) == 11

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    async def test_scoped_tool_set_omits_query_graph_directly(self) -> None:
        """A caller scope removes the unscoped-only generated-Cypher tool."""
        scoped = make_tools(
            self.engine, Ledger(), filters=SearchFilters(labels=[self.label])
        )
        assert len(scoped) == 10
        assert "query_graph_directly" not in {tool.name for tool in scoped}

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    async def test_tool_names(self) -> None:
        """Tools have the expected names and their per-call parameters."""
        tools = make_tools(self.engine, Ledger())
        for tool in tools:
            if tool.name not in {
                "search_source_text",
                "look_up_entity",
                "explore_related",
                "answer_from_graph_structure",
                "answer_thematic_question",
            }:
                continue
            assert "query" in tool.args_schema.model_fields
            assert "limit" in tool.args_schema.model_fields

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    async def test_describe_entity_renders_real_property_values(self) -> None:
        """The rendered text carries the stored properties, not just a cite."""
        await self._seed_entity_with_properties(
            self.label,
            "Ada",
            {"description": "A mathematician.", "born": 1815},
        )
        tool = _tool_named(make_tools(self.engine, Ledger()), "describe_entity")

        rendered = await tool.ainvoke({"entity": "Ada"})

        assert "- description: A mathematician." in rendered
        assert "- born: 1815" in rendered

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    async def test_traversal_cannot_leave_the_callers_property_scope(self) -> None:
        """Entities from another tenant are neither resolved nor traversed."""
        mine = await self._seed_entity_with_properties(
            self.label, "Ada", {"tenant_id": "tenant-a"}
        )
        outside = await self._seed_entity_with_properties(
            self.label, "Ada", {"tenant_id": "tenant-b"}
        )
        in_scope_neighbour = await self._seed_entity_with_properties(
            self.other_label, "Engines", {"tenant_id": "tenant-a"}
        )
        hidden_neighbour = await self._seed_entity_with_properties(
            self.other_label, "Shell", {"tenant_id": "tenant-b"}
        )
        await self._seed_relation("FOUNDED", mine, in_scope_neighbour)
        await self._seed_relation("FOUNDED", outside, hidden_neighbour)

        scoped = make_tools(
            self.engine,
            Ledger(),
            filters=SearchFilters(properties={"tenant_id": "tenant-a"}),
        )
        tool = _tool_named(scoped, "find_related_entities")

        rendered = await tool.ainvoke({"entity": "Ada", "relation_type": "FOUNDED"})

        assert "Engines" in rendered
        assert "Shell" not in rendered

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    async def test_traversal_refuses_a_relation_type_outside_the_scoped_allowlist(
        self,
    ) -> None:
        """A scoped caller cannot traverse a relation type it excluded."""
        person = await self._seed_entity_with_properties(self.label, "Ada", {})
        org = await self._seed_entity_with_properties(self.other_label, "Engines", {})
        await self._seed_relation("FOUNDED", person, org)
        await self._seed_relation("WORKS_FOR", person, org)
        scoped = make_tools(
            self.engine,
            Ledger(),
            filters=SearchFilters(relation_types=["WORKS_FOR"]),
        )
        tool = _tool_named(scoped, "find_related_entities")

        rendered = await tool.ainvoke({"entity": "Ada", "relation_type": "FOUNDED"})

        assert "outside this agent's permitted scope" in rendered
        assert "Engines" not in rendered

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    async def test_look_up_entity_applies_a_label_filter(self) -> None:
        """A labels argument restricts real native entity search."""
        await self._seed_entities(self.label, ["Alice"])
        await self._seed_entities(self.other_label, ["Acme"])
        tool = _tool_named(make_tools(self.engine, Ledger()), "look_up_entity")

        rendered = await tool.ainvoke({"query": "who?", "labels": [self.other_label]})

        assert "Acme" in rendered
        assert "Alice" not in rendered

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    async def test_explore_related_applies_both_filter_dimensions(self) -> None:
        """Labels and document ids both restrict a real hybrid search."""
        await self._seed_entities(self.label, ["Alice"])
        await self._seed_entities(self.other_label, ["Acme"])
        await self._seed_document_chunk(self.document_one, "Alice works at Acme")
        await self._seed_document_chunk(self.document_two, "Bob left Acme")
        tool = _tool_named(make_tools(self.engine, Ledger()), "explore_related")

        rendered = await tool.ainvoke(
            {
                "query": "who works where?",
                "labels": [self.label],
                "document_ids": [self.document_one],
            }
        )

        assert "Alice" in rendered
        assert "Alice works at Acme" in rendered
        assert "Bob left Acme" not in rendered

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    async def test_look_up_entity_refuses_labels_outside_the_caller_scope(
        self,
    ) -> None:
        """A caller scoped to one label cannot reach another through a tool."""
        await self._seed_entities(self.label, ["Alice"])
        await self._seed_entities(self.other_label, ["Acme"])
        scoped = make_tools(
            self.engine, Ledger(), filters=SearchFilters(labels=[self.label])
        )
        tool = _tool_named(scoped, "look_up_entity")

        rendered = await tool.ainvoke({"query": "who?", "labels": [self.other_label]})

        assert "outside this agent's permitted scope" in rendered
        assert "Acme" not in rendered

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    async def test_search_source_text_refuses_cross_document_requests(self) -> None:
        """A caller scoped to one document cannot read another through a tool."""
        await self._seed_document_chunk(self.document_one, "Alice works at Acme")
        await self._seed_document_chunk(self.document_two, "Bob left Acme")
        scoped = make_tools(
            self.engine,
            Ledger(),
            filters=SearchFilters(document_ids=[self.document_one]),
        )
        tool = _tool_named(scoped, "search_source_text")

        rendered = await tool.ainvoke(
            {"query": "who?", "document_ids": [self.document_two]}
        )

        assert "outside this agent's permitted scope" in rendered
        assert "Bob left Acme" not in rendered

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    async def test_scoped_document_search_returns_only_the_scoped_document(
        self,
    ) -> None:
        """The caller's document scope reaches real chunk retrieval."""
        await self._seed_document_chunk(self.document_one, "Alice works at Acme")
        await self._seed_document_chunk(self.document_two, "Bob left Acme")
        scoped = make_tools(
            self.engine,
            Ledger(),
            filters=SearchFilters(document_ids=[self.document_one]),
        )
        tool = _tool_named(scoped, "search_source_text")

        rendered = await tool.ainvoke({"query": "who?"})

        assert "Alice works at Acme" in rendered
        assert "Bob left Acme" not in rendered


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
        self.other_label = validate_identifier(f"Organization_{uuid4().hex[:8]}")
        self.embedder = _KeywordEmbedder()
        self.schema = GraphSchema(
            name="agent_integration",
            version="1",
            entities=[
                EntityType(label=self.label, description="A test entity."),
                EntityType(label=self.other_label, description="A company."),
            ],
            relations=[
                RelationType(
                    label="WORKS_FOR",
                    description="A person works for an organization.",
                    patterns=[(self.label, self.other_label)],
                )
            ],
        )
        self.settings = RetrievalSettings()
        self.engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
            graph_schema=self.schema,
        )
        self.chunk_ids: list = []
        self.document_id = str(uuid4())
        yield
        for label in (self.label, self.other_label):
            await self.store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
        if self.chunk_ids:
            await self.store.execute_write(
                f"MATCH (n:{CHUNK_LABEL}) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(chunk_id) for chunk_id in self.chunk_ids]},
            )
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
                        "merged_from": [],
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
        """Write one chunk in this test's document partition."""
        chunk = Chunk(
            document_id=uuid4(),
            index=0,
            text=text,
            provenance=TextProvenance(char_start=0, char_end=len(text)),
        )
        chunk.embedding = await self.embedder.embed_one(text)
        self.chunk_ids.append(chunk.id)
        await self.store.upsert_nodes(
            CHUNK_LABEL,
            [
                NodeRecord(
                    id=chunk.id,
                    labels=[CHUNK_LABEL],
                    properties={
                        "document_id": self.document_id,
                        "index": 0,
                        "text": text,
                        "provenance": '{"kind":"text","char_start":0,'
                        f'"char_end":{len(text)}}}',
                        "heading_path": [],
                        "embedding": chunk.embedding,
                        "created_at": "2024-01-01T00:00:00",
                    },
                )
            ],
        )
        await self.store.ensure_vector_index(
            label=CHUNK_LABEL,
            vector_property="embedding",
            dimensions=4,
            distance=Distance.COSINE,
        )

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
        """build_agent returns a compiled graph or _SimpleAgent."""
        settings = AgentLLMSettings.from_openai_compatible_env()
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
        agent = build_agent(engine=self.engine, llm_settings=settings)
        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Where does Alice work, and what does the source "
                            "text say about her time there?"
                        ),
                    }
                ]
            }
        )

        # The model chooses its own decomposition and synthesis style, so
        # the number of tool results is not deterministic run to run. The
        # final answer must still cite evidence from the transcript.
        transcript = "\n".join(
            self._message_text({"messages": [message]})
            for message in result.get("messages", [])
        )
        transcript_keys = set(re.findall(r"\bE\d+\b", transcript))
        assert transcript_keys, "research findings contain no citation keys"
        answer = self._message_text(result)
        assert re.search(r"\bE\d+\b", answer), "final answer cites no evidence"

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.skipif(
        not _agent_llm_configured(), reason="LLM endpoint not configured"
    )
    async def test_under_evidenced_question_reports_the_gap(self) -> None:
        """A question the graph cannot answer says so instead of guessing."""
        await self._seed_entity(self.label, "Alice")

        settings = AgentLLMSettings.from_openai_compatible_env()
        agent = build_agent(engine=self.engine, llm_settings=settings)
        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "What year did Alice found the engines team?",
                    }
                ]
            }
        )

        answer = self._message_text(result)
        assert not re.search(r"\b(?:1\d{3}|20\d{2})\b", answer)

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.skipif(
        not _agent_llm_configured(), reason="LLM endpoint not configured"
    )
    async def test_attempt_cap_allows_initial_decomposition(
        self,
    ) -> None:
        """A retry limit still permits the planner's initial decomposition."""
        alice = await self._seed_entity(self.label, "Alice")
        acme = await self._seed_entity(self.other_label, "Acme")
        await self._seed_relation("WORKS_FOR", alice, acme)

        settings = AgentLLMSettings.from_openai_compatible_env()
        agent = build_agent(
            engine=self.engine,
            llm_settings=settings,
            agent_settings=AgentSettings(max_research_attempts=1),
        )
        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "How many publications has Alice authored?",
                    }
                ]
            }
        )

        # The run terminated with a synthesized, citation-grounded answer
        # rather than a GraphRecursionError, and the verifier's structured
        # verdict -- the consultation the retry cap counts from -- appeared
        # in the transcript.
        answer = self._message_text(result)
        assert "Alice" in answer
        transcript = "\n".join(
            self._message_text({"messages": [message]})
            for message in result.get("messages", [])
        )
        assert any(
            f'"status":"{verdict}"' in transcript.replace(" ", "")
            for verdict in ("PASS", "INSUFFICIENT", "CONTRADICTORY")
        )
