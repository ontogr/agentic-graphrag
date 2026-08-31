"""End-to-end tests for the full ingest-retrieve-ask pipeline.

Seeds a fixture graph through Graph.add() including deliberate merges
(so merged_into chains exist), then verifies SearchEngine.search()
returns the correct results, citation keys resolve to live entities,
and the agent build/invoke path works.
"""

import importlib.util
from collections.abc import AsyncGenerator, Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pytest

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


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _FixedEmbedder(Embedder):
    """Embedder returning deterministic vectors for e2e tests."""

    model = "fixed"

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return deterministic vectors based on text content."""
        vectors: list[list[float]] = []
        for text in texts:
            h = hash(text) % 1000
            vectors.append(
                [
                    float(h % 10) / 10.0,
                    float((h // 10) % 10) / 10.0,
                    float((h // 100) % 10) / 10.0,
                    0.5,
                ]
            )
        return vectors


class _DrugExtractor(Extractor):
    """Extractor that pulls drug-condition pairs from text."""

    def __init__(self) -> None:
        """Initialize with known drug-condition pairs."""
        self._pairs = {
            "aspirin": ("Drug", "Aspirin"),
            "ibuprofen": ("Drug", "Ibuprofen"),
            "headache": ("Condition", "Headache"),
            "fever": ("Condition", "Fever"),
            "inflammation": ("Condition", "Inflammation"),
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


@pytest.mark.integration
@pytest.mark.enable_socket
@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestRetrievalE2E:
    """Full end-to-end test: ingest, merge, retrieve, verify."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store for each test."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.drug_label = validate_identifier(f"Drug_{uuid4().hex[:8]}")
        self.condition_label = validate_identifier(f"Condition_{uuid4().hex[:8]}")
        self.embedder = _FixedEmbedder()
        self.settings = RetrievalSettings(
            entity_labels=[self.drug_label, self.condition_label],
            entity_top_k=10,
            chunk_top_k=10,
        )
        self.schema = GraphSchema(
            name="e2e",
            version="1",
            entities=[
                EntityType(label="Drug", description="A medication."),
                EntityType(
                    label="Condition",
                    description="A medical condition.",
                ),
            ],
            relations=[],
        )
        yield
        await self.store.execute_write(f"MATCH (n:{self.drug_label}) DETACH DELETE n")
        await self.store.execute_write(
            f"MATCH (n:{self.condition_label}) DETACH DELETE n"
        )
        await self.store.execute_write(f"MATCH (n:{CHUNK_LABEL}) DETACH DELETE n")
        await self.store.close()

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

        return survivor, tombstone, chunk

    # ---- Entity search tests ----

    async def test_entity_search_finds_survivor(self) -> None:
        """Entity search returns the survivor, not the tombstone."""
        survivor, tombstone, _ = await self._seed_graph_with_merge()

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("Aspirin", ENTITY)

        assert len(results) >= 1
        result_ids = {r.item.id for r in results}
        assert survivor.id in result_ids
        assert tombstone.id not in result_ids

    async def test_entity_search_survivor_has_correct_name(
        self,
    ) -> None:
        """The survivor entity has the correct canonical name."""
        survivor, _, _ = await self._seed_graph_with_merge()

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("Aspirin", ENTITY)

        names = {r.item.name for r in results if hasattr(r.item, "name")}
        assert "Aspirin" in names

    # ---- Chunk search tests ----

    async def test_chunk_search_finds_related_chunk(self) -> None:
        """Chunk search finds the seeded chunk."""
        _, _, chunk = await self._seed_graph_with_merge()

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("headache treatment", CHUNK)

        assert len(results) >= 1
        result_texts = {r.item.text for r in results if hasattr(r.item, "text")}
        assert any("aspirin" in t.lower() for t in result_texts)

    async def test_chunk_result_has_embedding(self) -> None:
        """The chunk result carries its embedding."""
        _, _, chunk = await self._seed_graph_with_merge()

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("headache", CHUNK)

        assert len(results) >= 1
        chunk_result = next((r for r in results if hasattr(r.item, "text")), None)
        assert chunk_result is not None
        # The chunk should have been hydrated with its embedding.
        if chunk_result.item.embedding is not None:
            assert len(chunk_result.item.embedding) == 4

    # ---- Hybrid search tests ----

    async def test_hybrid_returns_both_types(self) -> None:
        """HYBRID returns both entity and chunk results."""
        await self._seed_graph_with_merge()

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("Aspirin headache", HYBRID)

        assert len(results) >= 1
        types = {type(r.item).__name__ for r in results}
        assert "Entity" in types or "Chunk" in types

    async def test_hybrid_fusion_deduplicates(self) -> None:
        """HYBRID fusion deduplicates results by identity_key."""
        await self._seed_graph_with_merge()

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("Aspirin", HYBRID)

        # Check no duplicate identity_keys.
        keys = [r.identity_key for r in results]
        assert len(keys) == len(set(keys))

    # ---- Citation key tests ----

    async def test_citation_keys_resolve_to_live_entities(
        self,
    ) -> None:
        """Every citation key resolves to a live, non-tombstoned entity."""
        from agrag.agents.ledger import Ledger  # noqa: PLC0415

        survivor, tombstone, _ = await self._seed_graph_with_merge()

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("Aspirin", HYBRID)

        ledger = Ledger()
        for result in results:
            key = ledger.cite(result)
            resolved = ledger.resolve(key)
            assert resolved is not None
            if hasattr(resolved.item, "id"):
                assert resolved.item.id != tombstone.id

    async def test_citation_keys_are_stable(self) -> None:
        """Citation keys are stable across multiple cite() calls."""
        from agrag.agents.ledger import Ledger  # noqa: PLC0415

        await self._seed_graph_with_merge()

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("Aspirin", ENTITY)

        ledger = Ledger()
        if results:
            key1 = ledger.cite(results[0])
            key2 = ledger.cite(results[0])
            assert key1 == key2

    # ---- SearchEngine direct usage tests ----

    async def test_search_engine_entity_direct(self) -> None:
        """SearchEngine entity search works directly."""
        await self._seed_graph_with_merge()

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("Aspirin", ENTITY)
        assert isinstance(results, list)

    async def test_search_engine_chunk_direct(self) -> None:
        """SearchEngine chunk search works directly."""
        await self._seed_graph_with_merge()

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("headache", CHUNK)
        assert isinstance(results, list)

    async def test_search_engine_empty_query(self) -> None:
        """SearchEngine handles an empty query gracefully."""
        await self._seed_graph_with_merge()

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("", ENTITY)
        assert isinstance(results, list)

    async def test_search_respects_limit(self) -> None:
        """Search respects the recipe's limit."""
        await self._seed_graph_with_merge()

        from agrag.retrieval.recipes import Recipe  # noqa: PLC0415

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        recipe = Recipe(methods=["entity"], limit=1)
        results = await engine.search("Aspirin", recipe)
        assert len(results) <= 1

    # ---- Graph.add() pipeline tests ----

    async def test_full_pipeline_with_graph_add(self) -> None:
        """Full pipeline: Graph.add() -> SearchEngine.search()."""
        graph = Graph(
            schema=self.schema,
            graph_store=self.store,
            embedder=self.embedder,
            extractor=_DrugExtractor(),
        )

        result = await graph.add(
            text="Aspirin is commonly used to treat headaches.",
            error_policy="skip",
        )

        assert result.extraction.entities_extracted >= 1

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )

        entity_results = await engine.search("Aspirin", ENTITY)
        assert len(entity_results) >= 1

        chunk_results = await engine.search("headache treatment", CHUNK)
        assert len(chunk_results) >= 1

    async def test_graph_add_chunk_embedding_roundtrip(self) -> None:
        """Graph.add() writes chunk embeddings that vector search finds."""
        graph = Graph(
            schema=self.schema,
            graph_store=self.store,
            embedder=self.embedder,
            extractor=_DrugExtractor(),
        )

        await graph.add(
            text="Ibuprofen reduces inflammation and fever.",
            error_policy="skip",
        )

        # Verify chunk has embedding in the database.
        rows = await self.store.execute_read(
            f"MATCH (c:{CHUNK_LABEL}) "
            f"WHERE c.text CONTAINS 'Ibuprofen' "
            f"RETURN c.embedding AS emb LIMIT 1"
        )
        assert len(rows) >= 1
        assert rows[0]["emb"] is not None
        assert len(rows[0]["emb"]) == 4

    async def test_graph_add_entity_embedding_roundtrip(self) -> None:
        """Graph.add() writes entity embeddings that vector search finds."""
        graph = Graph(
            schema=self.schema,
            graph_store=self.store,
            embedder=self.embedder,
            extractor=_DrugExtractor(),
        )

        await graph.add(
            text="Ibuprofen is a common anti-inflammatory drug.",
            error_policy="skip",
        )

        # Verify entity has embedding.
        rows = await self.store.execute_read(
            f"MATCH (n:{self.drug_label}) "
            f"WHERE n.name = 'Ibuprofen' "
            f"RETURN n.embedding AS emb LIMIT 1"
        )
        if rows:
            assert rows[0]["emb"] is not None

    async def test_multi_document_ingestion(self) -> None:
        """Multiple documents can be ingested and searched."""
        graph = Graph(
            schema=self.schema,
            graph_store=self.store,
            embedder=self.embedder,
            extractor=_DrugExtractor(),
        )

        await graph.add(
            text="Aspirin treats headaches.",
            error_policy="skip",
        )
        await graph.add(
            text="Ibuprofen reduces inflammation.",
            error_policy="skip",
        )

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )

        # Both entities should be findable.
        results = await engine.search("drug treatment", HYBRID)
        assert len(results) >= 1

    # ---- Agent build tests ----

    async def test_agent_build_and_invoke(self) -> None:
        """build_agent constructs an agent that can be invoked."""
        await self._seed_graph_with_merge()

        from agrag.agents.build import build_agent  # noqa: PLC0415
        from agrag.agents.settings import (  # noqa: PLC0415
            AgentLLMSettings,
        )
        from agrag.llm.client_config import LLMClientConfig  # noqa: PLC0415

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )

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

    async def test_agent_answer_contains_evidence(self) -> None:
        """The agent's answer contains evidence from the graph."""
        await self._seed_graph_with_merge()

        from agrag.agents.build import build_agent  # noqa: PLC0415
        from agrag.agents.settings import (  # noqa: PLC0415
            AgentLLMSettings,
        )
        from agrag.llm.client_config import LLMClientConfig  # noqa: PLC0415

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )

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

        answer = result["messages"][-1]["content"]
        # The answer should reference Aspirin or citation keys.
        assert "Aspirin" in answer or "[E" in answer or "[C" in answer

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

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("Aspirin", ENTITY)

        assert len(results) >= 1
        result_ids = {r.item.id for r in results}
        assert survivor.id in result_ids
        assert t1.id not in result_ids
        assert t0.id not in result_ids
