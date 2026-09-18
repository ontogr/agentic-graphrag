"""Non-destructive match persistence and resolved-entity computation."""

from datetime import datetime
from uuid import NAMESPACE_OID, UUID, uuid5

from pydantic import BaseModel

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import RelationRecord, UpsertResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.resolved_entity import (
    MATCHES_RELATION,
    RESOLVED_AS_RELATION,
    RESOLVED_ENTITY_LABEL,
    ResolvedEntity,
)
from agrag.cypher.resolution_write import (
    replace_component_materializations_query,
    upsert_matches_query,
)
from agrag.graphdb.base import GraphStore
from agrag.ingestion.merge import compute_merge


class MatchDecision(BaseModel):
    """A confirmed non-exact entity match ready to persist."""

    entity_a_id: UUID
    entity_b_id: UUID
    comparator: str
    score: float | None = None
    reasoning: str | None = None
    decided_at: datetime


def matches_id(entity_a_id: UUID, entity_b_id: UUID) -> UUID:
    """Return the order-independent deterministic id for an entity match."""
    first, second = sorted((entity_a_id, entity_b_id), key=str)
    return uuid5(NAMESPACE_OID, f"MATCHES:{first}:{second}")


async def compute_resolved_entity(
    members: list[Entity], schema: GraphSchema
) -> ResolvedEntity:
    """Compute a resolved entity from its current member data only."""
    if len(members) < 2:
        raise ValueError("A resolved entity requires at least two members")
    members = sorted(members, key=lambda member: str(member.id))
    labels = {member.label for member in members}
    if len(labels) != 1:
        raise ValueError("Resolved entity members must share a label")
    plan, _ = await compute_merge(
        existing_entities=members,
        mentions=[],
        schema=schema,
    )
    return ResolvedEntity(
        id=uuid5(
            NAMESPACE_OID,
            "RESOLVED:"
            + ":".join(sorted(map(str, labels)))
            + ":"
            + ":".join(sorted(str(member.id) for member in members)),
        ),
        label=plan.survivor.label,
        name=plan.survivor.name,
        properties=plan.survivor.properties,
        member_ids=sorted((member.id for member in members), key=str),
    )


def _raise_for_write_failure(result: UpsertResult | None) -> None:
    """Raise when a graph-store bulk write reports isolated failures."""
    if result is None or not result.failures:
        return
    failures = "; ".join(
        f"{failure.id}: {failure.error_message}" for failure in result.failures
    )
    raise RuntimeError(f"Could not materialize resolved entity: {failures}")


async def write_match_and_materialize(
    decision: MatchDecision,
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    members: list[Entity],
) -> ResolvedEntity:
    """Persist a match and materialize its supplied connected component.

    Callers fetch the bounded affected component before invoking this function.
    The resolved node is always recomputed from that current membership.
    """
    members = sorted(members, key=lambda member: str(member.id))
    resolved = await compute_resolved_entity(members, schema)
    match = RelationRecord(
        id=matches_id(decision.entity_a_id, decision.entity_b_id),
        type=MATCHES_RELATION,
        start_id=decision.entity_a_id,
        end_id=decision.entity_b_id,
        properties={
            "active": True,
            "comparator": decision.comparator,
            "score": decision.score,
            "reasoning": decision.reasoning,
            "decided_at": decision.decided_at.isoformat(),
        },
    )
    async with graph_store.transaction() as transaction:
        match_rows = await transaction.execute_write(
            upsert_matches_query(),
            {
                "entity_a_id": str(decision.entity_a_id),
                "entity_b_id": str(decision.entity_b_id),
                "match_id": str(match.id),
                "comparator": decision.comparator,
                "score": decision.score,
                "reasoning": decision.reasoning,
                "decided_at": decision.decided_at.isoformat(),
            },
        )
        if not match_rows:
            raise ValueError("Cannot materialize a match whose entities do not exist")
        await transaction.execute_write(
            replace_component_materializations_query(),
            {"member_ids": [str(member.id) for member in members]},
        )
        _raise_for_write_failure(
            await transaction.upsert_nodes(
                RESOLVED_ENTITY_LABEL, [resolved.to_node_record()]
            )
        )
        _raise_for_write_failure(
            await transaction.upsert_relations(
                [
                    RelationRecord(
                        id=uuid5(
                            NAMESPACE_OID, f"RESOLVED_AS:{member.id}:{resolved.id}"
                        ),
                        type=RESOLVED_AS_RELATION,
                        start_id=member.id,
                        end_id=resolved.id,
                        properties={"decided_at": decision.decided_at.isoformat()},
                    )
                    for member in members
                ]
            )
        )
    return resolved
