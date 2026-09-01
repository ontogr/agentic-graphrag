"""Integration tests for fusion and identity resolution.

Tests that fusion correctly deduplicates by identity_key after
identity resolution has resolved merged_into chains.
"""

import importlib.util
from collections.abc import AsyncGenerator, Sequence
from uuid import uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import NodeRecord
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.retrieval.fusion import fuse
from agrag.retrieval.identity import resolve_entity


neo4j_missing = importlib.util.find_spec("neo4j") is None


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
@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestFusionIdentityIntegration:
    """Fusion deduplicates after identity resolution against real Neo4j."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        yield
        await self.store.execute_write(f"MATCH (n:{self.label}) DETACH DELETE n")
        await self.store.close()

    async def test_fuse_deduplicates_same_entity(self) -> None:
        """Two SearchResults for the same entity fuse into one."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        r1 = SearchResult(item=ent, score=0.9, method="entity")
        r2 = SearchResult(item=ent, score=0.8, method="chunk")

        fused = fuse({"entity": [r1], "chunk": [r2]})
        assert len(fused) == 1
        assert fused[0].item.id == ent.id

    async def test_resolve_entity_returns_survivor(self) -> None:
        """resolve_entity follows merged_into to the live survivor."""
        survivor = Entity(id=uuid4(), label="Person", name="Alice (survivor)")
        tombstone = Entity(id=uuid4(), label="Person", name="Alice (old)")

        # Write both entities.
        await self.store.upsert_nodes(
            self.label,
            [
                NodeRecord(
                    id=survivor.id,
                    labels=[self.label],
                    properties={
                        "name": survivor.name,
                        "merge_key": survivor.merge_key,
                        "merged_from": [str(tombstone.id)],
                        "merge_count": 2,
                        "source_chunk_ids": [],
                        "created_at": (survivor.created_at.isoformat()),
                    },
                ),
                NodeRecord(
                    id=tombstone.id,
                    labels=[self.label],
                    properties={
                        "name": tombstone.name,
                        "merge_key": tombstone.merge_key,
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                        "merged_into": str(survivor.id),
                        "created_at": (tombstone.created_at.isoformat()),
                    },
                ),
            ],
        )

        # resolve_entity should follow merged_into and return survivor.
        resolved = await resolve_entity(self.store, tombstone.id)
        assert resolved.id == survivor.id
        assert resolved.name == survivor.name

    async def test_fuse_after_resolve_collapses_merged(
        self,
    ) -> None:
        """After resolve_entity, fused results collapse merged entities.

        Regression: am_diag's bug was deduplicating by pre-resolution
        id, so two results for the same entity (one via vector hit on
        the tombstone, one on the survivor) would not collapse.
        """
        survivor = Entity(id=uuid4(), label="Person", name="Alice")
        tombstone = Entity(id=uuid4(), label="Person", name="A. Lovelace")

        await self.store.upsert_nodes(
            self.label,
            [
                NodeRecord(
                    id=survivor.id,
                    labels=[self.label],
                    properties={
                        "name": survivor.name,
                        "merge_key": survivor.merge_key,
                        "merged_from": [str(tombstone.id)],
                        "merge_count": 2,
                        "source_chunk_ids": [],
                        "created_at": (survivor.created_at.isoformat()),
                    },
                ),
                NodeRecord(
                    id=tombstone.id,
                    labels=[self.label],
                    properties={
                        "name": tombstone.name,
                        "merge_key": tombstone.merge_key,
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                        "merged_into": str(survivor.id),
                        "created_at": (tombstone.created_at.isoformat()),
                    },
                ),
            ],
        )

        # Simulate what the retrievers do: resolve both ids.
        resolved_survivor = await resolve_entity(self.store, survivor.id)
        resolved_tombstone = await resolve_entity(self.store, tombstone.id)

        r1 = SearchResult(item=resolved_survivor, score=0.9, method="entity")
        r2 = SearchResult(item=resolved_tombstone, score=0.8, method="chunk")

        # Both should have the same identity_key after resolution.
        assert r1.identity_key == r2.identity_key

        fused = fuse({"entity": [r1], "chunk": [r2]})
        assert len(fused) == 1
        assert fused[0].item.id == survivor.id
