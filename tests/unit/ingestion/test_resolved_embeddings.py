"""Tests for resolved-entity embedding writes and their sync status."""

from collections.abc import Sequence
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agrag.common.data_models.graph_record import DeferredWrites
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.vector_record import Distance
from agrag.embedding.base import Embedder
from agrag.ingestion.resolved_embeddings import embed_resolved_entities
from agrag.loaders.types import ErrorPolicy


class _Embedder(Embedder):
    """An embedding test double with a configurable failure."""

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
    """Build one resolved entity."""
    return ResolvedEntity(
        id=uuid4(),
        label="Person",
        name="Ada Lovelace",
        properties={"description": "mathematician"},
        member_ids=[uuid4(), uuid4()],
    )


class TestEmbedResolvedEntities:
    """Resolved entity embeddings and their sync status live on the graph."""

    async def test_successful_write_marks_entity_synced(self) -> None:
        """A matched graph write sets the status to synced."""
        entity = _entity()
        graph_store = SimpleNamespace(
            vector_value=lambda expression: expression,
            execute_write=AsyncMock(
                return_value=[{"id": str(entity.id), "written": True}]
            ),
        )

        failures = await embed_resolved_entities(
            [entity],
            embedder=_Embedder(),
            graph_store=graph_store,
            error_policy=ErrorPolicy.RAISE,
        )

        assert failures == []
        assert entity.vector_sync_status == "synced"
        assert entity.embedding == [1.0, 2.0]
        assert graph_store.execute_write.await_count == 2

    async def test_failed_graph_write_clears_embedding_and_marks_failed(self) -> None:
        """A failed write is reported, clears the vector, and marks it failed."""
        entity = _entity()
        graph_store = SimpleNamespace(
            vector_value=lambda expression: expression,
            execute_write=AsyncMock(
                side_effect=[
                    RuntimeError("graph store down"),
                    [{"id": str(entity.id), "written": True}],
                    [{"id": str(entity.id), "written": True}],
                ]
            ),
        )

        failures = await embed_resolved_entities(
            [entity],
            embedder=_Embedder(),
            graph_store=graph_store,
            error_policy=ErrorPolicy.SKIP,
        )

        assert [failure.error_message for failure in failures] == ["graph store down"]
        assert entity.vector_sync_status == "failed"
        assert entity.vector_sync_error == "graph store down"
        assert entity.embedding is None

    async def test_raise_policy_reraises_after_marking_failed(self) -> None:
        """RAISE propagates the embed failure once the entity is marked failed."""
        entity = _entity()
        graph_store = SimpleNamespace(
            vector_value=lambda expression: expression,
            execute_write=AsyncMock(
                return_value=[{"id": str(entity.id), "written": True}]
            ),
        )

        with pytest.raises(RuntimeError, match="embed backend down"):
            await embed_resolved_entities(
                [entity],
                embedder=_Embedder(RuntimeError("embed backend down")),
                graph_store=graph_store,
                error_policy=ErrorPolicy.RAISE,
            )

        assert entity.vector_sync_status == "failed"
        assert entity.embedding is None

    async def test_entity_replaced_concurrently_keeps_its_status(self) -> None:
        """Only entities the guarded write matched get a new status.

        Regression test: the guarded embedding write can match zero rows for
        one entity in a batch because a concurrent rebuild replaced it. That
        entity's status must stay as the concurrent call left it.
        """
        matched, unmatched = _entity(), _entity()
        graph_store = SimpleNamespace(
            vector_value=lambda expression: expression,
            execute_write=AsyncMock(
                return_value=[{"id": str(matched.id), "written": True}]
            ),
        )

        failures = await embed_resolved_entities(
            [matched, unmatched],
            embedder=_Embedder(),
            graph_store=graph_store,
            error_policy=ErrorPolicy.RAISE,
        )

        assert failures == []
        assert matched.vector_sync_status == "synced"
        assert unmatched.vector_sync_status == "pending"

    async def test_job_defers_embedding_of_a_committed_entity(self) -> None:
        """A job's embedding over a committed entity waits for the commit."""
        entity = _entity()
        graph_store = SimpleNamespace(
            vector_value=lambda expression: expression,
            execute_write=AsyncMock(
                return_value=[{"id": str(entity.id), "written": False}]
            ),
        )
        deferred = DeferredWrites()

        failures = await embed_resolved_entities(
            [entity],
            embedder=_Embedder(),
            graph_store=graph_store,
            error_policy=ErrorPolicy.RAISE,
            pending_job_id=uuid4(),
            deferred=deferred,
        )

        assert failures == []
        assert len(deferred) == 1
        assert entity.vector_sync_status == "pending"

    async def test_empty_input_writes_nothing(self) -> None:
        """No entities means no embedding call and no graph write."""
        graph_store = SimpleNamespace(
            vector_value=lambda expression: expression, execute_write=AsyncMock()
        )

        failures = await embed_resolved_entities(
            [],
            embedder=_Embedder(),
            graph_store=graph_store,
            error_policy=ErrorPolicy.RAISE,
        )

        assert failures == []
        graph_store.execute_write.assert_not_awaited()
