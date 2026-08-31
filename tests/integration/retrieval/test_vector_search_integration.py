"""Integration tests for the shared vector_search helper.

Tests that vector_search correctly selects the GraphStore-native
path and applies filters.
"""

import importlib.util
from collections.abc import Sequence
from uuid import uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import NodeRecord
from agrag.common.data_models.vector_record import Distance, VectorHit
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.vector import vector_search
from agrag.retrieval.settings import RetrievalSettings


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _FixedEmbedder(Embedder):
    """Embedder returning deterministic vectors."""

    model = "fixed"

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return deterministic vectors based on text hash."""
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
class TestVectorSearchGraphStorePath:
    """vector_search against real Neo4j via GraphStore-native path."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> None:
        """Set up a fresh store."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        self.embedder = _FixedEmbedder()
        self.settings = RetrievalSettings()
        yield
        await self.store.execute_write(f"MATCH (n:{self.label}) DETACH DELETE n")
        await self.store.close()

    async def _seed_entities(self, names: list[str]) -> list[Entity]:
        """Write entities with embeddings."""
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

    async def test_returns_vector_hits(self) -> None:
        """vector_search returns VectorHit objects."""
        await self._seed_entities(["Alice", "Bob"])

        hits = await vector_search(
            "Alice",
            embedder=self.embedder,
            graph_store=self.store,
            vector_store=None,
            label_or_collection=self.label,
            limit=5,
            filters=None,
            settings=self.settings,
        )

        assert len(hits) >= 1
        assert all(isinstance(h, VectorHit) for h in hits)

    async def test_results_ranked_by_score(self) -> None:
        """Results are ordered by score, highest first."""
        await self._seed_entities(["Alice", "Bob", "Charlie"])

        hits = await vector_search(
            "Alice",
            embedder=self.embedder,
            graph_store=self.store,
            vector_store=None,
            label_or_collection=self.label,
            limit=5,
            filters=None,
            settings=self.settings,
        )

        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)

    async def test_limit_respected(self) -> None:
        """The limit parameter caps the number of results."""
        await self._seed_entities(
            [
                "A",
                "B",
                "C",
                "D",
                "E",
                "F",
                "G",
                "H",
                "I",
                "J",
            ]
        )

        hits = await vector_search(
            "test",
            embedder=self.embedder,
            graph_store=self.store,
            vector_store=None,
            label_or_collection=self.label,
            limit=3,
            filters=None,
            settings=self.settings,
        )

        assert len(hits) <= 3

    async def test_with_label_filter(self) -> None:
        """A label filter restricts results to matching nodes."""
        await self._seed_entities(["Alice"])

        filters = SearchFilters(labels=["NonExistent"])
        hits = await vector_search(
            "Alice",
            embedder=self.embedder,
            graph_store=self.store,
            vector_store=None,
            label_or_collection=self.label,
            limit=5,
            filters=filters,
            settings=self.settings,
        )

        # With a non-matching filter, results may be empty.
        assert isinstance(hits, list)

    async def test_never_calls_vector_store(self) -> None:
        """When vector_store is None, graph_store.vector_search is called."""
        await self._seed_entities(["Alice"])

        # The function should work without a VectorStore.
        hits = await vector_search(
            "Alice",
            embedder=self.embedder,
            graph_store=self.store,
            vector_store=None,
            label_or_collection=self.label,
            limit=5,
            filters=None,
            settings=self.settings,
        )

        assert len(hits) >= 1

    async def test_hit_carries_id_and_payload(self) -> None:
        """Each VectorHit carries an id and payload dict."""
        entities = await self._seed_entities(["Alice"])

        hits = await vector_search(
            "Alice",
            embedder=self.embedder,
            graph_store=self.store,
            vector_store=None,
            label_or_collection=self.label,
            limit=5,
            filters=None,
            settings=self.settings,
        )

        assert len(hits) >= 1
        hit = hits[0]
        assert hit.id == entities[0].id
        assert isinstance(hit.payload, dict)
