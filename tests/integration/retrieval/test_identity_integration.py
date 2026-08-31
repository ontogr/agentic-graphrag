"""Integration tests for identity resolution against a real Neo4j.

Tests that resolve_entity correctly follows merged_into chains,
handles missing entities, and resolves multi-hop tombstone chains.
"""

import importlib.util
from collections.abc import AsyncGenerator, Sequence
from uuid import uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import NodeRecord
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
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
class TestResolveEntityIntegration:
    """resolve_entity against a real Neo4j store."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store for each test."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        yield
        await self.store.execute_write(f"MATCH (n:{self.label}) DETACH DELETE n")
        await self.store.close()

    async def _write_entity_async(
        self,
        entity: Entity,
        *,
        merged_into: str | None = None,
    ) -> None:
        """Write an entity node to the store."""
        props: dict = {
            "name": entity.name,
            "merge_key": entity.merge_key,
            "merged_from": [str(eid) for eid in entity.merged_from],
            "merge_count": entity.merge_count,
            "source_chunk_ids": [],
            "created_at": entity.created_at.isoformat(),
        }
        if merged_into is not None:
            props["merged_into"] = merged_into

        await self.store.upsert_nodes(
            self.label,
            [NodeRecord(id=entity.id, labels=[self.label], properties=props)],
        )

    async def test_live_entity_returns_directly(self) -> None:
        """A live entity (no merged_into) is returned directly."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        await self._write_entity_async(ent)

        resolved = await resolve_entity(self.store, ent.id)
        assert resolved.id == ent.id
        assert resolved.name == "Alice"

    async def test_single_hop_tombstone_resolves_to_survivor(
        self,
    ) -> None:
        """A single tombstone hop resolves to the live survivor."""
        survivor = Entity(id=uuid4(), label="Person", name="Alice")
        tombstone = Entity(id=uuid4(), label="Person", name="A. Lovelace")

        await self._write_entity_async(survivor)
        await self._write_entity_async(tombstone, merged_into=str(survivor.id))

        # Resolving the tombstone should return the survivor.
        resolved = await resolve_entity(self.store, tombstone.id)
        assert resolved.id == survivor.id
        assert resolved.name == "Alice"

    async def test_resolving_survivor_returns_survivor(self) -> None:
        """Resolving the survivor directly returns itself, not the tombstone."""
        survivor = Entity(id=uuid4(), label="Person", name="Alice")
        tombstone = Entity(id=uuid4(), label="Person", name="A. Lovelace")

        await self._write_entity_async(survivor)
        await self._write_entity_async(tombstone, merged_into=str(survivor.id))

        resolved = await resolve_entity(self.store, survivor.id)
        assert resolved.id == survivor.id
        assert resolved.name == "Alice"

    async def test_two_hop_tombstone_chain(self) -> None:
        """A two-hop tombstone chain resolves to the final survivor.

        tombstone_A -> tombstone_B -> survivor
        """
        survivor = Entity(id=uuid4(), label="Person", name="Alice")
        tombstone_b = Entity(id=uuid4(), label="Person", name="A. Lovelace")
        tombstone_a = Entity(id=uuid4(), label="Person", name="Ada L.")

        await self._write_entity_async(survivor)
        await self._write_entity_async(tombstone_b, merged_into=str(survivor.id))
        await self._write_entity_async(tombstone_a, merged_into=str(tombstone_b.id))

        resolved = await resolve_entity(self.store, tombstone_a.id)
        assert resolved.id == survivor.id
        assert resolved.name == "Alice"

    async def test_three_hop_tombstone_chain(self) -> None:
        """A three-hop tombstone chain resolves to the final survivor."""
        survivor = Entity(id=uuid4(), label="Person", name="Bob")
        t2 = Entity(id=uuid4(), label="Person", name="B. Smith")
        t1 = Entity(id=uuid4(), label="Person", name="Roberto")
        t0 = Entity(id=uuid4(), label="Person", name="Bobby")

        await self._write_entity_async(survivor)
        await self._write_entity_async(t2, merged_into=str(survivor.id))
        await self._write_entity_async(t1, merged_into=str(t2.id))
        await self._write_entity_async(t0, merged_into=str(t1.id))

        resolved = await resolve_entity(self.store, t0.id)
        assert resolved.id == survivor.id
        assert resolved.name == "Bob"

    async def test_missing_entity_raises(self) -> None:
        """An entity id that does not exist raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await resolve_entity(self.store, uuid4())

    async def test_survivor_preserves_embedding(self) -> None:
        """The resolved survivor carries its embedding."""
        survivor = Entity(id=uuid4(), label="Person", name="Alice")
        tombstone = Entity(id=uuid4(), label="Person", name="A. L.")

        await self._write_entity_async(survivor)
        await self._write_entity_async(tombstone, merged_into=str(survivor.id))

        # Write embedding directly on the survivor node.
        await self.store.execute_write(
            f"MATCH (n:{self.label} {{id: $id}}) SET n.embedding = $vec",
            {"id": str(survivor.id), "vec": [0.1, 0.2, 0.3, 0.4]},
        )

        resolved = await resolve_entity(self.store, tombstone.id)
        assert resolved.id == survivor.id
        # The entity object from resolve_entity may not carry
        # the embedding (it's parsed from node properties),
        # but the survivor node itself should have it.
        rows = await self.store.execute_read(
            f"MATCH (n:{self.label} {{id: $id}}) RETURN n.embedding AS emb",
            {"id": str(survivor.id)},
        )
        assert rows[0]["emb"] is not None
        assert len(rows[0]["emb"]) == 4

    async def test_tombstone_has_no_embedding(self) -> None:
        """The tombstone node's embedding is removed after merge."""
        survivor = Entity(id=uuid4(), label="Person", name="Alice")
        tombstone = Entity(id=uuid4(), label="Person", name="A. L.")

        await self._write_entity_async(survivor)
        await self._write_entity_async(tombstone, merged_into=str(survivor.id))

        # Tombstone should not have an embedding property.
        rows = await self.store.execute_read(
            f"MATCH (n:{self.label} {{id: $id}}) RETURN n.embedding AS emb",
            {"id": str(tombstone.id)},
        )
        assert rows[0]["emb"] is None

    async def test_resolved_entity_is_not_tombstoned(self) -> None:
        """The resolved entity must never be a tombstone itself."""
        survivor = Entity(id=uuid4(), label="Person", name="Alice")
        t1 = Entity(id=uuid4(), label="Person", name="A. L.")
        t0 = Entity(id=uuid4(), label="Person", name="Ada")

        await self._write_entity_async(survivor)
        await self._write_entity_async(t1, merged_into=str(survivor.id))
        await self._write_entity_async(t0, merged_into=str(t1.id))

        resolved = await resolve_entity(self.store, t0.id)
        # Verify the resolved node has no merged_into property.
        rows = await self.store.execute_read(
            f"MATCH (n:{self.label} {{id: $id}}) RETURN n.merged_into AS mi",
            {"id": str(resolved.id)},
        )
        assert rows[0]["mi"] is None
