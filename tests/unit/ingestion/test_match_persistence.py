"""Regression coverage for atomic semantic edge and component writes."""

from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import UpsertFailure, UpsertResult
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.ingestion.match_decision import MatchDecision
from agrag.ingestion.match_persistence import write_match_and_materialize


def _schema() -> GraphSchema:
    """Build the smallest schema needed to materialize people."""
    return GraphSchema(
        name="test",
        version="1",
        entities=[EntityType(label="Person", description="A person.")],
        relations=[],
    )


class _TransactionStore:
    """GraphStore-shaped fake that records a single transactional write sequence."""

    def __init__(self, members: list[Entity], failure_at: str | None = None) -> None:
        """Create a fake with component members and an optional failing write stage."""
        self._members = members
        self._failure_at = failure_at
        self.operations: list[str] = []
        self.rolled_back = False

    @asynccontextmanager
    async def transaction(self):
        """Model rollback when any write inside the transaction raises."""
        try:
            yield self
        except Exception:
            self.rolled_back = True
            raise

    async def execute_read(self, query: str, parameters: dict[str, object]):
        """Return raw component nodes in deliberately reversed order."""
        self.operations.append("read_component")
        return [
            {"member": {"id": str(member.id), **member.to_node_record().properties}}
            for member in reversed(self._members)
        ]

    async def execute_write(self, query: str, parameters: dict[str, object]):
        """Record removal of prior component materialization."""
        self.operations.append("delete_materialization")
        return []

    async def upsert_nodes(self, label: str, nodes: list[object]):
        """Record resolved node writes and optionally return an isolated failure."""
        self.operations.append("upsert_resolved")
        return self._result("upsert_resolved")

    async def upsert_relations(self, relations: list[object]):
        """Record edge and membership writes with optional isolated failure."""
        operation = "upsert_matches" if not self.operations else "upsert_memberships"
        self.operations.append(operation)
        return self._result(operation)

    def _result(self, operation: str) -> UpsertResult:
        """Return a success result unless this operation was configured to fail."""
        if self._failure_at == operation:
            return UpsertResult(
                failures=[
                    UpsertFailure(
                        id="failed",
                        error_type="WriteError",
                        error_message="write failed",
                    )
                ]
            )
        return UpsertResult(written=1)


class TestWriteMatchAndMaterialize:
    """Semantic materialization writes all graph records in one transaction."""

    async def test_materializes_canonical_component_after_match_write(self) -> None:
        """A direct match writes its edge, resolved node, and member links in order."""
        first = Entity(id=uuid4(), label="Person", name="Ada Lovelace")
        second = Entity(id=uuid4(), label="Person", name="A. Lovelace")
        store = _TransactionStore([first, second])
        decision = MatchDecision.create(
            left_entity_id=first.id,
            right_entity_id=second.id,
            comparator="FuzzyMatch",
            score=0.96,
        )

        resolved = await write_match_and_materialize(
            [decision], graph_store=store, schema=_schema()
        )

        assert [entity.member_ids for entity in resolved] == [
            sorted([first.id, second.id], key=str)
        ]
        assert store.operations == [
            "upsert_matches",
            "read_component",
            "delete_materialization",
            "upsert_resolved",
            "upsert_memberships",
        ]

    @pytest.mark.parametrize(
        "failure_at", ["upsert_matches", "upsert_resolved", "upsert_memberships"]
    )
    async def test_rolls_back_when_any_record_write_reports_failure(
        self, failure_at: str
    ) -> None:
        """An isolated graph upsert failure aborts the complete materialization."""
        first = Entity(id=uuid4(), label="Person", name="Ada Lovelace")
        second = Entity(id=uuid4(), label="Person", name="A. Lovelace")
        store = _TransactionStore([first, second], failure_at=failure_at)
        decision = MatchDecision.create(
            left_entity_id=first.id,
            right_entity_id=second.id,
            comparator="FuzzyMatch",
        )

        with pytest.raises(RuntimeError, match="failed"):
            await write_match_and_materialize(
                [decision], graph_store=store, schema=_schema()
            )

        assert store.rolled_back
