"""End-to-end agent tracing against a real Neo4j and a real LLM.

One tracer is given to the graph store, the engine and ``build_agent``. The
agent answers two independent lookups, and each retrieval span must nest under
the ``TOOL`` span of the evidence call that made it. The span tree is written
to the test output directory as JSON. The test seeds its own four-dimension
corpus, like the other agent integration tests, so it shares the database-wide
``Chunk`` vector index with them. It skips when no agent LLM endpoint is configured.
"""

import json
import os
from collections.abc import AsyncGenerator, Sequence
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings
from agrag.chunking import Chunker
from agrag.common.data_models.document import Document
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.eval.trajectory import read_trajectory
from agrag.graphdb import build_graph_store
from agrag.ingestion.graph import Graph
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration.retrieval.evidence._corpus import (
    NoEntityExtractor,
    make_document,
)


_OUTPUT_DIR = Path(os.environ.get("AGRAG_TRACING_OUTPUT_DIR", "test-output"))

_PROMPT = (
    "I need two independent facts. Fact 1: who founded Zephyra Robotics? "
    "Fact 2: how much weight can the Lumen-9 robot lift? Find evidence for "
    "each fact, then answer both."
)

_FOUNDER_CHUNK = "Zephyra Robotics was founded by Mira Okafor in a garage workshop."
_LIFT_CHUNK = "The Lumen-9 robot can lift 40 kilograms with its dual arms."


class _FakeKeywordEmbedder(Embedder):
    """Embedder that separates texts by keyword in four dimensions.

    One dimension per keyword, so the founder and lifting facts land far
    apart. A text with no keyword gets a neutral uniform vector, since Neo4j
    rejects an all-zero vector.
    """

    model = "keyword"
    _KEYWORDS = ("zephyra", "mira", "lumen", "lift")

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return FAKE_EMBEDDING_DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one keyword-presence vector per text."""
        vectors = []
        for text in texts:
            lowered = text.lower()
            vector = [1.0 if word in lowered else 0.0 for word in self._KEYWORDS]
            vectors.append(vector if any(vector) else [0.5] * 4)
        return vectors


def _span_tree(spans: tuple[ReadableSpan, ...]) -> dict:
    """Serialize exported spans as one parent-pointer tree."""
    by_id = {span.context.span_id: span for span in spans}
    nodes = []
    for span in spans:
        parent = span.parent
        nodes.append(
            {
                "name": span.name,
                "trace_id": f"{span.context.trace_id:032x}",
                "span_id": f"{span.context.span_id:016x}",
                "parent_span_id": (
                    f"{parent.span_id:016x}" if parent is not None else None
                ),
                "parent_name": (
                    by_id[parent.span_id].name
                    if parent is not None and parent.span_id in by_id
                    else None
                ),
                "attributes": dict(span.attributes or {}),
            }
        )
    return {"spans": nodes}


def _ancestors(
    span: ReadableSpan, by_id: dict[int, ReadableSpan]
) -> list[ReadableSpan]:
    """Return the exported ancestors of a span, nearest first."""
    chain: list[ReadableSpan] = []
    parent = span.parent
    while parent is not None and parent.span_id in by_id:
        holder = by_id[parent.span_id]
        chain.append(holder)
        parent = holder.parent
    return chain


def _is_tool(span: ReadableSpan) -> bool:
    """Return True for an OpenInference TOOL span."""
    return (span.attributes or {}).get("openinference.span.kind") == "TOOL"


def _tool_name(span: ReadableSpan) -> str | None:
    """Return the tool name of a TOOL span, or None for any other span."""
    return str((span.attributes or {}).get("tool.name")) if _is_tool(span) else None


class TestAgentTracing:
    """Retrieval spans nest under the tool call that made them."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Connect a traced store and delete this test's rows afterwards."""
        self.exporter = InMemorySpanExporter()
        self.provider = TracerProvider()
        self.provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.tracer = self.provider.get_tracer("test")
        self.store = build_graph_store("neo4j", tracer=self.tracer)
        await self.store.connect()
        suffix = uuid4().hex[:8]
        self.person_label = validate_identifier(f"Person_{suffix}")
        self.company_label = validate_identifier(f"Company_{suffix}")
        self.robot_label = validate_identifier(f"Robot_{suffix}")
        self.embedder = _FakeKeywordEmbedder()
        self.chunk_ids: list = []
        self.document_key = f"agent-tracing-{suffix}"
        self.document_id = str(Document.node_id_for(document_key=self.document_key))
        yield
        for label in (self.person_label, self.company_label, self.robot_label):
            await self.store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
        await self.store.execute_write(
            "MATCH (d:Document {document_key: $key}) "
            "OPTIONAL MATCH (d)-[:HAS_PART]->(c:Chunk) DETACH DELETE c, d",
            {"key": self.document_key},
        )
        await self.store.execute_write(
            "MATCH (j:CutoverJob {document_key: $key}) DETACH DELETE j",
            {"key": self.document_key},
        )
        await self.store.close()

    async def _seed_entity(self, label: str, name: str) -> UUID:
        """Write one searchable entity."""
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

    async def _seed_document(self, text: str) -> None:
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
        await graph.add(documents=[make_document(self.document_key, text)])
        await self.store.execute_read("CALL db.awaitIndexes(60)")

    async def test_retrieval_spans_nest_under_their_tool_span(self) -> None:
        """Each retrieval span sits under a TOOL span of the agent run."""
        settings = AgentLLMSettings.from_openai_compatible_env()
        if not settings.clients[0].api_key:
            pytest.skip("Agent LLM API key not configured")

        founder = await self._seed_entity(self.person_label, "Mira Okafor")
        company = await self._seed_entity(self.company_label, "Zephyra Robotics")
        await self._seed_entity(self.robot_label, "Lumen-9")
        await self._seed_relation("FOUNDED", founder, company)
        await self._seed_document(f"{_FOUNDER_CHUNK}\n\n{_LIFT_CHUNK}")

        agent = build_agent(
            graph_store=self.store,
            embedder=self.embedder,
            scope=frozenset({self.document_key}),
            project_id="agent-tracing",
            agent_id="tracing-agent",
            llm_settings=settings,
            tracer=self.tracer,
        )
        await agent.ainvoke(
            {"task_name": f"tracing-run-{uuid4().hex[:8]}", "question": _PROMPT}
        )
        self.provider.force_flush()

        spans = self.exporter.get_finished_spans()
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (_OUTPUT_DIR / "agent_tracing_span_tree.json").write_text(
            json.dumps(_span_tree(spans), indent=2)
        )
        by_id = {span.context.span_id: span for span in spans}

        tools = [span for span in spans if _is_tool(span)]
        assert tools, "the agent made no tool calls"
        # Evidence discovery and fetch read the graph through the store, so
        # each read sits under the evidence TOOL call that issued it.
        owners: dict[int, str | None] = {}
        for span in spans:
            if span.name != "agrag.graphdb.execute_read":
                continue
            tool = next((a for a in _ancestors(span, by_id) if _is_tool(a)), None)
            if tool is not None:
                owners[tool.context.span_id] = _tool_name(tool)
        assert owners, "no graph read ran under a tool span"
        assert set(owners.values()) <= {
            "discover_evidence",
            "fetch_evidence",
            "navigate",
            "find_entities",
            "explore",
        }
        assert len(owners) >= 2, "fewer than two tool calls ran retrieval"

        searches = [
            step for step in read_trajectory(spans).steps if step.kind == "tool"
        ]
        assert searches
