"""End-to-end tests for the full ingest-retrieve-ask pipeline.

Ingests a fixture document, then verifies the evidence tools return the
seeded entity and chunk, and that the agent build/invoke path works.
"""

import importlib.util
import os
from collections.abc import AsyncGenerator, Sequence
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.evidence import EvidenceSearchMode
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.evidence import entity_search, search_evidence
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration._backend import await_indexes, build_test_store
from tests.integration._schema_cleanup import delete_resolved_entities, drop_schema_for
from tests.integration.e2e._artifact import write_artifact
from tests.integration.retrieval.evidence._corpus import make_document


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
    """Embedder returning one vector unique to the run for every text.

    The vector indexes are shared with other suites. A run-unique vector gives
    the run's own nodes cosine score 1 against every query, so they rank above
    nodes other suites left in the database.
    """

    model = "fixed"

    def __init__(self, token: str) -> None:
        """Derive the vector from the run token."""
        self._vector = [(int(char, 16) + 1) / 16 for char in token[:4]]

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return FAKE_EMBEDDING_DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the run vector for every text."""
        return [list(self._vector) for _ in texts]


class _DistinctTextEmbedder(_FixedEmbedder):
    """Run-vector embedder that tilts each text toward its own axis.

    The tilt is an offset of 1, not a multiple of the run vector. For every
    run vector, two texts on different axes have a cosine similarity of at
    most 0.86, below the resolver's hard-merge similarity of 0.95, so
    unrelated entities are never merged. Every vector still has a positive
    cosine similarity with the run vector the queries use.
    """

    model = "distinct"

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the run vector with one text-chosen axis scaled up."""
        vectors = []
        for text in texts:
            vector = list(self._vector)
            vector[len(text) % 4] += 1.0
            vectors.append(vector)
        return vectors


