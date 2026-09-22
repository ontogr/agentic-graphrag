"""Non-destructive match persistence and resolved-entity computation."""

from collections import defaultdict
from datetime import datetime
from uuid import NAMESPACE_OID, UUID, uuid5

from pydantic import BaseModel

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import RelationRecord, UpsertResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.resolved_entity import (
    RESOLVED_AS_RELATION,
    RESOLVED_ENTITY_LABEL,
    ResolvedEntity,
)
from agrag.cypher.resolution_read import (
    fetch_active_component_members_query,
    fetch_entities_with_open_evidence_query,
    fetch_entity_cluster_memberships_query,
    fetch_match_endpoints_query,
)
from agrag.cypher.resolution_write import (
    deactivate_match_query,
    delete_entities_query,
    delete_merge_aliases_for_entities_query,
    delete_resolved_entities_query,
    replace_component_materializations_query,
    upsert_matches_query,
)
from agrag.graphdb.base import GraphStore
from agrag.ingestion.merge import compute_merge
from agrag.ingestion.resolve.resolver import ResolvedMatch


class MatchDecision(BaseModel):
    """A confirmed non-exact entity match ready to persist."""

    entity_a_id: UUID
    entity_b_id: UUID
    comparator: str
    score: float | None = None
    reasoning: str | None = None
    decided_at: datetime


class MaterializationResult(BaseModel):
    """The derived entity created and prior derived ids it replaced."""

    resolved_entity: ResolvedEntity
    removed_entity_ids: list[UUID]


class DeactivationResult(BaseModel):
    """Materializations created after a match correction and stale ids removed."""

    resolved_entities: list[ResolvedEntity]
    removed_entity_ids: list[UUID]


class PruningResult(BaseModel):
    """Ids removed and clusters rebuilt by deletion-triggered pruning."""

    removed_entity_ids: list[UUID]
    removed_resolved_entity_ids: list[UUID]
    rematerialized_entities: list[ResolvedEntity]


def decisions_by_component(
    matches: list[ResolvedMatch], mention_to_entity: dict[int, UUID]
) -> list[list[MatchDecision]]:
    """Map resolution evidence to raw ids and group it by connected component."""
    decisions: list[MatchDecision] = []
    seen_match_ids: set[UUID] = set()
    for match in matches:
        left_id = mention_to_entity.get(match.left_index)
        right_id = mention_to_entity.get(match.right_index)
        if left_id is None or right_id is None or left_id == right_id:
            continue
        match_id = matches_id(left_id, right_id)
        if match_id in seen_match_ids:
            continue
        seen_match_ids.add(match_id)
        decisions.append(
            MatchDecision(
                entity_a_id=left_id,
                entity_b_id=right_id,
                comparator=match.comparator,
                score=match.score,
                reasoning=match.reasoning,
                decided_at=match.decided_at,
            )
        )

    return match_decision_components(decisions)


def match_decision_components(
    decisions: list[MatchDecision],
) -> list[list[MatchDecision]]:
    """Group persisted match decisions by their connected raw component."""
    parent: dict[UUID, UUID] = {}

    def find(entity_id: UUID) -> UUID:
        parent.setdefault(entity_id, entity_id)
        if parent[entity_id] != entity_id:
            parent[entity_id] = find(parent[entity_id])
        return parent[entity_id]

    for decision in decisions:
        left_root = find(decision.entity_a_id)
        right_root = find(decision.entity_b_id)
        if left_root != right_root:
            parent[right_root] = left_root

    components: dict[UUID, list[MatchDecision]] = defaultdict(list)
    for decision in decisions:
        components[find(decision.entity_a_id)].append(decision)
    ordered_components = sorted(
        components.values(),
        key=lambda component: min(
            str(entity_id)
            for decision in component
            for entity_id in (decision.entity_a_id, decision.entity_b_id)
        ),
    )
    return [
        sorted(
            component,
            key=lambda decision: str(
                matches_id(decision.entity_a_id, decision.entity_b_id)
            ),
        )
        for component in ordered_components
    ]


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


