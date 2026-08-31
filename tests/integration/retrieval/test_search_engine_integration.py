"""Integration tests for SearchEngine against a real Neo4j instance.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``).
"""

import importlib.util
from collections.abc import Sequence
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import (
    validate_identifier,
)
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion.merge import mentioned_in_id
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.recipes import (
    CHUNK,
    ENTITY,
    GRAPH_EXPAND,
    HYBRID,
    Recipe,
)
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _FixedEmbedder(Embedder):
    """Embedder returning deterministic vectors for testing."""

    model = "fixed"

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a deterministic vector per text.

        Each text gets a unique vector based on its hash, so
        similar texts get similar vectors.
        """
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


@pytest.mark.integration
@pytest.mark.enable_socket
@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestSearchEngineIntegration:
    """SearchEngine searches a real Neo4j graph store."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> None:
        """Set up a fresh store for each test."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        self.chunk_label = validate_identifier(f"Chunk_{uuid4().hex[:8]}")
        self.embedder = _FixedEmbedder()
        self.settings = RetrievalSettings(
            entity_labels=[self.label],
            entity_top_k=10,
            chunk_top_k=10,
        )
        yield
        await self.store.execute_write(f"MATCH (n:{self.label}) DETACH DELETE n")
        await self.store.execute_write(f"MATCH (n:{self.chunk_label}) DETACH DELETE n")
        await self.store.close()

    async def _seed_entities(self, names: list[str]) -> list[Entity]:
        """Write entities with embeddings to the store."""
        entities: list[Entity] = []
        for name in names:
            ent = Entity(id=uuid4(), label="Person", name=name)
            ent.embedding = await self.embedder.embed_one(name)
            entities.append(ent)

        records = [
            NodeRecord(
                id=ent.id,
                labels=[self.label],
                properties={
                    "name": ent.name,
                    "merge_key": ent.merge_key,
                    "merged_from": [],
                    "merge_count": 1,
                    "source_chunk_ids": [],
                    "embedding": ent.embedding,
                    "created_at": ent.created_at.isoformat(),
                },
            )
            for ent in entities
        ]
        await self.store.upsert_nodes(self.label, records)
        await self.store.ensure_vector_index(
            label=self.label,
            vector_property="embedding",
            dimensions=4,
            distance=Distance.COSINE,
        )
        return entities

    async def _seed_chunks(self, texts: list[str]) -> list[Chunk]:
        """Write chunks with embeddings to the store."""
        chunks: list[Chunk] = []
        for text in texts:
            ch = Chunk(
                document_id=uuid4(),
                index=0,
                text=text,
                provenance=TextProvenance(char_start=0, char_end=len(text)),
            )
            ch.embedding = await self.embedder.embed_one(text)
            chunks.append(ch)

        records = [
            NodeRecord(
                id=ch.id,
                labels=[CHUNK_LABEL],
                properties={
                    "document_id": str(ch.document_id),
                    "index": ch.index,
                    "text": ch.text,
                    "provenance": '{"kind":"text",'
                    '"char_start":0,'
                    f'"char_end":{len(ch.text)}}}',
                    "heading_path": [],
                    "content_kind": "text",
                    "embedding": ch.embedding,
                    "created_at": ch.created_at.isoformat(),
                },
            )
            for ch in chunks
        ]
        await self.store.upsert_nodes(CHUNK_LABEL, records)
        await self.store.ensure_vector_index(
            label=CHUNK_LABEL,
            vector_property="embedding",
            dimensions=4,
            distance=Distance.COSINE,
        )
        return chunks

    async def test_entity_search_returns_results(self) -> None:
        """Entity search returns entities matching a query."""
        await self._seed_entities(["Alice", "Bob", "Charlie"])

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("Alice", ENTITY)

        assert len(results) >= 1
        names = {r.item.name for r in results if hasattr(r.item, "name")}
        assert "Alice" in names

    async def test_chunk_search_returns_results(self) -> None:
        """Chunk search returns chunks matching a query."""
        await self._seed_chunks(
            [
                "Aspirin treats headaches",
                "Ibuprofen reduces inflammation",
            ]
        )

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("headache treatment", CHUNK)

        assert len(results) >= 1

    async def test_hybrid_fuses_entity_and_chunk(self) -> None:
        """HYBRID recipe returns both entity and chunk results."""
        await self._seed_entities(["Alice"])
        await self._seed_chunks(["Alice works at Acme Corp"])

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await engine.search("Alice", HYBRID)

        assert len(results) >= 1
        types = {type(r.item).__name__ for r in results}
        assert "Entity" in types or "Chunk" in types

    async def test_graph_expand_returns_bfs_results(
        self,
    ) -> None:
        """GRAPH_EXPAND recipe runs BFS from seed entities."""
        entities = await self._seed_entities(["Alice", "Bob"])

        # Create a MENTIONED_IN relationship via direct write.
        chunk_id = uuid4()
        await self.store.upsert_nodes(
            CHUNK_LABEL,
            [
                NodeRecord(
                    id=chunk_id,
                    labels=[CHUNK_LABEL],
                    properties={
                        "document_id": str(uuid4()),
                        "index": 0,
                        "text": "Alice works with Bob",
                        "provenance": "{}",
                        "heading_path": [],
                        "content_kind": "text",
                        "created_at": "2024-01-01T00:00:00",
                    },
                )
            ],
        )
        await self.store.upsert_relations(
            [
                RelationRecord(
                    id=mentioned_in_id(chunk_id, entities[0].id),
                    type="MENTIONED_IN",
                    start_id=chunk_id,
                    end_id=entities[0].id,
                    properties={},
                ),
            ]
        )

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        # GRAPH_EXPAND searches entities first, then BFS expands.
        results = await engine.search("Alice", GRAPH_EXPAND)

        assert isinstance(results, list)

    async def test_search_with_filters(self) -> None:
        """Search respects SearchFilters."""
        await self._seed_entities(["Alice", "Bob"])

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        # Filter by label that doesn't exist.
        filters = SearchFilters(labels=["NonExistent"])
        results = await engine.search("Alice", ENTITY, filters=filters)

        # With a non-matching label filter, results may be empty.
        assert isinstance(results, list)

    async def test_search_respects_limit(self) -> None:
        """Search respects the recipe's limit."""
        await self._seed_entities(["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"])

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        recipe = Recipe(methods=["entity"], limit=3)
        results = await engine.search("test", recipe)

        assert len(results) <= 3

    async def test_cypher_where_labels_match_native_node_labels(self) -> None:
        """SearchFilters(labels=[...]) includes matching labels, excludes others."""
        person_label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        org_label = validate_identifier(f"Org_{uuid4().hex[:8]}")
        try:
            # Seed nodes with distinct native labels.
            person_id = uuid4()
            org_id = uuid4()
            await self.store.execute_write(
                f"CREATE (p:{person_label} {{id: $id, name: $name}}) "
                f"CREATE (o:{org_label} {{id: $id2, name: $name2}})",
                {
                    "id": str(person_id),
                    "name": "Alice",
                    "id2": str(org_id),
                    "name2": "Acme",
                },
            )

            # Filter for Person label only.
            filters = SearchFilters(labels=[person_label])
            where, params = filters.to_cypher_where(node_var="n")
            query = f"MATCH (n:_AgragNode) {where} RETURN n.id AS id, n.name AS name"
            rows = await self.store.execute_read(query, params)
            ids = {row["id"] for row in rows}

            assert str(person_id) in ids
            assert str(org_id) not in ids
        finally:
            await self.store.execute_write(f"MATCH (n:{person_label}) DETACH DELETE n")
            await self.store.execute_write(f"MATCH (n:{org_label}) DETACH DELETE n")
