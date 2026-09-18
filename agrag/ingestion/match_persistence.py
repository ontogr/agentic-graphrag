"""Transactional persistence for semantic matches and resolved components."""

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID, uuid5

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import RelationRecord, UpsertResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.cypher.resolution import (
    active_component_query,
    delete_component_materializations_query,
)
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.ingestion.match_decision import MatchDecision
from agrag.ingestion.materialize import materialize_component


def _require_success(result: UpsertResult | None, *, operation: str) -> None:
    """Raise when a graph bulk operation did not write every requested record."""
    if result is not None and result.failures:
        failures = "; ".join(
            f"{failure.id}: {failure.error_message}" for failure in result.failures
        )
        raise RuntimeError(f"{operation} failed: {failures}")


def _node_properties(node: object) -> dict[str, Any]:
    """Extract property dictionaries from supported graph-store node representations."""
    if isinstance(node, dict):
        properties = node.get("properties")
        return dict(properties) if isinstance(properties, dict) else dict(node)
    if isinstance(node, Mapping):
        return dict(node)
    raise ValueError("A graph component member has no readable properties.")


def _entity_from_node(node: object) -> Entity:
    """Build a raw entity from the graph record returned for a component member."""
    properties = _node_properties(node)
    raw_id = properties.get("id")
    merge_key = properties.get("merge_key")
    if raw_id is None or not isinstance(merge_key, str) or ":" not in merge_key:
        raise ValueError("A match component member is not a valid raw Entity.")
    label, _ = merge_key.split(":", 1)
    system_fields = {
        "id",
        "name",
        "merge_key",
        "merged_from",
        "merge_count",
        "source_chunk_ids",
        "created_at",
        "embedding",
    }
    created_at = properties.get("created_at")
    entity_kwargs: dict[str, Any] = {
        "id": UUID(str(raw_id)),
        "label": label,
        "name": str(properties["name"]),
        "properties": {
            key: value for key, value in properties.items() if key not in system_fields
        },
        "merge_count": int(properties.get("merge_count", 1)),
        "source_chunk_ids": [
            UUID(str(value)) for value in properties.get("source_chunk_ids", [])
        ],
    }
    if isinstance(created_at, str):
        entity_kwargs["created_at"] = datetime.fromisoformat(created_at)
    return Entity(
        **entity_kwargs,
    )


def _match_record(decision: MatchDecision) -> RelationRecord:
    """Convert a decision into the persistent active MATCHES relationship."""
    return RelationRecord(
        id=decision.id,
        type="MATCHES",
        start_id=decision.left_entity_id,
        end_id=decision.right_entity_id,
        properties={
            "active": decision.active,
            "comparator": decision.comparator,
            "score": decision.score,
            "reasoning": decision.reasoning,
            "decided_at": decision.decided_at.isoformat(),
        },
    )


def _membership_records(resolved: ResolvedEntity) -> list[RelationRecord]:
    """Build deterministic raw-member to resolved-component relationships."""
    return [
        RelationRecord(
            id=uuid5(resolved.id, f"resolved_as:{member_id}"),
            type="RESOLVED_AS",
            start_id=member_id,
            end_id=resolved.id,
            properties={},
        )
        for member_id in resolved.member_ids
    ]


async def _component_members(
    transaction: GraphStoreTransaction, seed_ids: Iterable[UUID]
) -> list[Entity]:
    """Load and canonicalize the active raw component for supplied match endpoints."""
    rows = await transaction.execute_read(
        active_component_query(), {"seed_ids": [str(seed_id) for seed_id in seed_ids]}
    )
    members = [_entity_from_node(row.get("member", row)) for row in rows]
    unique = {member.id: member for member in members}
    return sorted(unique.values(), key=lambda member: str(member.id))


async def write_match_and_materialize(
    decisions: list[MatchDecision], *, graph_store: GraphStore, schema: GraphSchema
) -> list[ResolvedEntity]:
    """Atomically persist semantic edges and rematerialize their active components.

    Raises:
        RuntimeError: Any per-record graph upsert reports a failure.
        ValueError: A graph component cannot be parsed as raw entities.
    """
    unique_decisions = {decision.id: decision for decision in decisions}
    ordered_decisions = [
        unique_decisions[decision_id]
        for decision_id in sorted(unique_decisions, key=str)
    ]
    if not ordered_decisions:
        return []

    async with graph_store.transaction() as transaction:
        _require_success(
            await transaction.upsert_relations(
                [_match_record(decision) for decision in ordered_decisions]
            ),
            operation="MATCHES upsert",
        )
        components: dict[tuple[UUID, ...], list[Entity]] = {}
        for decision in ordered_decisions:
            members = await _component_members(
                transaction, (decision.left_entity_id, decision.right_entity_id)
            )
            if len(members) >= 2:
                components[tuple(member.id for member in members)] = members

        resolved_entities: list[ResolvedEntity] = []
        ordered_components = sorted(components.items(), key=lambda item: str(item[0]))
        for member_ids, members in ordered_components:
            await transaction.execute_write(
                delete_component_materializations_query(),
                {"member_ids": [str(member_id) for member_id in member_ids]},
            )
            resolved = await materialize_component(members, schema=schema)
            _require_success(
                await transaction.upsert_nodes(
                    "ResolvedEntity", [resolved.to_node_record()]
                ),
                operation="ResolvedEntity upsert",
            )
            _require_success(
                await transaction.upsert_relations(_membership_records(resolved)),
                operation="RESOLVED_AS upsert",
            )
            resolved_entities.append(resolved)
    return resolved_entities
