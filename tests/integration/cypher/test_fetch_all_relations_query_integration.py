"""Integration tests for fetch_all_relations_query against real Neo4j.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). The
``skipif`` only guards the missing extra; with the extra installed the
tests expect a reachable Neo4j at the default ``NEO4J_URI``.

Covers the real Cypher builder's filtering: system edges (MENTIONED_IN),
Chunk endpoints, and tombstone endpoints are excluded.
"""

import importlib.util
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.cypher.entities import validate_identifier
from agrag.cypher.relations import fetch_all_relations_query
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _FixedEmbedder(Embedder):
    """Embedder returning deterministic vectors for testing."""

    model = "fixed"

    async def dimensions(self) -> int:
        """Return fixed dimension count."""
        return 4

    async def embed(self, texts):
        """Return a deterministic vector per text."""
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestFetchAllRelationsQueryIntegration:
    """``fetch_all_relations_query`` excludes system and tombstone edges."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store with a unique entity label."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.entity_label = validate_identifier(f"Entity_{uuid4().hex[:8]}")
        self.embedder = _FixedEmbedder()
        yield
        await self.store.execute_write(f"MATCH (n:{self.entity_label}) DETACH DELETE n")
        await self.store.close()

    async def test_excludes_mentioned_in_chunk_and_tombstone(self) -> None:
        """Only live domain relations survive the filter.

        Writes 1 KNOWS (kept), 1 MENTIONED_IN (excluded), 1 Chunk
        endpoint (excluded), and 1 tombstone endpoint (excluded).
        Asserts only the KNOWS row remains among the seeded ids.
        """
        # Unique ids for deterministic filtering.
        good_a = uuid4()
        good_b = uuid4()
        mentioned_a = uuid4()
        mentioned_b = uuid4()
        chunk_id = uuid4()
        chunk_target = uuid4()
        tombstone_id = uuid4()
        survivor_id = uuid4()
        chunk_target_b = uuid4()
        # Track Chunk id for targeted cleanup.
        created_chunk_ids = [chunk_id]

        try:
            await self.store.upsert_nodes(
                self.entity_label,
                [
                    NodeRecord(
                        id=good_a, labels=[self.entity_label], properties={"name": "a"}
                    ),
                    NodeRecord(
                        id=good_b, labels=[self.entity_label], properties={"name": "b"}
                    ),
                    NodeRecord(
                        id=mentioned_a,
                        labels=[self.entity_label],
                        properties={"name": "c"},
                    ),
                    NodeRecord(
                        id=mentioned_b,
                        labels=[self.entity_label],
                        properties={"name": "d"},
                    ),
                    NodeRecord(
                        id=chunk_target,
                        labels=[self.entity_label],
                        properties={"name": "e"},
                    ),
                    NodeRecord(
                        id=survivor_id,
                        labels=[self.entity_label],
                        properties={"name": "f"},
                    ),
                    NodeRecord(
                        id=tombstone_id,
                        labels=[self.entity_label],
                        properties={"name": "g", "merged_into": str(survivor_id)},
                    ),
                    NodeRecord(
                        id=chunk_target_b,
                        labels=[self.entity_label],
                        properties={"name": "h"},
                    ),
                ],
            )
            await self.store.upsert_nodes(
                CHUNK_LABEL,
                [
                    NodeRecord(
                        id=chunk_id,
                        labels=[CHUNK_LABEL],
                        properties={
                            "document_id": str(uuid4()),
                            "index": 0,
                            "text": "chunk text",
                            "provenance": '{"kind":"text","char_start":0,"char_end":10}',  # noqa: E501
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
                        id=uuid4(),
                        type="KNOWS",
                        start_id=good_a,
                        end_id=good_b,
                        properties={"source_chunk_ids": []},
                    ),
                    RelationRecord(
                        id=uuid4(),
                        type="MENTIONED_IN",
                        start_id=mentioned_a,
                        end_id=mentioned_b,
                        properties={},
                    ),
                    RelationRecord(
                        id=uuid4(),
                        type="KNOWS",
                        start_id=chunk_id,
                        end_id=chunk_target,
                        properties={},
                    ),
                    RelationRecord(
                        id=uuid4(),
                        type="KNOWS",
                        start_id=tombstone_id,
                        end_id=chunk_target_b,
                        properties={},
                    ),
                ]
            )

            rows = await self.store.execute_read(
                fetch_all_relations_query(), {"skip": 0, "limit": 100}
            )

            seeded_source_ids = {
                str(good_a),
                str(mentioned_a),
                str(chunk_id),
                str(tombstone_id),
            }
            relevant = [r for r in rows if r["source_id"] in seeded_source_ids]

            assert len(relevant) == 1
            assert relevant[0]["source_id"] == str(good_a)
            assert relevant[0]["target_id"] == str(good_b)
        finally:
            for cid in created_chunk_ids:
                await self.store.execute_write(
                    "MATCH (n:Chunk {id: $id}) DETACH DELETE n",
                    {"id": str(cid)},
                )
