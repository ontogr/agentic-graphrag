"""Non-destructive match persistence and resolved-entity computation."""

from collections import defaultdict
from datetime import datetime
from uuid import NAMESPACE_OID, UUID, uuid5

from opentelemetry.trace import Tracer
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
    fetch_committed_component_decided_at_query,
    fetch_entities_with_open_evidence_query,
    fetch_entity_cluster_memberships_query,
    fetch_match_endpoints_query,
)
from agrag.cypher.resolution_write import (
    deactivate_match_query,
    delete_entities_query,
    delete_merge_aliases_for_entities_query,
    delete_resolved_entities_query,
    replace_component_resolved_entities_query,
    upsert_matches_query,
)
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.graphdb.entities import load_entities
from agrag.graphdb.serialize import parse_entity_node
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


MatchComponent = tuple[list[MatchDecision], list[Entity]]
"""One connected component: its match decisions and its raw member entities."""


class RebuildResult(BaseModel):
    """The derived entity created and prior derived ids it replaced."""

    resolved_entity: ResolvedEntity
    removed_entity_ids: list[UUID]


class DeactivationResult(BaseModel):
    """Resolved entities created after a match correction and stale ids removed."""

    resolved_entities: list[ResolvedEntity]
    removed_entity_ids: list[UUID]


class PruningResult(BaseModel):
    """Ids removed and clusters rebuilt by deletion-triggered pruning."""

    removed_entity_ids: list[UUID]
    removed_resolved_entity_ids: list[UUID]
    rebuilt_entities: list[ResolvedEntity]


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
    members: list[Entity],
    schema: GraphSchema,
    *,
    tracer: Tracer | None = None,
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
        tracer=tracer,
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
    raise RuntimeError(f"Could not rebuild resolved entity: {failures}")