async def write_matches_and_materialize(
    decisions: list[MatchDecision],
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    members: list[Entity],
    pending_job_id: str | None = None,
) -> MaterializationResult:
    """Persist matches and materialize their supplied connected component.

    Callers fetch the bounded affected component before invoking this function.
    The resolved node is always recomputed from that current membership.

    Args:
        decisions: The confirmed matches to persist.
        graph_store: Where matches and materializations are written.
        schema: The schema the members belong to.
        members: The component members the resolved node is computed from.
        pending_job_id: The in-flight Cutover Job's id, tagging the match
            edges and materialized nodes until that job commits. None
            writes untagged, for callers outside a job.

    Raises:
        ValueError: No decisions are supplied, or a decision references a
            member outside the supplied component.
    """
    if not decisions:
        raise ValueError("At least one match decision is required")
    members = sorted(members, key=lambda member: str(member.id))
    member_ids = {member.id for member in members}
    if any(
        decision.entity_a_id not in member_ids or decision.entity_b_id not in member_ids
        for decision in decisions
    ):
        raise ValueError(
            "Every match decision must reference a supplied component member"
        )
    from agrag.common.data_models.graph_record import tag_pending  # noqa: PLC0415

    async with graph_store.transaction() as transaction:
        for decision in decisions:
            first_id, second_id = sorted(
                (decision.entity_a_id, decision.entity_b_id), key=str
            )
            match_rows = await transaction.execute_write(
                upsert_matches_query(),
                {
                    "entity_a_id": str(first_id),
                    "entity_b_id": str(second_id),
                    "match_id": str(matches_id(first_id, second_id)),
                    "comparator": decision.comparator,
                    "score": decision.score,
                    "reasoning": decision.reasoning,
                    "decided_at": decision.decided_at.isoformat(),
                    "pending_job_id": pending_job_id,
                },
            )
            if not match_rows:
                raise ValueError(
                    "Cannot materialize a match whose entities do not exist"
                )
        component_rows = await transaction.execute_read(
            fetch_active_component_members_query(),
            {
                "seed_ids": [str(member.id) for member in members],
                "job_id": pending_job_id,
            },
        )
        if component_rows:
            from agrag.ingestion._ingest_pipeline import (  # noqa: PLC0415
                _parse_entity_node,
            )

            persisted_members = {
                entity.id: entity
                for row in component_rows
                if (entity := _parse_entity_node(row.get("member"))) is not None
            }
            if persisted_members:
                members = sorted(
                    persisted_members.values(), key=lambda member: str(member.id)
                )
        resolved = await compute_resolved_entity(members, schema)
        removed_rows = await transaction.execute_write(
            replace_component_materializations_query(),
            {
                "member_ids": [str(member.id) for member in members],
                "pending_job_id": pending_job_id,
            },
        )
        removed_entity_ids = [
            UUID(str(entity_id))
            for row in removed_rows
            if isinstance(row, dict)
            for entity_id in row.get("removed_resolved_entity_ids", [])
        ]
        _raise_for_write_failure(
            await transaction.upsert_nodes(
                RESOLVED_ENTITY_LABEL,
                [tag_pending(resolved.to_node_record(), pending_job_id)],
            )
        )
        _raise_for_write_failure(
            await transaction.upsert_relations(
                [
                    tag_pending(
                        RelationRecord(
                            id=uuid5(
                                NAMESPACE_OID, f"RESOLVED_AS:{member.id}:{resolved.id}"
                            ),
                            type=RESOLVED_AS_RELATION,
                            start_id=member.id,
                            end_id=resolved.id,
                            properties={
                                "decided_at": max(
                                    decision.decided_at for decision in decisions
                                ).isoformat()
                            },
                        ),
                        pending_job_id,
                    )
                    for member in members
                ]
            )
        )
    return MaterializationResult(
        resolved_entity=resolved,
        removed_entity_ids=list(dict.fromkeys(removed_entity_ids)),
    )


