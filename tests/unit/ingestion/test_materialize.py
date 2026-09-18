"""Tests for non-destructive entity-resolution materialization."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import UpsertFailure, UpsertResult
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.ingestion.materialize import (
    MatchDecision,
    compute_resolved_entity,
    matches_id,
    write_matches_and_materialize,
)


def _schema() -> GraphSchema:
    """Build a minimal entity schema."""
    return GraphSchema(
        name="test",
        version="1",
        entities=[EntityType(label="Person", description="", properties={})],
        relations=[],
    )


def _entity(name: str, entity_id=None) -> Entity:
    """Build a persisted test entity."""
    return Entity(
        id=entity_id or uuid4(),
        created_at=datetime.now(UTC),
        label="Person",
        name=name,
    )


class TestMatchesId:
    """Deterministic MATCHES relationship identifiers."""

    def test_is_order_independent(self) -> None:
        """Both endpoint orders produce the same identifier."""
        first, second = uuid4(), uuid4()
        assert matches_id(first, second) == matches_id(second, first)


class TestComputeResolvedEntity:
    """Pure resolved-entity materialization."""

    async def test_is_order_independent(self) -> None:
        """Member order does not affect cluster identity or membership."""
        first, second = _entity("Ada"), _entity("Ada Lovelace")
        forward = await compute_resolved_entity([first, second], _schema())
        reverse = await compute_resolved_entity([second, first], _schema())
        assert forward.id == reverse.id
        assert forward.member_ids == reverse.member_ids

    async def test_rejects_singleton_membership(self) -> None:
        """A materialized cluster must have at least two members."""
        with pytest.raises(ValueError, match="at least two"):
            await compute_resolved_entity([_entity("Ada")], _schema())


def _store(
    *,
    node_result: UpsertResult | None = None,
    relation_result: UpsertResult | None = None,
) -> SimpleNamespace:
    """Build a transaction-capable graph-store test double."""
    transaction = SimpleNamespace(
        execute_write=AsyncMock(return_value=[{"id": "match"}]),
        upsert_nodes=AsyncMock(return_value=node_result),
        upsert_relations=AsyncMock(return_value=relation_result),
    )

    @asynccontextmanager
    async def open_transaction():
        yield transaction

    return SimpleNamespace(
        transaction=open_transaction, current_transaction=transaction
    )


class TestWriteMatchesAndMaterialize:
    """Match materialization uses one atomic graph transaction."""

    async def test_replaces_existing_component_materialization(self) -> None:
        """A match writes its edge and replacement membership in one transaction."""
        first, second = _entity("Ada"), _entity("Ada Lovelace")
        store = _store(
            node_result=UpsertResult(written=1), relation_result=UpsertResult(written=2)
        )
        decision = MatchDecision(
            entity_a_id=first.id,
            entity_b_id=second.id,
            comparator="FuzzyMatch",
            decided_at=datetime.now(UTC),
        )

        resolved = await write_matches_and_materialize(
            [decision], graph_store=store, schema=_schema(), members=[second, first]
        )

        assert resolved.member_ids == sorted([first.id, second.id], key=str)
        assert store.current_transaction.execute_write.await_count == 2
        store.current_transaction.upsert_nodes.assert_awaited_once()
        store.current_transaction.upsert_relations.assert_awaited_once()

    async def test_raises_when_a_bulk_write_reports_failure(self) -> None:
        """A failed membership write prevents a partial materialization result."""
        first, second = _entity("Ada"), _entity("Ada Lovelace")
        store = _store(
            node_result=UpsertResult(written=1),
            relation_result=UpsertResult(
                written=1,
                failures=[
                    UpsertFailure(
                        id="failed", error_type="WriteError", error_message="failed"
                    )
                ],
            ),
        )
        decision = MatchDecision(
            entity_a_id=first.id,
            entity_b_id=second.id,
            comparator="FuzzyMatch",
            decided_at=datetime.now(UTC),
        )

        with pytest.raises(RuntimeError, match="failed"):
            await write_matches_and_materialize(
                [decision], graph_store=store, schema=_schema(), members=[first, second]
            )

    async def test_canonicalizes_reverse_order_match_writes(self) -> None:
        """A reverse-order repeat preserves one canonical edge direction."""
        first, second = sorted(
            (_entity("Ada"), _entity("Ada Lovelace")), key=lambda e: str(e.id)
        )
        store = _store(
            node_result=UpsertResult(written=1), relation_result=UpsertResult(written=2)
        )
        decision = MatchDecision(
            entity_a_id=second.id,
            entity_b_id=first.id,
            comparator="FuzzyMatch",
            decided_at=datetime.now(UTC),
        )

        await write_matches_and_materialize(
            [decision], graph_store=store, schema=_schema(), members=[first, second]
        )

        match_parameters = store.current_transaction.execute_write.call_args_list[
            0
        ].args[1]
        assert match_parameters["entity_a_id"] == str(first.id)
        assert match_parameters["entity_b_id"] == str(second.id)

    async def test_rejects_decisions_outside_the_component(self) -> None:
        """A write cannot create a match to a member it did not rematerialize."""
        first, second, outside = (
            _entity("Ada"),
            _entity("Ada Lovelace"),
            _entity("Grace"),
        )
        store = _store()
        decision = MatchDecision(
            entity_a_id=first.id,
            entity_b_id=outside.id,
            comparator="FuzzyMatch",
            decided_at=datetime.now(UTC),
        )

        with pytest.raises(ValueError, match="supplied component"):
            await write_matches_and_materialize(
                [decision], graph_store=store, schema=_schema(), members=[first, second]
            )