async def write_matches_and_rebuild(
    decisions: list[MatchDecision],
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    members: list[Entity],
    pending_job_id: str | None = None,
    tracer: Tracer | None = None,
) -> RebuildResult:
    """Persist matches and rebuild their supplied connected component.

    Callers fetch the bounded affected component before invoking this function.
    The resolved node is always recomputed from that current membership.

    Args:
        decisions: The confirmed matches to persist.
        graph_store: Where matches and resolved entities are written.
        schema: The schema the members belong to.
        members: The component members the resolved node is computed from.
        pending_job_id: The in-flight Cutover Job's id, tagging the match
            edges and resolved entity nodes until that job commits. None
            writes untagged, for callers outside a job.
        tracer: Passed to description summarization.

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
                raise ValueError("Cannot rebuild a match whose entities do not exist")
        component_rows = await transaction.execute_read(
            fetch_active_component_members_query(),
            {
                "seed_ids": [str(member.id) for member in members],
                "job_id": pending_job_id,
            },
        )
        if component_rows:
            persisted_members = {
                entity.id: entity
                for row in component_rows
                if (entity := parse_entity_node(row.get("member"))) is not None
            }
            if persisted_members:
                members = sorted(
                    persisted_members.values(), key=lambda member: str(member.id)
                )
        return await _replace_resolved_entity(
            transaction,
            members,
            schema=schema,
            pending_job_id=pending_job_id,
            decided_at=max(decision.decided_at for decision in decisions),
            tracer=tracer,
        )


async def rebuild_resolved_entities(
    seed_ids: list[UUID],
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    tracer: Tracer | None = None,
) -> list[RebuildResult]:
    """Rebuild the resolved entity of each committed component from its seeds.

    The matches already exist, so no match decision is written or changed.
    The resolved nodes and their ``RESOLVED_AS`` memberships are rebuilt,
    each membership carrying the newest committed match time when one
    exists. Each component is read as it stands now, replacing whatever
    resolved entities its members belonged to. A seed whose entity is
    gone, or whose component has fewer than two members, is skipped:
    nothing is left to rebuild for it. Safe to run again on the same
    seeds.

    Args:
        seed_ids: One member id per component to rebuild. Seeds that share a
            component rebuild it once.
        graph_store: Where the components are read and rewritten.
        schema: The schema the members belong to.
        tracer: Passed to description summarization.

    Returns:
        One result per rebuilt component, in seed order.
    """
    results: list[RebuildResult] = []
    rebuilt_member_ids: set[UUID] = set()
    for seed_id in dict.fromkeys(seed_ids):
        if seed_id in rebuilt_member_ids:
            continue
        async with graph_store.transaction() as transaction:
            component_rows = await transaction.execute_read(
                fetch_active_component_members_query(),
                {"seed_ids": [str(seed_id)], "job_id": None},
            )
            members = sorted(
                {
                    entity.id: entity
                    for row in component_rows
                    if (entity := parse_entity_node(row.get("member"))) is not None
                }.values(),
                key=lambda member: str(member.id),
            )
            if len(members) < 2:
                continue
            decided_at_rows = await transaction.execute_read(
                fetch_committed_component_decided_at_query(),
                {"member_ids": [str(member.id) for member in members]},
            )
            decided_at_values = [
                datetime.fromisoformat(str(row["decided_at"]))
                for row in decided_at_rows
                if row.get("decided_at") is not None
            ]
            results.append(
                await _replace_resolved_entity(
                    transaction,
                    members,
                    schema=schema,
                    pending_job_id=None,
                    decided_at=max(decided_at_values, default=None),
                    tracer=tracer,
                )
            )
        rebuilt_member_ids.update(member.id for member in members)
    return results


async def _replace_resolved_entity(
    transaction: GraphStoreTransaction,
    members: list[Entity],
    *,
    schema: GraphSchema,
    pending_job_id: str | None,
    decided_at: datetime | None,
    tracer: Tracer | None,
) -> RebuildResult:
    """Replace the resolved entity of one component inside an open transaction.

    Args:
        transaction: The transaction the writes join.
        members: The component's current members.
        schema: The schema the members belong to.
        pending_job_id: The in-flight Cutover Job's id, or None outside a job.
        decided_at: When the newest match was decided, stored on each
            membership edge. None stores no timestamp.
        tracer: Passed to description summarization.

    Returns:
        The new resolved entity and the resolved ids it replaced.
    """
    from agrag.common.data_models.graph_record import tag_pending  # noqa: PLC0415

    resolved = await compute_resolved_entity(members, schema, tracer=tracer)
    removed_rows = await transaction.execute_write(
        replace_component_resolved_entities_query(),
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
                        properties=(
                            {}
                            if decided_at is None
                            else {"decided_at": decided_at.isoformat()}
                        ),
                    ),
                    pending_job_id,
                )
                for member in members
            ]
        )
    )
    return RebuildResult(
        resolved_entity=resolved,
        removed_entity_ids=list(dict.fromkeys(removed_entity_ids)),
    )


async def deactivate_match_and_rebuild(
    match_id: UUID,
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    tracer: Tracer | None = None,
) -> DeactivationResult:
    """Deactivate a match and return its replacements and deleted derived IDs."""
    async with graph_store.transaction() as transaction:
        endpoint_rows = await transaction.execute_read(
            fetch_match_endpoints_query(), {"match_id": str(match_id)}
        )
        if not endpoint_rows:
            raise ValueError(f"Match {match_id} does not exist")
        endpoints: list[UUID] = []
        for row in endpoint_rows:
            for key in ("a", "b"):
                entity = parse_entity_node(row.get(key))
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
            entity = parse_entity_node(row.get("member"))
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
            replace_component_resolved_entities_query(),
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
        rebuilt: list[ResolvedEntity] = []
        for members in sorted(
            components.values(),
            key=lambda component: min(str(member.id) for member in component),
        ):
            if len(members) < 2:
                continue
            resolved = await compute_resolved_entity(members, schema, tracer=tracer)
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
            rebuilt.append(resolved)
    rebuilt_ids = {entity.id for entity in rebuilt}
    return DeactivationResult(
        resolved_entities=rebuilt,
        removed_entity_ids=[
            entity_id
            for entity_id in dict.fromkeys(removed_entity_ids)
            if entity_id not in rebuilt_ids
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
    candidate_entity_ids: list[UUID],
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    tracer: Tracer | None = None,
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
    unique_ids = list(dict.fromkeys(candidate_entity_ids))
    empty = PruningResult(
        removed_entity_ids=[],
        removed_resolved_entity_ids=[],
        rebuilt_entities=[],
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
    rebuilt_resolved: list[ResolvedEntity] = []
    for resolved_id, member_ids in clusters.items():
        remaining_ids = [m for m in dict.fromkeys(member_ids) if m not in removed_set]
        members = list(
            (
                await load_entities(
                    graph_store, [UUID(m) for m in remaining_ids], tracer=tracer
                )
            ).values()
        )
        if len(members) >= 2:
            async with graph_store.transaction() as transaction:
                replacement_rows = await transaction.execute_write(
                    replace_component_resolved_entities_query(),
                    {
                        "member_ids": [str(member.id) for member in members],
                        "pending_job_id": None,
                    },
                )
                removed_resolved_entity_ids.extend(
                    _uuid_list(replacement_rows, "removed_resolved_entity_ids")
                )
                resolved = await compute_resolved_entity(members, schema, tracer=tracer)
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
            rebuilt_resolved.append(resolved)
        elif len(members) == 1:
            async with graph_store.transaction() as transaction:
                replacement_rows = await transaction.execute_write(
                    replace_component_resolved_entities_query(),
                    {
                        "member_ids": [str(members[0].id)],
                        "pending_job_id": None,
                    },
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
        rebuilt_entities=rebuilt_resolved,
    )
