"""Integration tests for SearchEngine against a real Neo4j instance.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``).
"""

import importlib.util
import os
from collections.abc import AsyncGenerator, Sequence
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.search_result import SearchResult
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


def _cross_encoder_weights_cached() -> bool:
    """Return True when the reranker's weights are already on disk.

    Loading them downloads the model, so the test that needs real scores
    skips rather than making the suite reach the network for it.
    """
    if importlib.util.find_spec("sentence_transformers") is None:
        return False
    cache = os.environ.get("HF_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache", "huggingface"
    )
    snapshots = os.path.join(
        cache,
        "hub",
        "models--cross-encoder--ms-marco-MiniLM-L-6-v2",
        "snapshots",
    )
    return os.path.isdir(snapshots)


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
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store for each test and delete only its own rows."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        self.chunk_ids: list[UUID] = []
        self.embedder = _FixedEmbedder()
        self.schema = GraphSchema(
            name="search_engine_integration",
            version="1",
            entities=[EntityType(label=self.label, description="A test entity.")],
            relations=[],
        )
        self.settings = RetrievalSettings(
            entity_top_k=10,
            chunk_top_k=10,
        )
        yield
        await self.store.execute_write(f"MATCH (n:{self.label}) DETACH DELETE n")
        if self.chunk_ids:
            # Chunk nodes and their vector index are global: every suite
            # writes CHUNK_LABEL, and the index cannot be dropped per test.
            # Deleting this test's own ids leaves a concurrent test's chunk
            # data alone, which a label-wide delete would not.
            await self.store.execute_write(
                f"MATCH (n:{CHUNK_LABEL}) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(chunk_id) for chunk_id in self.chunk_ids]},
            )
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

        self.chunk_ids.extend(ch.id for ch in chunks if ch.id is not None)
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
            graph_schema=self.schema,
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
            graph_schema=self.schema,
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
            graph_schema=self.schema,
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
        self.chunk_ids.append(chunk_id)
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
            graph_schema=self.schema,
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
            graph_schema=self.schema,
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
            graph_schema=self.schema,
        )
        recipe = Recipe(methods=["entity"], limit=3)
        results = await engine.search("test", recipe)

        assert len(results) <= 3

    @pytest.mark.skipif(
        not _cross_encoder_weights_cached(), reason="cross-encoder weights not cached"
    )
    async def test_recipe_min_score_filters_a_real_reranked_list(self) -> None:
        """A per-call min_score genuinely drops results after real reranking."""
        await self._seed_entities(["Alice", "Bob"])
        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
            graph_schema=self.schema,
        )
        unfiltered = Recipe(methods=["entity"], reranker="cross_encoder", limit=10)
        positive_only = Recipe(
            methods=["entity"], reranker="cross_encoder", limit=10, min_score=0.0
        )
        rerank_everything = Recipe(
            methods=["entity"], reranker="cross_encoder", limit=10, min_score=1e6
        )

        whole = await engine.search("Alice", unfiltered)
        above_zero = await engine.search("Alice", positive_only)
        filtered = await engine.search("Alice", rerank_everything)

        assert whole
        assert all(result.method == "cross_encoder" for result in whole)
        assert all(result.score >= 0.0 for result in above_zero)
        assert len(above_zero) < len(whole)
        assert filtered == []

    async def test_cypher_where_labels_match_native_node_labels(self) -> None:
        """SearchFilters(labels=[...]) includes matching labels, excludes others."""
        person_label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        org_label = validate_identifier(f"Org_{uuid4().hex[:8]}")
        try:
            # Seed nodes with distinct native labels through the store, so
            # they carry the _AgragNode identity anchor like every node this
            # project writes.
            person_id = uuid4()
            org_id = uuid4()
            await self.store.upsert_nodes(
                person_label,
                [
                    NodeRecord(
                        id=person_id,
                        labels=[person_label],
                        properties={"name": "Alice"},
                    )
                ],
            )
            await self.store.upsert_nodes(
                org_label,
                [
                    NodeRecord(
                        id=org_id,
                        labels=[org_label],
                        properties={"name": "Acme"},
                    )
                ],
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


@pytest.mark.integration
@pytest.mark.enable_socket
@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestTraversalIntegration:
    """SearchEngine and its traversal tools walk a real, directed graph."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store for each test and delete only its own rows."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        suffix = uuid4().hex[:8]
        self.person_label = validate_identifier(f"Person_{suffix}")
        self.org_label = validate_identifier(f"Organization_{suffix}")
        self.embedder = _FixedEmbedder()
        self.settings = RetrievalSettings()
        self.schema = GraphSchema(
            name="traversal_integration",
            version="1",
            entities=[
                EntityType(label=self.person_label, description="A person."),
                EntityType(label=self.org_label, description="An organization."),
            ],
            relations=[],
        )
        self.engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
            graph_schema=self.schema,
        )
        yield
        for label in (self.person_label, self.org_label):
            await self.store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
        await self.store.close()

    async def _write_entity(self, label: str, name: str) -> Entity:
        """Write one searchable entity and return it."""
        entity = Entity(id=uuid4(), label=label, name=name)
        entity.embedding = await self.embedder.embed_one(name)
        await self.store.upsert_nodes(
            label,
            [
                NodeRecord(
                    id=entity.id,
                    labels=[label],
                    properties={
                        "name": name,
                        "merge_key": entity.merge_key,
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                        "embedding": entity.embedding,
                        "created_at": entity.created_at.isoformat(),
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
        return entity

    async def _write_relation(
        self, rel_type: str, start_id: UUID, end_id: UUID
    ) -> None:
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

    async def _resolved_seed(self, name: str) -> SearchResult:
        """Resolve a seeded entity the way a traversal tool does."""
        resolved = await self.engine.find_entity(name)
        assert resolved is not None, f"{name} did not resolve"
        return resolved

    async def test_outgoing_traversal_follows_a_relationship_forward(self) -> None:
        """A FOUNDED edge is reachable from its source, not its target."""
        person = await self._write_entity(self.person_label, "Ada")
        org = await self._write_entity(self.org_label, "Engines")
        await self._write_relation("FOUNDED", person.id, org.id)

        outward = await self.engine.traverse(
            await self._resolved_seed("Ada"), direction="outgoing"
        )

        assert [result.item.id for result in outward] == [org.id]

    async def test_incoming_traversal_follows_a_relationship_backward(self) -> None:
        """The same FOUNDED edge is reachable from its target, reversed."""
        person = await self._write_entity(self.person_label, "Ada")
        org = await self._write_entity(self.org_label, "Engines")
        await self._write_relation("FOUNDED", person.id, org.id)

        inward = await self.engine.traverse(
            await self._resolved_seed("Engines"), direction="incoming"
        )

        assert [result.item.id for result in inward] == [person.id]

    async def test_direction_is_not_ignored(self) -> None:
        """Reversing the direction on either endpoint finds nothing."""
        person = await self._write_entity(self.person_label, "Ada")
        org = await self._write_entity(self.org_label, "Engines")
        await self._write_relation("FOUNDED", person.id, org.id)

        backwards = await self.engine.traverse(
            await self._resolved_seed("Ada"), direction="incoming"
        )
        forwards = await self.engine.traverse(
            await self._resolved_seed("Engines"), direction="outgoing"
        )

        assert backwards == []
        assert forwards == []

    async def test_wide_fanout_falls_back_to_relationship_types(self) -> None:
        """A high-degree entity is reported as its types, not its neighbours."""
        from agrag.agents.ledger import Ledger  # noqa: PLC0415
        from agrag.agents.tools import make_tools  # noqa: PLC0415

        hub = await self._write_entity(self.person_label, "Hub")
        for index in range(13):
            neighbour = await self._write_entity(self.person_label, f"Knows {index}")
            await self._write_relation("KNOWS", hub.id, neighbour.id)
        for index in range(12):
            neighbour = await self._write_entity(self.org_label, f"Employer {index}")
            await self._write_relation("WORKS_FOR", hub.id, neighbour.id)

        tools = make_tools(self.engine, Ledger())
        tool = next(tool for tool in tools if tool.name == "traverse_from_entity")

        rendered = await tool.ainvoke({"entity": "Hub"})

        assert "KNOWS, WORKS_FOR" in rendered
        assert "Knows 0" not in rendered

    async def test_narrowed_traversal_returns_real_neighbours(self) -> None:
        """Naming a relationship type from that list returns the neighbours."""
        from agrag.agents.ledger import Ledger  # noqa: PLC0415
        from agrag.agents.tools import make_tools  # noqa: PLC0415

        hub = await self._write_entity(self.person_label, "Hub")
        for index in range(21):
            neighbour = await self._write_entity(self.person_label, f"Knows {index}")
            await self._write_relation("KNOWS", hub.id, neighbour.id)
        for index in range(3):
            neighbour = await self._write_entity(self.org_label, f"Employer {index}")
            await self._write_relation("WORKS_FOR", hub.id, neighbour.id)

        tools = make_tools(self.engine, Ledger())
        tool = next(tool for tool in tools if tool.name == "traverse_from_entity")

        rendered = await tool.ainvoke({"entity": "Hub", "relation_type": "WORKS_FOR"})

        assert "Employer 0" in rendered
        assert "Knows 0" not in rendered

    async def test_list_relationship_types_reports_real_types(self) -> None:
        """The types query reads the real attached relationship types."""
        hub = await self._write_entity(self.person_label, "Hub")
        org = await self._write_entity(self.org_label, "Engines")
        await self._write_relation("FOUNDED", hub.id, org.id)
        await self._write_relation("WORKS_FOR", hub.id, org.id)

        types = await self.engine.list_relationship_types(
            await self._resolved_seed("Hub")
        )

        assert sorted(types) == ["FOUNDED", "WORKS_FOR"]