async def deactivate_match_and_rematerialize(
    match_id: UUID, *, graph_store: GraphStore, schema: GraphSchema
) -> DeactivationResult:
    """Deactivate a match and return its replacements and deleted derived IDs."""
    from agrag.ingestion._ingest_pipeline import _parse_entity_node  # noqa: PLC0415

    async with graph_store.transaction() as transaction:
        endpoint_rows = await transaction.execute_read(
            fetch_match_endpoints_query(), {"match_id": str(match_id)}
        )
        if not endpoint_rows:
            raise ValueError(f"Match {match_id} does not exist")
        endpoints: list[UUID] = []
        for row in endpoint_rows:
            for key in ("a", "b"):
                entity = _parse_entity_node(row.get(key))
                if entity is not None:
                    endpoints.append(entity.id)
        if len(set(endpoints)) != 2:
            raise ValueError(f"Match {match_id} has invalid endpoints")
        if not await transaction.execute_write(
            deactivate_match_query(), {"match_id": str(match_id)}
        ):
            raise ValueError(f"Match {match_id} does not exist")
        component_rows = await transaction.execute_read(
            fetch_active_component_members_query(),
            {
                "seed_ids": [str(endpoint_id) for endpoint_id in endpoints],
                "job_id": None,
            },
        )
        by_seed: dict[str, list[Entity]] = defaultdict(list)
        for row in component_rows:
            entity = _parse_entity_node(row.get("member"))
            if entity is not None:
                by_seed[str(row["seed_id"])].append(entity)
        components = {
            frozenset(member.id for member in members): members
            for members in by_seed.values()
        }
        all_member_ids = sorted(
            {member.id for members in components.values() for member in members},
            key=str,
        )
        replacement_rows = await transaction.execute_write(
            replace_component_materializations_query(),
            {
                "member_ids": [str(member_id) for member_id in all_member_ids],
                "pending_job_id": None,
            },
        )
        removed_entity_ids = [
            UUID(str(entity_id))
            for row in replacement_rows
            if isinstance(row, dict)
            for entity_id in row.get("removed_resolved_entity_ids", [])
        ]
        materialized: list[ResolvedEntity] = []
        for members in sorted(
            components.values(),
            key=lambda component: min(str(member.id) for member in component),
        ):
            if len(members) < 2:
                continue
            resolved = await compute_resolved_entity(members, schema)
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
                                NAMESPACE_OID,
                                f"RESOLVED_AS:{member.id}:{resolved.id}",
                            ),
                            type=RESOLVED_AS_RELATION,
                            start_id=member.id,
                            end_id=resolved.id,
                            properties={},
                        )
                        for member in sorted(members, key=lambda member: str(member.id))
                    ]
                )
            )
            materialized.append(resolved)
    materialized_ids = {entity.id for entity in materialized}
    return DeactivationResult(
        resolved_entities=materialized,
        removed_entity_ids=[
            entity_id
            for entity_id in dict.fromkeys(removed_entity_ids)
            if entity_id not in materialized_ids
        ],
    )


def _uuid_list(rows: object, key: str) -> list[UUID]:
    """Parse string ids out of graph-store rows, skipping unreadable ones."""
    parsed: list[UUID] = []
    if not isinstance(rows, list):
        return parsed
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = row.get(key)
        if isinstance(value, list):
            for item in value:
                try:
                    parsed.append(UUID(str(item)))
                except ValueError:
                    continue
        elif value is not None:
            try:
                parsed.append(UUID(str(value)))
            except ValueError:
                continue
    return parsed


