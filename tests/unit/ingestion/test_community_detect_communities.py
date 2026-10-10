"""Tests for detect_communities against fake stores at the driver boundary.

The graph store is a mock that answers relation reads, entity loads and
community writes. Clustering runs the real Leiden implementation on a graph
small enough to split the same way on every run.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from agrag.ingestion.community import detect_communities
from agrag.retrieval.settings import RetrievalSettings


def _entity_node(entity_id: UUID, name: str) -> dict[str, object]:
    return {"id": str(entity_id), "merge_key": f"Person:{name}", "name": name}


def _graph_store(
    entity_ids: list[UUID], edges: list[tuple[UUID, UUID]]
) -> tuple[AsyncMock, AsyncMock]:
    """Return a graph store holding the edges and its transaction handle."""
    rows = [
        {
            "source_id": str(a),
            "target_id": str(b),
            "source_chunk_ids": ["chunk"],
            "rel_type": "KNOWS",
            "rel_id": str(uuid4()),
        }
        for a, b in edges
    ]
    nodes = [_entity_node(i, f"entity-{n}") for n, i in enumerate(entity_ids)]

    async def execute_read(query: str, params: dict) -> list[dict]:
        if "ids" in params:
            wanted = set(params["ids"])
            return [{"n": n} for n in nodes if n["id"] in wanted]
        return rows if params["last_a"] == "" else []

    transaction = AsyncMock()
    transaction.execute_write.return_value = [{"deleted": 0}]
    store = MagicMock()
    store.execute_read = AsyncMock(side_effect=execute_read)

    @asynccontextmanager
    async def open_transaction():
        yield transaction

    store.transaction = open_transaction
    return store, transaction


def _vector_store() -> AsyncMock:
    store = AsyncMock()
    store.scroll.return_value = ([], None)
    return store


def _embedder() -> AsyncMock:
    embedder = AsyncMock()
    embedder.embed.side_effect = lambda texts: [[0.1, 0.2] for _ in texts]
    return embedder


def _two_triangles() -> tuple[list[UUID], list[tuple[UUID, UUID]]]:
    ids = [uuid4() for _ in range(6)]
    first, second = ids[:3], ids[3:]
    edges = [(first[0], first[1]), (first[1], first[2]), (first[0], first[2])]
    edges += [(second[0], second[1]), (second[1], second[2]), (second[0], second[2])]
    return ids, edges


class TestDetectCommunities:
    """detect_communities reads, clusters and writes through the stores."""

    @pytest.mark.parametrize("failing_call", ["scroll", "upsert"])
    async def test_vector_store_failure_is_reported_not_raised(
        self, failing_call: str
    ) -> None:
        """A vector store error lands in failures; the graph write stays."""
        ids, edges = _two_triangles()
        graph_store, transaction = _graph_store(ids, edges)
        vector_store = _vector_store()
        getattr(vector_store, failing_call).side_effect = RuntimeError("store down")

        report = await detect_communities(
            graph_store,
            vector_store=vector_store,
            embedder=_embedder(),
            settings=RetrievalSettings(),
            apply=True,
        )

        assert report.applied is True
        assert len(report.communities) == 2
        assert [f.item_id for f in report.failures] == ["community_vector_store"]
        assert report.failures[0].error_type == "RuntimeError"
        transaction.upsert_nodes.assert_awaited()
