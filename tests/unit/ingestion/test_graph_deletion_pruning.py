"""Tests for deletion-triggered pruning and its document wiring.

prune_orphaned_entities runs against a scripted GraphStore: candidates
with open-chunk evidence keep their nodes, orphans lose theirs, and
each affected cluster is rebuilt over its survivors or deleted. The
wiring tests prove the no-op document paths never reach pruning.
"""

import hashlib
import unicodedata
from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from agrag.common.data_models.graph_record import (
    NodeRecord,
    RelationRecord,
    UpsertResult,
)
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.vector_record import Distance, VectorHit
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion import Graph
from agrag.ingestion.materialize import prune_orphaned_entities


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
    return {"id": str(entity_id), "labels": ["Person"], "name": name}


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
        self, label: str, nodes: Sequence[NodeRecord], *, batch_size: int = 256
    ) -> UpsertResult:
        """Report every node written."""
        return UpsertResult(written=len(nodes))

    async def upsert_relations(
        self, relations: Sequence[RelationRecord], *, batch_size: int = 256
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


class _FixedEmbedder(Embedder):
    """Embedder returning a constant vector."""

    model = "fixed"

    async def dimensions(self) -> int:
        """Return a small fixed dimension."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector for every text."""
        return [[0.1] * 4 for _ in texts]


def _evidence(entity_id: UUID) -> dict[str, Any]:
    """Build one open-evidence row for an entity."""
    return {"id": str(entity_id)}


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


def _delete_params(store: _ScriptedStore) -> list[Any]:
    """Return the id lists of every entity-delete write."""
    return [
        params.get("ids")
        for query, params in store.write_calls
        if "DETACH DELETE entity" in query and isinstance(params, dict)
    ]


class TestPruneOrphanedEntities:
    """prune_orphaned_entities deletes orphans and rebuilds clusters."""

    async def test_shrink_to_zero_prunes_cluster(self) -> None:
        """Orphaning every member deletes the nodes and the cluster."""
        first, second, third, cluster = (uuid4() for _ in range(4))
        members = [first, second, third]
        store = _ScriptedStore(
            reads=[
                [],
                [_membership(member, cluster, members) for member in members],
            ],
            writes={
                "DETACH DELETE entity": [_deleted(member) for member in members],
                "DETACH DELETE resolved": [{"resolved_id": str(cluster)}],
            },
        )

        result = await prune_orphaned_entities(
            members, graph_store=store, schema=_schema()
        )

        assert result.removed_entity_ids == members
        assert result.removed_resolved_entity_ids == [cluster]
        assert result.rematerialized_entities == []
        assert _delete_params(store) == [[str(member) for member in members]]
        alias_deletes = [
            params.get("ids")
            for query, params in store.write_calls
            if "DETACH DELETE alias" in query and isinstance(params, dict)
        ]
        assert alias_deletes == [[str(member) for member in members]]

    async def test_shrink_to_one_prunes_to_singleton(self) -> None:
        """One survivor keeps its node while the cluster node goes away."""
        first, second, third, cluster = (uuid4() for _ in range(4))
        members = [first, second, third]
        store = _ScriptedStore(
            reads=[
                [_evidence(second)],
                [
                    _membership(first, cluster, members),
                    _membership(third, cluster, members),
                ],
                [{"n": _node(second, "Beta")}],
            ],
            writes={
                "DETACH DELETE entity": [_deleted(first), _deleted(third)],
                "removed_resolved_entity_ids": [
                    {"removed_resolved_entity_ids": [str(cluster)]}
                ],
            },
        )

        result = await prune_orphaned_entities(
            members, graph_store=store, schema=_schema()
        )

        assert result.removed_entity_ids == [first, third]
        assert result.removed_resolved_entity_ids == [cluster]
        assert result.rematerialized_entities == []
        materialization_calls = [
            parameters
            for query, parameters in store.write_calls
            if "$pending_job_id" in query and isinstance(parameters, dict)
        ]
        assert materialization_calls == [
            {"member_ids": [str(second)], "pending_job_id": None}
        ]
        for deleted_ids in _delete_params(store):
            assert str(second) not in deleted_ids

    async def test_rematerializes_over_remaining_pair(self) -> None:
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
        assert len(result.rematerialized_entities) == 1
        assert result.rematerialized_entities[0].member_ids == sorted(
            [second, third], key=str
        )
        materialization_calls = [
            parameters
            for query, parameters in store.write_calls
            if "$pending_job_id" in query and isinstance(parameters, dict)
        ]
        assert materialization_calls == [
            {
                "member_ids": [str(second), str(third)],
                "pending_job_id": None,
            }
        ]

    async def test_evidenced_candidate_is_a_no_op(self) -> None:
        """A candidate with open evidence triggers no writes at all."""
        member = uuid4()
        store = _ScriptedStore(reads=[[_evidence(member)]], writes={})

        result = await prune_orphaned_entities(
            [member], graph_store=store, schema=_schema()
        )

        assert result.removed_entity_ids == []
        assert result.removed_resolved_entity_ids == []
        assert result.rematerialized_entities == []
        assert store.write_calls == []


class TestDeletionPruningWiring:
    """No-op document paths never reach pruning."""

    def _graph(self, store: _ScriptedStore) -> Graph:
        """Build a Graph over the scripted store."""
        return Graph(
            schema=_schema(),
            graph_store=store,
            embedder=_FixedEmbedder(),
            extractor=MagicMock(),
        )

    async def test_delete_unknown_document_skips_pruning(self) -> None:
        """An unknown document key performs no reads beyond the lookup."""
        store = _ScriptedStore(reads=[[]], writes={})

        result = await self._graph(store).delete_document("missing")

        assert result.no_op is True
        assert len(store.read_calls) == 1
        assert store.write_calls == []

    async def test_update_no_op_skips_pruning(self) -> None:
        """Unchanged content returns before any pruning read."""
        text = "unchanged content. " * 20
        content_hash = hashlib.sha256(
            unicodedata.normalize("NFKC", text).encode("utf-8")
        ).hexdigest()
        store = _ScriptedStore(
            reads=[[{"id": str(uuid4()), "current_content_hash": content_hash}]],
            writes={},
        )

        result = await self._graph(store).update("key", text=text)

        assert result.no_op is True
        assert len(store.read_calls) == 1
        assert store.write_calls == []
