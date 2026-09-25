"""End-to-end tests for the full ingest-retrieve-ask pipeline.

Seeds a fixture graph through Graph.add() including deliberate merges
(so merged_into chains exist), then verifies SearchEngine.search()
returns the correct results, citation keys resolve to live entities,
and the agent build/invoke path works.
"""

import importlib.util
import os
from collections.abc import AsyncGenerator, Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractionResult,
)
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.merge import mentioned_in_id
from agrag.retrieval.recipes import CHUNK, ENTITY, HYBRID
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.e2e._artifact import write_artifact


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
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the run vector for every text."""
        return [list(self._vector) for _ in texts]


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
    """Full end-to-end test: ingest, merge, retrieve, verify."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store for each test."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.token = uuid4().hex[:8]
        self.chunk_ids: list[str] = []
        self.drug_label = validate_identifier(f"Drug_{uuid4().hex[:8]}")
        self.condition_label = validate_identifier(f"Condition_{uuid4().hex[:8]}")
        self.embedder = _FixedEmbedder(self.token)
        self.settings = RetrievalSettings(
            entity_top_k=100,
            chunk_top_k=100,
        )
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
                await drop_schema_for(self.store, self.drug_label, self.condition_label)
            finally:
                await self.store.close()

    def _engine(self) -> SearchEngine:
        """Build a search engine over the test store."""
        return SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
            graph_schema=self.schema,
        )

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
        """Provision the vector indexes retrieval searches.

        ``Graph.open`` provisions these while opening a graph; the
        tests here construct stores directly, so each test creates the
        indexes ``SearchEngine.search`` searches itself.
        """
        for label in (self.drug_label, self.condition_label, CHUNK_LABEL):
            await self.store.ensure_vector_index(
                label=label,
                vector_property="embedding",
                dimensions=4,
                distance=Distance.COSINE,
            )

    async def _seed_graph_with_merge(
        self,
    ) -> tuple[Entity, Entity, Chunk]:
        """Seed a graph with a merge scenario.

        Creates:
        - Entity "Aspirin" (survivor)
        - Entity "ASA" (tombstoned into Aspirin)
        - Chunk mentioning Aspirin
        - MENTIONED_IN edge from Chunk to Aspirin
        """
        survivor = Entity(id=uuid4(), label="Drug", name="Aspirin")
        tombstone = Entity(id=uuid4(), label="Drug", name="ASA")

        await self.store.upsert_nodes(
            self.drug_label,
            [
                NodeRecord(
                    id=survivor.id,
                    labels=[self.drug_label],
                    properties={
                        "name": survivor.name,
                        "merge_key": survivor.merge_key,
                        "merged_from": [str(tombstone.id)],
                        "merge_count": 2,
                        "source_chunk_ids": [],
                        "created_at": survivor.created_at.isoformat(),
                    },
                ),
                NodeRecord(
                    id=tombstone.id,
                    labels=[self.drug_label],
                    properties={
                        "name": tombstone.name,
                        "merge_key": tombstone.merge_key,
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                        "merged_into": str(survivor.id),
                        "created_at": tombstone.created_at.isoformat(),
                    },
                ),
            ],
        )

        chunk = Chunk(
            document_id=uuid4(),
            index=0,
            text="Aspirin is effective for treating headaches.",
            provenance=TextProvenance(char_start=0, char_end=44),
        )
        chunk.embedding = await self.embedder.embed_one(chunk.text)
        self.chunk_ids.append(str(chunk.id))
        await self.store.upsert_nodes(
            CHUNK_LABEL,
            [
                NodeRecord(
                    id=chunk.id,
                    labels=[CHUNK_LABEL],
                    properties={
                        "document_id": str(chunk.document_id),
                        "index": chunk.index,
                        "text": chunk.text,
                        "provenance": ('{"kind":"text","char_start":0,"char_end":44}'),
                        "heading_path": [],
                        "content_kind": "text",
                        "embedding": chunk.embedding,
                        "created_at": chunk.created_at.isoformat(),
                    },
                )
            ],
        )

        await self.store.upsert_relations(
            [
                RelationRecord(
                    id=mentioned_in_id(chunk.id, survivor.id),
                    type="MENTIONED_IN",
                    start_id=chunk.id,
                    end_id=survivor.id,
                    properties={
                        "created_at": datetime.now(UTC).isoformat(),
                    },
                ),
            ]
        )

        await self._ensure_retrieval_indexes()

        survivor.embedding = await self.embedder.embed_one(survivor.name)
        await self.store.execute_write(
            "UNWIND $records AS record "
            f"MATCH (n:{self.drug_label} {{id: record.id}}) "
            "SET n.embedding = record.vector",
            {
                "records": [
                    {
                        "id": str(survivor.id),
                        "vector": survivor.embedding,
                    }
                ]
            },
        )

        return survivor, tombstone, chunk

    # ---- Entity search tests ----

    async def test_entity_search_finds_survivor(self) -> None:
        """Entity search returns the survivor, not the tombstone."""
        survivor, tombstone, _ = await self._seed_graph_with_merge()

        results = await self._engine().search("Aspirin", ENTITY)

        result_ids = {r.item.id for r in results}
        assert survivor.id in result_ids
        assert tombstone.id not in result_ids
        own = await self._own_entities()
        names = sorted(own[str(r.item.id)] for r in results if str(r.item.id) in own)
        assert names == ["Aspirin"]
        artifact = write_artifact(
            "retrieval_and_agent_merge_entity_search",
            {"entity_names": names, "tombstone_returned": False},
        )
        assert artifact["entity_names"] == ["Aspirin"]

    # ---- Chunk search tests ----

    async def test_chunk_search_finds_related_chunk(self) -> None:
        """Chunk search finds the seeded chunk."""
        _, _, chunk = await self._seed_graph_with_merge()

        results = await self._engine().search(chunk.text, CHUNK)

        matching = [r for r in results if r.item.id == chunk.id]
        assert len(matching) == 1
        assert "aspirin" in matching[0].item.text.lower()

    async def test_chunk_result_has_embedding(self) -> None:
        """The chunk result carries its embedding."""
        _, _, chunk = await self._seed_graph_with_merge()

        results = await self._engine().search(chunk.text, CHUNK)

        matching = [r for r in results if r.item.id == chunk.id]
        assert len(matching) == 1
        assert matching[0].item.embedding is not None
        assert len(matching[0].item.embedding) == 4

    # ---- Hybrid search tests ----

    async def test_hybrid_returns_both_types(self) -> None:
        """HYBRID returns the survivor entity and the seeded chunk."""
        survivor, _, chunk = await self._seed_graph_with_merge()

        results = await self._engine().search(chunk.text, HYBRID)

        ids = {r.item.id for r in results}
        assert survivor.id in ids
        assert chunk.id in ids

    async def test_hybrid_fusion_deduplicates(self) -> None:
        """HYBRID fusion deduplicates results by identity_key."""
        survivor, _, chunk = await self._seed_graph_with_merge()

        results = await self._engine().search(chunk.text, HYBRID)

        keys = [r.identity_key for r in results]
        assert len(keys) == len(set(keys))
        assert {survivor.id, chunk.id} <= {r.item.id for r in results}

    # ---- Citation key tests ----

    async def test_citation_keys_resolve_to_live_entities(
        self,
    ) -> None:
        """Every citation key resolves to a live, non-tombstoned entity."""
        from agrag.agents.ledger import Ledger  # noqa: PLC0415

        survivor, tombstone, chunk = await self._seed_graph_with_merge()

        results = await self._engine().search(chunk.text, HYBRID)

        ledger = Ledger()
        keys = [ledger.cite(result) for result in results]
        for key in keys:
            resolved = ledger.resolve(key)
            assert resolved is not None
            assert resolved.item.id != tombstone.id
        resolved_ids = {ledger.resolve(k).item.id for k in keys}  # type: ignore[union-attr]
        assert {survivor.id, chunk.id} <= resolved_ids
        assert len(set(keys)) == len(keys)
        artifact = write_artifact(
            "retrieval_and_agent_hybrid_citations",
            {
                "survivor_cited": True,
                "chunk_cited": True,
                "tombstone_cited": False,
                "unique_keys": len(set(keys)) == len(keys),
                "own_entities_cited": len(resolved_ids & {survivor.id, tombstone.id}),
            },
        )
        assert artifact["own_entities_cited"] == 1

    async def test_citation_keys_are_stable(self) -> None:
        """Citation keys are stable across multiple cite() calls."""
        from agrag.agents.ledger import Ledger  # noqa: PLC0415

        survivor, _, _ = await self._seed_graph_with_merge()

        results = await self._engine().search("Aspirin", ENTITY)
        assert results

        ledger = Ledger()
        key1 = ledger.cite(results[0])
        key2 = ledger.cite(results[0])
        assert key1 == key2
        resolved = ledger.resolve(key1)
        assert resolved is not None
        assert resolved.item.id == survivor.id

    # ---- SearchEngine direct usage tests ----

    async def test_search_engine_entity_direct(self) -> None:
        """SearchEngine entity search returns the survivor entity."""
        survivor, _, _ = await self._seed_graph_with_merge()

        results = await self._engine().search("Aspirin", ENTITY)

        own = await self._own_entities()
        assert [r.item.id for r in results if str(r.item.id) in own] == [survivor.id]

    async def test_search_engine_chunk_direct(self) -> None:
        """SearchEngine chunk search returns the seeded chunk."""
        _, _, chunk = await self._seed_graph_with_merge()

        results = await self._engine().search(chunk.text, CHUNK)

        assert chunk.id in {r.item.id for r in results}

    async def test_search_engine_empty_query(self) -> None:
        """An empty query never returns a tombstoned entity."""
        _, tombstone, _ = await self._seed_graph_with_merge()

        results = await self._engine().search("", ENTITY)

        assert tombstone.id not in {r.item.id for r in results}

    async def test_search_respects_limit(self) -> None:
        """Search respects the recipe's limit."""
        survivor, _, _ = await self._seed_graph_with_merge()

        from agrag.retrieval.recipes import Recipe  # noqa: PLC0415

        recipe = Recipe(methods=["entity"], limit=1)
        results = await self._engine().search("Aspirin", recipe)
        assert len(results) == 1

    # ---- Graph.add() pipeline tests ----

    async def test_full_pipeline_with_graph_add(self) -> None:
        """Full pipeline: Graph.add() -> SearchEngine.search()."""
        text = f"Aspirin is commonly used to treat headaches. ref {self.token}"

        result = await self._graph().add(text=text, error_policy="skip")

        assert result.extraction.entities_extracted == 2
        await self._ensure_retrieval_indexes()
        engine = self._engine()
        chunks = await self._token_chunks()
        assert len(chunks) == 1
        chunk_text = str(chunks[0]["text"])

        entity_results = await engine.search("Aspirin", ENTITY)
        own = await self._own_entities()
        found = {own[str(r.item.id)] for r in entity_results if str(r.item.id) in own}
        assert "Aspirin" in found
        entity_names = sorted(own.values())

        chunk_results = await engine.search(chunk_text, CHUNK)
        assert str(chunks[0]["id"]) in {str(r.item.id) for r in chunk_results}
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
        graph = self._graph()
        await graph.add(
            text=f"Aspirin treats headaches. ref {self.token}", error_policy="skip"
        )
        await graph.add(
            text=f"Ibuprofen reduces inflammation. ref {self.token}",
            error_policy="skip",
        )
        await self._ensure_retrieval_indexes()

        results = await self._engine().search("drug treatment", ENTITY)
        own = await self._own_entities()
        names = sorted(own[str(r.item.id)] for r in results if str(r.item.id) in own)
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
    async def test_agent_build_and_invoke(self) -> None:
        """build_agent constructs an agent that can be invoked."""
        await self._seed_graph_with_merge()

        from agrag.agents.build import build_agent  # noqa: PLC0415
        from agrag.agents.settings import (  # noqa: PLC0415
            AgentLLMSettings,
        )

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
            graph_schema=self.schema,
        )

        settings = AgentLLMSettings.from_openai_compatible_env()
        agent = build_agent(engine=engine, llm_settings=settings)
        assert agent is not None
        assert hasattr(agent, "ainvoke")

        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "What treats headaches?",
                    }
                ]
            }
        )
        assert "messages" in result
        assert len(result["messages"]) >= 1

    @pytest.mark.skipif(
        not _agent_llm_configured(), reason="LLM endpoint not configured"
    )
    async def test_agent_answer_contains_evidence(self) -> None:
        """The agent's answer contains evidence from the graph."""
        await self._seed_graph_with_merge()

        from agrag.agents.build import build_agent  # noqa: PLC0415
        from agrag.agents.settings import (  # noqa: PLC0415
            AgentLLMSettings,
        )

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
            graph_schema=self.schema,
        )

        settings = AgentLLMSettings.from_openai_compatible_env()
        agent = build_agent(engine=engine, llm_settings=settings)

        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "What treats headaches?",
                    }
                ]
            }
        )

        last_message = result["messages"][-1]
        answer = (
            last_message["content"]
            if isinstance(last_message, dict)
            else last_message.content
        )
        # The answer should reference Aspirin or citation keys.
        assert "aspirin" in answer.lower() or "[E" in answer or "[C" in answer

    # ---- Tombstone chain tests ----

    async def test_multi_hop_merge_chain(self) -> None:
        """A multi-hop merge chain resolves to the final survivor."""
        survivor = Entity(id=uuid4(), label="Drug", name="Aspirin")
        t1 = Entity(id=uuid4(), label="Drug", name="ASA")
        t0 = Entity(id=uuid4(), label="Drug", name="Acetylsalicylic acid")

        await self.store.upsert_nodes(
            self.drug_label,
            [
                NodeRecord(
                    id=survivor.id,
                    labels=[self.drug_label],
                    properties={
                        "name": survivor.name,
                        "merge_key": survivor.merge_key,
                        "merged_from": [str(t1.id)],
                        "merge_count": 2,
                        "source_chunk_ids": [],
                        "created_at": survivor.created_at.isoformat(),
                    },
                ),
                NodeRecord(
                    id=t1.id,
                    labels=[self.drug_label],
                    properties={
                        "name": t1.name,
                        "merge_key": t1.merge_key,
                        "merged_from": [str(t0.id)],
                        "merge_count": 2,
                        "source_chunk_ids": [],
                        "merged_into": str(survivor.id),
                        "created_at": t1.created_at.isoformat(),
                    },
                ),
                NodeRecord(
                    id=t0.id,
                    labels=[self.drug_label],
                    properties={
                        "name": t0.name,
                        "merge_key": t0.merge_key,
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                        "merged_into": str(t1.id),
                        "created_at": t0.created_at.isoformat(),
                    },
                ),
            ],
        )

        await self.store.ensure_vector_index(
            label=self.drug_label,
            vector_property="embedding",
            dimensions=4,
            distance=Distance.COSINE,
        )

        survivor.embedding = await self.embedder.embed_one(survivor.name)
        await self.store.execute_write(
            "UNWIND $records AS record "
            f"MATCH (n:{self.drug_label} {{id: record.id}}) "
            "SET n.embedding = record.vector",
            {
                "records": [
                    {
                        "id": str(survivor.id),
                        "vector": survivor.embedding,
                    }
                ]
            },
        )

        results = await self._engine().search("Aspirin", ENTITY)

        own = await self._own_entities()
        result_ids = {r.item.id for r in results if str(r.item.id) in own}
        assert result_ids == {survivor.id}
        assert t1.id not in result_ids
        assert t0.id not in result_ids
        artifact = write_artifact(
            "retrieval_and_agent_multi_hop_merge",
            {
                "entity_names": sorted(own[str(i)] for i in result_ids),
                "chain_length": 3,
            },
        )
        assert artifact["entity_names"] == ["Aspirin"]