async def prune_orphaned_entities(
    candidate_entity_ids: list[UUID], *, graph_store: GraphStore, schema: GraphSchema
) -> PruningResult:
    """Delete candidates with no open-chunk evidence and rebuild clusters.

    A candidate mentioned by any chunk with an open PART_OF edge keeps its
    node. Any other candidate loses its node with its incident MENTIONED_IN
    and RESOLVED_AS edges; each affected cluster is then recomputed over
    its remaining members, or deleted when fewer than two remain and the
    survivor returns to plain status. Merge aliases owned by removed
    entities are deleted too, so re-ingesting a pruned name starts clean
    instead of colliding with an alias pointing at a missing node.

    Only the supplied candidates are ever deleted. Evidence is checked per
    candidate id, never with a graph-wide scan.
    """
    from agrag.cypher.entities import hydrate_entities_by_id_query  # noqa: PLC0415
    from agrag.ingestion._ingest_pipeline import _parse_entity_node  # noqa: PLC0415

    unique_ids = list(dict.fromkeys(candidate_entity_ids))
    empty = PruningResult(
        removed_entity_ids=[],
        removed_resolved_entity_ids=[],
        rematerialized_entities=[],
    )
    if not unique_ids:
        return empty
    evidenced_rows = await graph_store.execute_read(
        fetch_entities_with_open_evidence_query(),
        {"ids": [str(entity_id) for entity_id in unique_ids], "job_id": None},
    )
    evidenced = set(_uuid_list(evidenced_rows, "id"))
    orphans = [entity_id for entity_id in unique_ids if entity_id not in evidenced]
    if not orphans:
        return empty
    membership_rows = await graph_store.execute_read(
        fetch_entity_cluster_memberships_query(),
        {"ids": [str(entity_id) for entity_id in orphans], "job_id": None},
    )
    clusters: dict[str, list[str]] = {}
    if isinstance(membership_rows, list):
        for row in membership_rows:
            if not isinstance(row, dict):
                continue
            resolved_id = row.get("resolved_id")
            member_ids = row.get("member_ids") or []
            if resolved_id is not None and isinstance(member_ids, list):
                clusters.setdefault(str(resolved_id), [str(m) for m in member_ids])
    deleted_rows = await graph_store.execute_write(
        delete_entities_query(), {"ids": [str(entity_id) for entity_id in orphans]}
    )
    removed_entity_ids = _uuid_list(deleted_rows, "entity_id")
    await graph_store.execute_write(
        delete_merge_aliases_for_entities_query(),
        {"ids": [str(entity_id) for entity_id in removed_entity_ids]},
    )
    removed_set = {str(entity_id) for entity_id in removed_entity_ids}
    removed_resolved_entity_ids: list[UUID] = []
    rematerialized: list[ResolvedEntity] = []
    for resolved_id, member_ids in clusters.items():
        remaining_ids = [m for m in dict.fromkeys(member_ids) if m not in removed_set]
        hydrate_rows = (
            await graph_store.execute_read(
                hydrate_entities_by_id_query(), {"ids": remaining_ids, "job_id": None}
            )
            if remaining_ids
            else []
        )
        members = [
            entity
            for row in hydrate_rows
            if (
                entity := _parse_entity_node(
                    row.get("member", row.get("n", row))
                    if isinstance(row, dict)
                    else row
                )
            )
            is not None
        ]
        if len(members) >= 2:
            async with graph_store.transaction() as transaction:
                replacement_rows = await transaction.execute_write(
                    replace_component_materializations_query(),
                    {"member_ids": [str(member.id) for member in members]},
                )
                removed_resolved_entity_ids.extend(
                    _uuid_list(replacement_rows, "removed_resolved_entity_ids")
                )
                resolved = await compute_resolved_entity(members, schema)
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
                                    NAMESPACE_OID,
                                    f"RESOLVED_AS:{member.id}:{resolved.id}",
                                ),
                                type=RESOLVED_AS_RELATION,
                                start_id=member.id,
                                end_id=resolved.id,
                                properties={},
                            )
                            for member in sorted(members, key=lambda m: str(m.id))
                        ]
                    )
                )
            rematerialized.append(resolved)
        elif len(members) == 1:
            async with graph_store.transaction() as transaction:
                replacement_rows = await transaction.execute_write(
                    replace_component_materializations_query(),
                    {"member_ids": [str(members[0].id)]},
                )
                removed_resolved_entity_ids.extend(
                    _uuid_list(replacement_rows, "removed_resolved_entity_ids")
                )
        else:
            pruned_rows = await graph_store.execute_write(
                delete_resolved_entities_query(), {"ids": [resolved_id]}
            )
            removed_resolved_entity_ids.extend(_uuid_list(pruned_rows, "resolved_id"))
    return PruningResult(
        removed_entity_ids=removed_entity_ids,
        removed_resolved_entity_ids=list(dict.fromkeys(removed_resolved_entity_ids)),
        rematerialized_entities=rematerialized,
    )
