"""Tests for Graph.reevaluate() over a scripted GraphStore.

The real zone-routed Resolver runs against a one-hot fake embedder, so
no LLM or network is involved: names sharing a vector merge in the
embedding tier, orthogonal names are discarded, and identical names meet
as exact-text pairs. Active MATCHES edges come from canned reads, and
the real materialize functions persist through the fake's transaction.
"""

from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.graph_record import (
    NodeRecord,
    RelationRecord,
    UpsertResult,
)
from agrag.common.data_models.graph_schema import GENERIC
from agrag.common.data_models.vector_record import Distance, VectorHit
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion import Graph


_A_NAME = "Alpha Meridian"
_B_NAME = "Beta Meridian"
_C_NAME = "Gamma Delta"
_D_NAME = "Epsilon Zeta"
_E_NAME = "Theta Iota"
_F_NAME = "Kappa Kappa"

_VECTORS = {
    _A_NAME: [1.0, 0.0, 0.0, 0.0, 0.0],
    _B_NAME: [1.0, 0.0, 0.0, 0.0, 0.0],
    _C_NAME: [0.0, 1.0, 0.0, 0.0, 0.0],
    _D_NAME: [0.0, 0.0, 1.0, 0.0, 0.0],
    _E_NAME: [0.0, 0.0, 0.0, 1.0, 0.0],
    _F_NAME: [0.0, 0.0, 0.0, 0.0, 1.0],
}
_FALLBACK_VECTOR = [0.0, 0.0, 0.0, 0.0, 1.0]


def _node(entity_id: UUID, name: str) -> dict[str, Any]:
    """Build a flat entity node row the pipeline parser accepts."""
    return {"id": str(entity_id), "labels": ["Person"], "name": name}


class _ScriptedStore(GraphStore):
    """GraphStore serving canned reads and routing writes by query text."""

    def __init__(self, reads: list[list[dict[str, Any]]]) -> None:
        """Queue canned read responses and start empty call logs."""
        self._reads = list(reads)
        self.read_calls: list[tuple[str, Any]] = []
        self.write_calls: list[tuple[str, Any]] = []
        self.upserted_nodes: list[tuple[str, list[NodeRecord]]] = []
        self.upserted_relations: list[list[RelationRecord]] = []

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
        """Record the write and return a canned success row."""
        self.write_calls.append((query, parameters))
        if "SET r.active = false" in query:
            return [{"r": 1}]
        if "MERGE (a)-[r:MATCHES" in query:
            return [{"id": "match"}]
        if "removed_resolved_entity_ids" in query:
            return [{"removed_resolved_entity_ids": []}]
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
        """Record a node upsert."""
        self.upserted_nodes.append((label, list(nodes)))
        return UpsertResult(written=len(nodes))

    async def upsert_relations(
        self, relations: Sequence[RelationRecord], *, batch_size: int = 256
    ) -> UpsertResult:
        """Record a relation upsert."""
        self.upserted_relations.append(list(relations))
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


class _OneHotEmbedder(Embedder):
    """Embedder mapping each known name to a fixed one-hot vector."""

    model = "one-hot"

    async def dimensions(self) -> int:
        """Return the fixed one-hot dimension."""
        return 5

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return each text's vector, falling back for resolved names."""
        return [list(_VECTORS.get(text, _FALLBACK_VECTOR)) for text in texts]


def _hydrate_rows(names: dict[UUID, str]) -> list[dict[str, Any]]:
    """Build hydrate-by-id rows for the given entity names."""
    return [{"n": _node(entity_id, name)} for entity_id, name in names.items()]


def _edge_row(match_id: UUID, first: UUID, second: UUID) -> dict[str, Any]:
    """Build one active-match edge row."""
    return {"match_id": str(match_id), "a_id": str(first), "b_id": str(second)}


def _graph(store: _ScriptedStore) -> Graph:
    """Build a Graph over the scripted store and one-hot embedder."""
    return Graph(
        schema=GENERIC,
        graph_store=store,
        embedder=_OneHotEmbedder(),
        extractor=MagicMock(),
    )


class TestGraphReevaluate:
    """Graph.reevaluate() adds, removes, and leaves edges alone."""

    async def test_adds_confirmed_removes_stale_and_counts_unchanged(self) -> None:
        """One batch reports an addition, a removal, and three unchanged."""
        first, second, third, fourth, fifth, sixth, seventh = (
            uuid4() for _ in range(7)
        )
        stale_match = uuid4()
        kept_match = uuid4()
        names = {
            first: _A_NAME,
            second: _B_NAME,
            third: _C_NAME,
            fourth: _D_NAME,
            fifth: _E_NAME,
            sixth: _F_NAME,
            seventh: _F_NAME,
        }
        store = _ScriptedStore(
            reads=[
                _hydrate_rows(names),
                [
                    _edge_row(stale_match, third, fourth),
                    _edge_row(kept_match, sixth, seventh),
                ],
                [],
                [{"a": _node(third, _C_NAME), "b": _node(fourth, _D_NAME)}],
                [
                    {"seed_id": str(third), "member": _node(third, _C_NAME)},
                    {"seed_id": str(fourth), "member": _node(fourth, _D_NAME)},
                ],
                [],
            ]
        )

        report = await _graph(store).reevaluate(
            [first, second, third, fourth, fifth, sixth, seventh]
        )

        assert report.entities_reevaluated == [
            first,
            second,
            third,
            fourth,
            fifth,
            sixth,
            seventh,
        ]
        assert len(report.matches_added) == 1
        added = report.matches_added[0]
        assert {added.entity_a_id, added.entity_b_id} == {first, second}
        assert added.comparator == "embedding"
        assert report.matches_removed == [stale_match]
        assert report.unchanged_count == 3
        deactivated = [
            params
            for query, params in store.write_calls
            if "SET r.active = false" in query
        ]
        assert len(deactivated) == 1
        assert all(
            isinstance(params, dict) and params.get("match_id") != str(kept_match)
            for params in deactivated
        )

    async def test_raises_for_unknown_id(self) -> None:
        """An id with no live persisted entity raises ValueError."""
        known, unknown = uuid4(), uuid4()
        store = _ScriptedStore(reads=[_hydrate_rows({known: _C_NAME})])

        with pytest.raises(ValueError, match="Unknown entity"):
            await _graph(store).reevaluate([known, unknown])

    async def test_returns_empty_report_for_empty_input(self) -> None:
        """An empty input makes no store calls and reports nothing."""
        store = _ScriptedStore(reads=[])

        report = await _graph(store).reevaluate([])

        assert report.entities_reevaluated == []
        assert report.matches_added == []
        assert report.matches_removed == []
        assert report.unchanged_count == 0
        assert store.read_calls == []
        assert store.write_calls == []
