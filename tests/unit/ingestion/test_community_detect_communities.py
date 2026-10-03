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

    async def test_writes_communities_and_members_when_applied(self) -> None:
        """Apply stores each community, its member edges and its vector."""
        ids, edges = _two_triangles()
        graph_store, transaction = _graph_store(ids, edges)
        vector_store = _vector_store()

        report = await detect_communities(
            graph_store,
            vector_store=vector_store,
            embedder=_embedder(),
            settings=RetrievalSettings(),
            apply=True,
        )

        assert report.applied is True
        assert report.failures == []
        assert len(report.communities) == 2
        written = transaction.upsert_nodes.await_args.args[1]
        assert len(written) == 2
        member_edges = transaction.upsert_relations.await_args.args[0]
        assert len(member_edges) == 6
        vector_store.upsert.assert_awaited_once()
        assert len(vector_store.upsert.await_args.args[1]) == 2

    async def test_empty_corpus_returns_no_communities(self) -> None:
        """A graph without relations yields an empty, unapplied report."""
        graph_store, transaction = _graph_store([], [])

        report = await detect_communities(
            graph_store,
            vector_store=_vector_store(),
            embedder=_embedder(),
            settings=RetrievalSettings(),
        )

        assert report.communities == []
        assert report.applied is False
        transaction.execute_write.assert_not_called()

    async def test_empty_corpus_applied_removes_stale_communities(self) -> None:
        """Applying to a graph without relations clears earlier communities."""
        graph_store, transaction = _graph_store([], [])
        vector_store = _vector_store()

        report = await detect_communities(
            graph_store,
            vector_store=vector_store,
            embedder=_embedder(),
            settings=RetrievalSettings(),
            apply=True,
        )

        assert report.communities == []
        assert report.applied is True
        transaction.execute_write.assert_awaited()
        vector_store.scroll.assert_awaited()
        transaction.upsert_nodes.assert_not_called()

    async def test_dry_run_writes_nothing(self) -> None:
        """Without apply the report lists communities and no store changes."""
        ids, edges = _two_triangles()
        graph_store, transaction = _graph_store(ids, edges)
        vector_store = _vector_store()
        embedder = _embedder()

        report = await detect_communities(
            graph_store,
            vector_store=vector_store,
            embedder=embedder,
            settings=RetrievalSettings(),
        )

        assert len(report.communities) == 2
        assert report.applied is False
        transaction.execute_write.assert_not_called()
        transaction.upsert_nodes.assert_not_called()
        transaction.upsert_relations.assert_not_called()
        vector_store.scroll.assert_not_called()
        vector_store.upsert.assert_not_called()
        embedder.embed.assert_not_called()

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
