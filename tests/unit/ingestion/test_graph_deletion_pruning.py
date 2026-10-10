"""Tests for deletion-triggered pruning.

prune_orphaned_entities runs against a scripted GraphStore: orphans lose
their nodes, and each affected cluster is rebuilt over its survivors.
"""

from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Any
from uuid import UUID, uuid4

from agrag.common.data_models.graph_record import (
    NodeRecord,
    RelationRecord,
    UpsertResult,
)
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.vector_record import Distance, VectorHit
from agrag.graphdb.base import GraphStore
from agrag.ingestion.resolved_entities import prune_orphaned_entities


def _schema() -> GraphSchema:
    """Build a minimal entity schema."""
    return GraphSchema(
        name="test",
        version="1",
        entities=[EntityType(label="Person", description="", properties={})],
        relations=[],
    )


def _node(entity_id: UUID, name: str) -> dict[str, Any]:
    """Build a flat entity node row the pipeline parser accepts."""
    return {"id": str(entity_id), "name": name, "merge_key": f"Person:{name}"}


class _ScriptedStore(GraphStore):
    """GraphStore serving canned reads and routed write responses."""

    def __init__(
        self,
        reads: list[list[dict[str, Any]]],
        writes: dict[str, list[dict[str, Any]]],
    ) -> None:
        """Queue read responses and route writes by query substring."""
        self._reads = list(reads)
        self._writes = writes
        self.read_calls: list[tuple[str, Any]] = []
        self.write_calls: list[tuple[str, Any]] = []

    async def connect(self) -> None:
        """No-op connect."""
        return

    async def close(self) -> None:
        """No-op close."""
        return

    def session(self) -> AbstractAsyncContextManager[Any]:
        """Return a no-op async session."""

        class _Session:
            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *exc: object) -> None:
                return None

        return _Session()  # type: ignore[return-value]

    async def execute_read(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Record the read and return the next canned response."""
        del timeout
        self.read_calls.append((query, parameters))
        if self._reads:
            return self._reads.pop(0)
        return []

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Record the write and return the routed canned response."""
        self.write_calls.append((query, parameters))
        for marker, response in self._writes.items():
            if marker in query:
                return response
        return []

    async def setup_constraints(self) -> None:
        """No-op constraint setup."""
        return

    async def setup_indexes(self) -> None:
        """No-op index setup."""
        return

    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
    ) -> UpsertResult:
        """Report every node written."""
        return UpsertResult(written=len(nodes))

    async def upsert_relations(
        self,
        relations: Sequence[RelationRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
    ) -> UpsertResult:
        """Report every relation written."""
        return UpsertResult(written=len(relations))

    async def ensure_vector_index(
        self, *, label: str, vector_property: str, dimensions: int, distance: Distance
    ) -> None:
        """No-op vector index creation."""
        return

    async def vector_search(
        self,
        *,
        label: str,
        vector_property: str,
        query_vector: Sequence[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        """Return no hits."""
        return []

    async def register_labels(self, labels: Sequence[str]) -> None:
        """No-op label registration."""
        return

    async def register_relation_types(self, types: Sequence[str]) -> None:
        """No-op relation-type registration."""
        return


def _membership(
    entity_id: UUID, resolved_id: UUID, member_ids: list[UUID]
) -> dict[str, Any]:
    """Build one cluster-membership row for an orphan."""
    return {
        "entity_id": str(entity_id),
        "resolved_id": str(resolved_id),
        "member_ids": [str(member_id) for member_id in member_ids],
    }


def _deleted(entity_id: UUID) -> dict[str, Any]:
    """Build one entity-delete result row."""
    return {"entity_id": str(entity_id)}


class TestPruneOrphanedEntities:
    """prune_orphaned_entities deletes orphans and rebuilds clusters."""

    async def test_rebuilds_over_remaining_pair(self) -> None:
        """Two survivors form a new cluster replacing the old one."""
        first, second, third, cluster = (uuid4() for _ in range(4))
        members = [first, second, third]
        store = _ScriptedStore(
            reads=[
                [],
                [_membership(first, cluster, members)],
                [
                    {"n": _node(second, "Beta")},
                    {"n": _node(third, "Gamma")},
                ],
            ],
            writes={
                "DETACH DELETE entity": [_deleted(first)],
                "removed_resolved_entity_ids": [
                    {"removed_resolved_entity_ids": [str(cluster)]}
                ],
            },
        )

        result = await prune_orphaned_entities(
            [first], graph_store=store, schema=_schema()
        )

        assert result.removed_entity_ids == [first]
        assert result.removed_resolved_entity_ids == [cluster]
        assert len(result.rebuilt_entities) == 1
        assert result.rebuilt_entities[0].member_ids == sorted([second, third], key=str)
        rebuild_calls = [
            parameters
            for query, parameters in store.write_calls
            if "$pending_job_id" in query and isinstance(parameters, dict)
        ]
        assert rebuild_calls == [
            {
                "member_ids": [str(second), str(third)],
                "pending_job_id": None,
            }
        ]