class _DrugExtractor(Extractor):
    """Extractor that pulls drug-condition pairs from text."""

    def __init__(
        self,
        *,
        drug_label: str,
        condition_label: str,
    ) -> None:
        """Initialize with known drug-condition pairs.

        Args:
            drug_label: The graph label drug mentions extract to.
            condition_label: The graph label condition mentions extract to.
        """
        self._pairs = {
            "aspirin": (drug_label, "Aspirin"),
            "ibuprofen": (drug_label, "Ibuprofen"),
            "headache": (condition_label, "Headache"),
            "fever": (condition_label, "Fever"),
            "inflammation": (condition_label, "Inflammation"),
        }

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Extract known drug and condition entities."""
        entities: list[ExtractedEntity] = []
        text_lower = chunk.text.lower()
        for keyword, (label, name) in self._pairs.items():
            idx = text_lower.find(keyword)
            if idx >= 0:
                entities.append(
                    ExtractedEntity(
                        chunk_id=chunk.id,
                        label=label,
                        text=name,
                        char_start=idx,
                        char_end=idx + len(keyword),
                    )
                )
        return ExtractionResult(entities=entities, relations=[], extractor_name="e2e")


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestRetrievalE2E:
    """Full end-to-end test: ingest, retrieve, verify."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store for each test."""
        self.store = build_test_store()
        await self.store.connect()
        self.token = uuid4().hex[:8]
        self.chunk_ids: list[str] = []
        self.drug_label = validate_identifier(f"Drug_{uuid4().hex[:8]}")
        self.condition_label = validate_identifier(f"Condition_{uuid4().hex[:8]}")
        self.embedder = _FixedEmbedder(self.token)
        self.support_key = f"e2e-ra://{self.token}/doc"
        self.schema = GraphSchema(
            name="e2e",
            version="1",
            entities=[
                EntityType(
                    label=self.drug_label,
                    description="A medication.",
                ),
                EntityType(
                    label=self.condition_label,
                    description="A medical condition.",
                ),
            ],
            relations=[],
        )
        try:
            yield
        finally:
            try:
                # Chunks are shared across suites, so delete only the ones this
                # test seeded, ones that mention its entities, and ones carrying
                # its unique text token.
                await self.store.execute_write(
                    f"MATCH (c:{CHUNK_LABEL})--(e) "
                    "WHERE $drug IN labels(e) OR $condition IN labels(e) "
                    "DETACH DELETE c",
                    {"drug": self.drug_label, "condition": self.condition_label},
                )
                await self.store.execute_write(
                    f"MATCH (c:{CHUNK_LABEL}) "
                    "WHERE c.id IN $ids OR c.text CONTAINS $token DETACH DELETE c",
                    {"ids": self.chunk_ids, "token": self.token},
                )
                await self.store.execute_write(
                    f"MATCH (n:{self.drug_label}) DETACH DELETE n"
                )
                await self.store.execute_write(
                    f"MATCH (n:{self.condition_label}) DETACH DELETE n"
                )
                await delete_resolved_entities(
                    self.store, self.drug_label, self.condition_label
                )
                await drop_schema_for(self.store, self.drug_label, self.condition_label)
            finally:
                await self.store.close()

    def _graph(self) -> Graph:
        """Build a graph that ingests through the fake extractor."""
        return Graph(
            schema=self.schema,
            graph_store=self.store,
            embedder=self.embedder,
            extractor=_DrugExtractor(
                drug_label=self.drug_label,
                condition_label=self.condition_label,
            ),
        )

    async def _own_entities(self) -> dict[str, str]:
        """Return ``{id: name}`` of entities under this test's labels.

        Entity search spans every label in the shared database, so tests
        filter hits down to these ids before asserting.
        """
        rows = await self.store.execute_read(
            "MATCH (n) WHERE $drug IN labels(n) OR $condition IN labels(n) "
            "RETURN n.id AS id, n.name AS name",
            {"drug": self.drug_label, "condition": self.condition_label},
        )
        return {str(r["id"]): r["name"] for r in rows}

    async def _token_chunks(self) -> list[dict[str, object]]:
        """Return id and text of chunks whose text carries this test's token."""
        return await self.store.execute_read(
            f"MATCH (c:{CHUNK_LABEL}) WHERE c.text CONTAINS $token "
            "RETURN c.id AS id, c.text AS text",
            {"token": self.token},
        )

    async def _ensure_retrieval_indexes(self) -> None:
        """Provision the vector and full-text indexes retrieval searches.

        ``Graph.open`` provisions these while opening a graph; the
        tests here construct stores directly, so each test creates the
        indexes the evidence tools search.
        """
        for label in (self.drug_label, self.condition_label, CHUNK_LABEL):
            await self.store.ensure_vector_index(
                label=label,
                vector_property="embedding",
                dimensions=4,
                distance=Distance.COSINE,
            )
        for label in (self.drug_label, self.condition_label):
            await self.store.ensure_fulltext_index(label=label, properties=["name"])
        await self.store.ensure_fulltext_index(label=CHUNK_LABEL, properties=["text"])
        # New indexes populate asynchronously; search reports
        # INDEX_NOT_READY until they are ONLINE.
        await await_indexes(self.store)

    async def _seed_graph(self) -> None:
        """Ingest one document that names Aspirin and headache.

        The fake extractor writes the Aspirin and Headache entities under this
        run's labels, and the ingested chunk mentions them.
        """
        text = "Aspirin is effective for treating headaches."
        await self._graph().add(documents=[make_document(self.support_key, text)])
        await self._ensure_retrieval_indexes()

    # ---- Evidence search tests ----

    async def test_entity_search_finds_survivor(self) -> None:
        """Entity search returns the seeded entity."""
        await self._seed_graph()

        found = await entity_search(
            self.store,
            self.embedder,
            "Aspirin",
            scope=frozenset({self.support_key}),
            labels=[self.drug_label, self.condition_label],
            mode=EvidenceSearchMode.LEXICAL,
        )

        own = await self._own_entities()
        names = sorted(hit.name for hit in found.hits if hit.entity_id in own)
        assert names == ["Aspirin"]
        artifact = write_artifact(
            "retrieval_and_agent_merge_entity_search",
            {"entity_names": names},
        )
        assert artifact["entity_names"] == ["Aspirin"]

    async def test_chunk_search_finds_related_chunk(self) -> None:
        """Chunk search finds the seeded chunk text."""
        await self._seed_graph()

        found = await search_evidence(
            self.store,
            self.embedder,
            "Aspirin headaches",
            mode=EvidenceSearchMode.LEXICAL,
            limit=10,
            scope=frozenset({self.support_key}),
        )

        assert found.hits
        assert any("aspirin" in hit.snippet.lower() for hit in found.hits)

    async def test_hybrid_returns_both_types(self) -> None:
        """Hybrid search finds the chunk, and entity search finds the entity."""
        await self._seed_graph()

        scope = frozenset({self.support_key})
        evidence = await search_evidence(
            self.store,
            self.embedder,
            "Aspirin headaches",
            limit=10,
            scope=scope,
        )
        entities = await entity_search(
            self.store,
            self.embedder,
            "Aspirin",
            scope=scope,
            labels=[self.drug_label, self.condition_label],
        )

        assert evidence.hits
        assert any("aspirin" in hit.snippet.lower() for hit in evidence.hits)
        assert any(hit.name == "Aspirin" for hit in entities.hits)

    async def test_search_respects_limit(self) -> None:
        """Search returns at most the requested number of hits."""
        await self._seed_graph()

        found = await search_evidence(
            self.store,
            self.embedder,
            "Aspirin headaches",
            mode=EvidenceSearchMode.LEXICAL,
            limit=1,
            scope=frozenset({self.support_key}),
        )

        assert len(found.hits) == 1

    # ---- Graph.add() pipeline tests ----

    async def test_full_pipeline_with_graph_add(self) -> None:
        """Full pipeline: Graph.add() -> evidence search."""
        text = f"Aspirin is commonly used to treat headaches. ref {self.token}"

        result = await self._graph().add(
            documents=[make_document(self.support_key, text)], error_policy="skip"
        )

        assert result.extraction.entities_extracted == 2
        await self._ensure_retrieval_indexes()
        scope = frozenset({self.support_key})
        chunks = await self._token_chunks()
        assert len(chunks) == 1

        entity_results = await entity_search(
            self.store,
            self.embedder,
            "Aspirin",
            scope=scope,
            labels=[self.drug_label, self.condition_label],
            mode=EvidenceSearchMode.LEXICAL,
        )
        own = await self._own_entities()
        found = {
            own[hit.entity_id] for hit in entity_results.hits if hit.entity_id in own
        }
        assert "Aspirin" in found
        entity_names = sorted(own.values())

        chunk_results = await search_evidence(
            self.store,
            self.embedder,
            "Aspirin headaches",
            mode=EvidenceSearchMode.LEXICAL,
            limit=10,
            scope=scope,
        )
        assert chunk_results.hits
        artifact = write_artifact(
            "retrieval_and_agent_graph_add_pipeline",
            {
                "entities_extracted": result.extraction.entities_extracted,
                "entity_names": entity_names,
                "chunks_written": len(chunks),
                "chunk_found_by_text": True,
            },
        )
        assert artifact["entity_names"] == ["Aspirin", "Headache"]

    async def test_graph_add_chunk_embedding_roundtrip(self) -> None:
        """Graph.add() writes chunk embeddings that vector search finds."""
        await self._graph().add(
            text=f"Ibuprofen reduces inflammation and fever. ref {self.token}",
            error_policy="skip",
        )

        rows = await self.store.execute_read(
            f"MATCH (c:{CHUNK_LABEL}) WHERE c.text CONTAINS $token "
            "RETURN c.embedding AS emb",
            {"token": self.token},
        )
        assert len(rows) == 1
        assert rows[0]["emb"] is not None
        assert len(rows[0]["emb"]) == 4

    async def test_graph_add_entity_embedding_roundtrip(self) -> None:
        """Graph.add() writes entity embeddings that vector search finds."""
        await self._graph().add(
            text=f"Ibuprofen is a common anti-inflammatory drug. ref {self.token}",
            error_policy="skip",
        )

        rows = await self.store.execute_read(
            f"MATCH (n:{self.drug_label}) "
            "WHERE n.name = 'Ibuprofen' "
            "RETURN n.embedding AS emb"
        )
        assert len(rows) == 1
        assert rows[0]["emb"] is not None
        assert len(rows[0]["emb"]) == 4

    async def test_multi_document_ingestion(self) -> None:
        """Entities from several documents are all searchable."""
        graph = Graph(
            schema=self.schema,
            graph_store=self.store,
            embedder=_DistinctTextEmbedder(self.token),
            extractor=_DrugExtractor(
                drug_label=self.drug_label,
                condition_label=self.condition_label,
            ),
        )
        await graph.add(
            documents=[
                make_document(
                    self.support_key,
                    f"Aspirin treats headaches. ref {self.token}",
                )
            ]
        )
        second_key = f"e2e-ra://{self.token}/doc2"
        await graph.add(
            documents=[
                make_document(
                    second_key,
                    f"Ibuprofen reduces inflammation. ref {self.token}",
                )
            ]
        )
        await self._ensure_retrieval_indexes()

        # The text-tilted vectors score below 1 against the run vector, so entities
        # in other labels of the shared database can outrank them. Searching only
        # this test's labels keeps those entities out of the comparison.
        results = await entity_search(
            self.store,
            self.embedder,
            "drug treatment",
            scope=frozenset({self.support_key, second_key}),
            labels=[self.drug_label, self.condition_label],
        )
        own = await self._own_entities()
        names = sorted(hit.name for hit in results.hits if hit.entity_id in own)
        chunks = await self._token_chunks()

        assert {"Aspirin", "Ibuprofen"} <= set(names)
        assert len(chunks) == 2
        artifact = write_artifact(
            "retrieval_and_agent_multi_document",
            {"entity_names": names, "chunks_written": len(chunks)},
        )
        assert {"Aspirin", "Ibuprofen"} <= set(artifact["entity_names"])  # type: ignore[arg-type]

    # ---- Agent build tests ----

    @pytest.mark.skipif(
        not _agent_llm_configured(), reason="LLM endpoint not configured"
    )
    async def test_agent_answer_contains_evidence(self) -> None:
        """The agent's answer contains evidence from the graph."""
        await self._seed_graph()

        from agrag.agents.build import build_agent  # noqa: PLC0415
        from agrag.agents.settings import (  # noqa: PLC0415
            AgentLLMSettings,
        )

        settings = AgentLLMSettings.from_openai_compatible_env()
        agent = build_agent(
            graph_store=self.store,
            embedder=self.embedder,
            scope=frozenset({self.support_key}),
            project_id="retrieval-e2e",
            agent_id="e2e-agent",
            llm_settings=settings,
        )

        result = await agent.ainvoke(
            {
                "task_name": f"headache-treatment-{uuid4().hex[:8]}",
                "question": "What treats headaches?",
            }
        )

        assert "aspirin" in result["answer"].lower()
        assert result["citations"]
