"""Tests for resolved-entity embedding and vector synchronization."""

from collections.abc import Sequence
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.vector_record import Distance, VectorRecord
from agrag.embedding.base import Embedder
from agrag.ingestion.resolved_embeddings import (
    _synchronize_resolved_entity_vectors,
    embed_resolved_entities,
)
from agrag.loaders.corpus.types import ErrorPolicy


class _Embedder(Embedder):
    """An embedding test double with a configurable result."""

    model = "test"
    distance = Distance.COSINE

    def __init__(self, failure: Exception | None = None) -> None:
        """Create the test embedder."""
        self.failure = failure

    async def dimensions(self) -> int:
        """Return the fixed test-vector size."""
        return 2

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector for each requested text or raise the configured error."""
        if self.failure is not None:
            raise self.failure
        return [[1.0, 2.0] for _ in texts]


def _entity() -> ResolvedEntity:
    """Build one materialized entity."""
    return ResolvedEntity(
        id=uuid4(),
        label="Person",
        name="Ada Lovelace",
        properties={"description": "mathematician"},
        member_ids=[uuid4(), uuid4()],
    )


class TestEmbedResolvedEntities:
    """Resolved entity vectors have an explicit graph-to-vector-store state."""

    async def test_writes_graph_vector_mirror_and_synced_status(self) -> None:
        """Successful synchronization marks derived entities as ready to retrieve."""
        calls: list[str] = []

        async def execute_write(*_args: object) -> None:
            calls.append("graph")

        async def upsert(*_args: object) -> None:
            calls.append("vector")

        graph_store = SimpleNamespace(
            execute_write=AsyncMock(side_effect=execute_write)
        )
        vector_store = SimpleNamespace(
            upsert=AsyncMock(side_effect=upsert), delete=AsyncMock()
        )
        entity = _entity()

        failures = await embed_resolved_entities(
            [entity],
            embedder=_Embedder(),
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collection="resolved",
            error_policy=ErrorPolicy.RAISE,
        )

        assert failures == []
        assert entity.embedding == [1.0, 2.0]
        vector_store.upsert.assert_awaited_once()
        records = vector_store.upsert.await_args.args[1]
        assert isinstance(records[0], VectorRecord)
        assert records[0].payload["resolved"] is True
        assert records[0].payload["name"] == entity.name
        assert graph_store.execute_write.await_count == 2
        assert calls == ["graph", "vector", "graph"]
        assert entity.vector_sync_status == "synced"
        assert entity.vector_sync_error is None

    async def test_removes_stale_vector_and_marks_failure_after_sync_error(
        self,
    ) -> None:
        """A failed mirror write cannot leave a retrievable stale resolved vector."""
        graph_store = SimpleNamespace(execute_write=AsyncMock())
        vector_store = SimpleNamespace(
            upsert=AsyncMock(side_effect=RuntimeError("vector store down")),
            delete=AsyncMock(),
        )
        entity = _entity()

        failures = await embed_resolved_entities(
            [entity],
            embedder=_Embedder(),
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collection="resolved",
            error_policy=ErrorPolicy.SKIP,
        )

        assert [failure.item_id for failure in failures] == [
            "resolved_entity_embeddings"
        ]
        vector_store.delete.assert_awaited_once_with("resolved", [entity.id])
        statuses = [
            call.args[1]["records"][0]["status"]
            for call in graph_store.execute_write.await_args_list
            if "status" in call.args[1]["records"][0]
        ]
        assert statuses == ["failed"]
        assert entity.embedding is None
        assert entity.vector_sync_status == "failed"
        assert entity.vector_sync_error == "vector store down"

    async def test_skips_vector_store_when_graph_embedding_write_fails(self) -> None:
        """A graph write failure never sends a vector lacking graph state."""
        graph_store = SimpleNamespace(
            execute_write=AsyncMock(
                side_effect=[RuntimeError("graph store down"), None, None]
            )
        )
        vector_store = SimpleNamespace(upsert=AsyncMock(), delete=AsyncMock())
        entity = _entity()

        failures = await embed_resolved_entities(
            [entity],
            embedder=_Embedder(),
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collection="resolved",
            error_policy=ErrorPolicy.SKIP,
        )

        assert [failure.error_message for failure in failures] == ["graph store down"]
        vector_store.upsert.assert_not_awaited()
        vector_store.delete.assert_awaited_once_with("resolved", [entity.id])
        assert entity.vector_sync_status == "failed"

    async def test_retries_a_failed_synchronization_with_a_new_materialization_pass(
        self,
    ) -> None:
        """A later pass can make a previously failed derived vector searchable."""
        graph_store = SimpleNamespace(execute_write=AsyncMock())
        vector_store = SimpleNamespace(
            upsert=AsyncMock(side_effect=[RuntimeError("vector store down"), None]),
            delete=AsyncMock(),
        )
        entity = _entity()

        first_failures = await embed_resolved_entities(
            [entity],
            embedder=_Embedder(),
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collection="resolved",
            error_policy=ErrorPolicy.SKIP,
        )
        second_failures = await embed_resolved_entities(
            [entity],
            embedder=_Embedder(),
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collection="resolved",
            error_policy=ErrorPolicy.RAISE,
        )

        assert len(first_failures) == 1
        assert second_failures == []
        assert entity.vector_sync_status == "synced"
        assert entity.vector_sync_error is None
        vector_store.delete.assert_awaited_once_with("resolved", [entity.id])

    async def test_raises_after_cleaning_up_a_failed_synchronization(self) -> None:
        """RAISE leaves neither graph nor mirrored vector searchable after failure."""
        graph_store = SimpleNamespace(execute_write=AsyncMock())
        vector_store = SimpleNamespace(
            upsert=AsyncMock(side_effect=RuntimeError("vector store down")),
            delete=AsyncMock(),
        )
        entity = _entity()

        with pytest.raises(RuntimeError, match="vector store down"):
            await embed_resolved_entities(
                [entity],
                embedder=_Embedder(),
                graph_store=graph_store,
                vector_store=vector_store,
                vector_collection="resolved",
                error_policy=ErrorPolicy.RAISE,
            )

        vector_store.delete.assert_awaited_once_with("resolved", [entity.id])
        assert entity.embedding is None

    async def test_returns_without_writing_for_no_materialized_entities(self) -> None:
        """An empty materialization batch avoids all external calls."""
        graph_store = SimpleNamespace(execute_write=AsyncMock())
        vector_store = SimpleNamespace(upsert=AsyncMock(), delete=AsyncMock())

        failures = await embed_resolved_entities(
            [],
            embedder=_Embedder(),
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collection="resolved",
            error_policy=ErrorPolicy.RAISE,
        )

        assert failures == []
        graph_store.execute_write.assert_not_awaited()
        vector_store.upsert.assert_not_awaited()
        vector_store.delete.assert_not_awaited()

    async def test_marks_native_graph_vectors_synced_without_a_vector_store(
        self,
    ) -> None:
        """Native-vector retrieval is ready when no mirror store is configured."""
        graph_store = SimpleNamespace(execute_write=AsyncMock())
        entity = _entity()

        failures = await embed_resolved_entities(
            [entity],
            embedder=_Embedder(),
            graph_store=graph_store,
            vector_store=None,
            vector_collection="resolved",
            error_policy=ErrorPolicy.RAISE,
        )

        assert failures == []
        assert entity.vector_sync_status == "synced"
        assert graph_store.execute_write.await_count == 2


class TestSynchronizeResolvedEntityVectors:
    """Replacement vectors do not outlive their materialized graph nodes."""

    async def test_deletes_replaced_vectors_before_embedding_current_entities(
        self,
    ) -> None:
        """A replacement cannot leave a former vector searchable after a later error."""
        calls: list[str] = []

        async def execute_write(*_args: object) -> None:
            calls.append("graph")

        async def delete(*_args: object) -> None:
            calls.append("delete")

        async def upsert(*_args: object) -> None:
            calls.append("upsert")

        entity = _entity()
        replaced_id = uuid4()
        vector_store = SimpleNamespace(
            delete=AsyncMock(side_effect=delete),
            upsert=AsyncMock(side_effect=upsert),
        )
        failures = await _synchronize_resolved_entity_vectors(
            [entity],
            [replaced_id, replaced_id],
            embedder=_Embedder(),
            graph_store=SimpleNamespace(
                execute_write=AsyncMock(side_effect=execute_write)
            ),
            vector_store=vector_store,
            vector_collection="resolved",
            error_policy=ErrorPolicy.RAISE,
        )

        assert failures == []
        vector_store.delete.assert_awaited_once_with("resolved", [replaced_id])
        assert calls == ["delete", "graph", "upsert", "graph"]

    async def test_reports_stale_vector_delete_failure_with_skip(self) -> None:
        """A failed stale-vector deletion remains visible to the caller."""
        entity = _entity()
        graph_store = SimpleNamespace(execute_write=AsyncMock())
        vector_store = SimpleNamespace(
            delete=AsyncMock(side_effect=RuntimeError("delete failed")),
            upsert=AsyncMock(),
        )

        failures = await _synchronize_resolved_entity_vectors(
            [entity],
            [uuid4()],
            embedder=_Embedder(),
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collection="resolved",
            error_policy=ErrorPolicy.SKIP,
        )

        assert [failure.item_id for failure in failures] == [
            "resolved_entity_vector_store"
        ]
        assert entity.vector_sync_status == "synced"
