"""Merge mechanics: computing how a resolved group of mentions and entities combine.

This module is storage-agnostic: it decides what a merge should look like,
but never touches GraphStore itself. Applying a computed MergePlan is a
separate step.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast
from uuid import NAMESPACE_OID, UUID, uuid4, uuid5

from pydantic import BaseModel

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.text import normalize_text
from agrag.ingestion.stats import StageFailure


if TYPE_CHECKING:
    from baml_py import ClientRegistry

    from agrag.graphdb.base import GraphStore, GraphStoreTransaction
    from agrag.llm.baml_client.runtime import BamlCallOptions


class PropertyStrategy(StrEnum):
    """Fallback rule for a property with no entry in PropertyRules."""

    KEEP_FIRST = "keep_first"
    KEEP_LAST = "keep_last"
    MERGE_ALL = "merge_all"


PropertyRule = Callable[[list[object]], object]
"""Per-property conflict resolver.

Takes every candidate value for one property, in encounter order, already
filtered to exclude None, and returns the resolved value.
"""


@dataclass
class PropertyRules:
    """Per-property conflict resolution, with a default for unlisted properties.

    Attributes:
        rules: Property name to resolver, for properties needing a specific rule.
        default: Strategy applied to a property with no entry in rules.
    """

    rules: dict[str, PropertyRule] = field(default_factory=dict)
    default: PropertyStrategy = PropertyStrategy.KEEP_FIRST


class ConflictRecord(BaseModel):
    """One property that had more than one candidate value.

    Attributes:
        field: The property name.
        candidates: Every distinct candidate value seen, in encounter order.
        resolved: The value compute_merge chose.
    """

    field: str
    candidates: list[object]
    resolved: object


class MergePlan(BaseModel):
    """Computed result of merging zero or more entities and mentions.

    Attributes:
        survivor: The resulting Entity. Its merge_count, source_chunk_ids,
            and merged_from are this call's best local computation, for
            reporting; apply_merge writes new_source_chunk_ids and
            merge_count_delta atomically instead, so a concurrent writer's
            own contribution to the same node is never overwritten.
        tombstone_ids: Ids of entities absorbed into survivor. Also this
            call's new contribution to the survivor's merged_from, applied
            atomically.
        conflicts: Every field that had more than one candidate value.
        accepted_merge_keys: Every normalized merge_key this merge
            accepted -- from existing_entities and mentions alike, not only
            the survivor's own chosen name -- so a later mention of any
            accepted name resolves back to this entity instead of creating
            a duplicate.
        new_source_chunk_ids: The chunk ids this call's mentions and
            absorbed entities contribute, applied as an atomic union
            against whatever the survivor's node currently has.
        merge_count_delta: The amount to atomically add to whatever
            merge_count the survivor's node currently has.
    """

    survivor: Entity
    tombstone_ids: list[UUID] = []
    conflicts: list[ConflictRecord] = []
    accepted_merge_keys: list[str] = []
    new_source_chunk_ids: list[UUID] = []
    merge_count_delta: int = 0


def select_canonical(
    entities: list[Entity], entity_type: EntityType | None
) -> tuple[Entity, list[Entity]]:
    """Return the canonical survivor and the rest, from two or more entities.

    Schema-completeness (fewest missing declared fields) first, then earliest
    created_at, then lexicographically smallest id.

    Args:
        entities: The entities to choose from.
        entity_type: The schema type for this label, if declared.

    Returns:
        The survivor and the absorbed entities.
    """
    declared_fields = set(entity_type.properties) if entity_type is not None else set()

    def missing_count(entity: Entity) -> int:
        return len(declared_fields - entity.properties.keys())

    ranked = sorted(entities, key=lambda e: (missing_count(e), e.created_at, str(e.id)))
    return ranked[0], ranked[1:]


def _dedupe_preserve_order(candidates: list[object]) -> list[object]:
    """Deduplicate values by equality, preserving first-occurrence order.

    Unlike ``dict.fromkeys``, this accepts unhashable values such as list- or
    dict-valued properties, for example a prior ``PropertyStrategy.MERGE_ALL``
    result being merged again on a later ingest.

    Args:
        candidates: Candidate values in encounter order.

    Returns:
        The distinct values, first-occurrence order.
    """
    distinct: list[object] = []
    for candidate in candidates:
        if candidate not in distinct:
            distinct.append(candidate)
    return distinct


def _resolve_property(
    field_name: str, candidates: list[object], rules: PropertyRules
) -> tuple[object, bool]:
    """Return the resolved value for one property and whether it conflicted.

    Args:
        field_name: The property name.
        candidates: Candidate values in encounter order, already filtered for
            None.
        rules: The per-property rule table.

    Returns:
        The resolved value and True if more than one distinct value was seen.
    """
    distinct = _dedupe_preserve_order(candidates)
    if len(distinct) <= 1:
        return (distinct[0] if distinct else None), False

    if field_name in rules.rules:
        return rules.rules[field_name](distinct), True

    if rules.default is PropertyStrategy.KEEP_FIRST:
        return distinct[0], True
    if rules.default is PropertyStrategy.KEEP_LAST:
        return distinct[-1], True
    return distinct, True  # MERGE_ALL


async def resolve_description(
    candidates: list[object],
    *,
    settings: Any | None = None,
    client: Any | None = None,
) -> tuple[object, bool, Any | None]:
    """Resolve a description field, trying LLM summarization.

    A single distinct candidate needs no LLM call. Multiple candidates try
    LLM summarization; on failure, fall back to concatenation.

    Args:
        candidates: Candidate values in encounter order.
        settings: LLM settings for summarization. None uses defaults.
        client: An already-built BAML client for tests.

    Returns:
        The resolved value, whether it conflicted, and an optional failure.
    """
    distinct = _dedupe_preserve_order(candidates)
    if len(distinct) <= 1:
        return (distinct[0] if distinct else None), False, None

    # Try LLM summarization.
    try:
        from agrag.ingestion.extract import ExtractionLLMSettings  # noqa: PLC0415
        from agrag.llm.client_registry import build_client_registry  # noqa: PLC0415
        from agrag.llm.retry import NO_RETRY, call_with_retry  # noqa: PLC0415

        baml_options: BamlCallOptions = {}
        if client is not None:
            retry = NO_RETRY
            active_client = client
        else:
            active_settings = settings or ExtractionLLMSettings()  # type: ignore[call-arg]
            registry = build_client_registry(
                active_settings.clients, strategy=active_settings.strategy
            )
            baml_options["client_registry"] = cast("ClientRegistry", registry)
            retry_obj = active_settings.retry
            try:
                from agrag.llm.baml_client import b as default_client  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError("llm extra not installed") from exc
            active_client = default_client
            retry = retry_obj if retry_obj is not None else NO_RETRY

        descriptions = [str(candidate) for candidate in distinct]
        result = await call_with_retry(
            lambda: active_client.SummarizeDescriptions(
                descriptions=descriptions, baml_options=baml_options
            ),
            retry,  # type: ignore[misc]
        )
        return result, True, None
    except Exception as exc:  # noqa: BLE001
        fallback = " | ".join(str(v) for v in distinct)
        failure = StageFailure(
            item_id="description",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return fallback, True, failure


async def merge_properties(
    property_sources: list[dict[str, object]],
    rules: PropertyRules,
    *,
    description_settings: Any | None = None,
    description_client: Any | None = None,
) -> tuple[dict[str, object], list[ConflictRecord], list[Any]]:
    """Return field-resolved properties and records of every real conflict.

    Args:
        property_sources: One dict per source entity/mention, keyed by field.
        rules: The per-property rule table.
        description_settings: LLM settings for description summarization.
        description_client: Injected LLM client for tests.

    Returns:
        The resolved properties, conflict records, and optional stage failures.
    """
    fields = {key for source in property_sources for key in source}
    resolved: dict[str, object] = {}
    conflicts: list[ConflictRecord] = []
    failures: list[Any] = []
    for field_name in fields:
        candidates = [
            source[field_name]
            for source in property_sources
            if source.get(field_name) is not None
        ]
        if field_name == "description":
            value, conflicted, failure = await resolve_description(
                candidates,
                settings=description_settings,
                client=description_client,
            )
            resolved[field_name] = value  # type: ignore[assignment]
            if conflicted:
                conflicts.append(
                    ConflictRecord(
                        field=field_name, candidates=candidates, resolved=value
                    )
                )
            if failure is not None:
                failures.append(failure)
        else:
            value, conflicted = _resolve_property(field_name, candidates, rules)
            resolved[field_name] = value
            if conflicted:
                conflicts.append(
                    ConflictRecord(
                        field=field_name, candidates=candidates, resolved=value
                    )
                )
    return resolved, conflicts, failures


def _new_survivor_id(label: str, name: str, job_id: UUID | None) -> UUID:
    """Return the id for a brand-new merge survivor.

    Inside a Cutover Job the id derives from (job_id, merge_key), so
    replaying the job after a crash reproduces the same id instead of
    minting a duplicate. Outside a job it stays random.

    Args:
        label: The survivor's entity label.
        name: The survivor's resolved name.
        job_id: The Cutover Job id, or None outside a job.

    Returns:
        The survivor id.
    """
    if job_id is None:
        return uuid4()
    merge_key = f"{label}:{normalize_text(name)}"
    return uuid5(NAMESPACE_OID, f"CutoverJob:{job_id}:{merge_key}")


async def compute_merge(  # noqa: PLR0912
    *,
    existing_entities: list[Entity],
    mentions: list[ExtractedEntity],
    schema: GraphSchema,
    rules: PropertyRules | None = None,
    description_settings: Any | None = None,
    description_client: Any | None = None,
    job_id: UUID | None = None,
) -> tuple[MergePlan, list[Any]]:
    """Compute how existing_entities and mentions combine into one Entity.

    No storage is touched. Zero existing entities produces a brand-new Entity.
    One produces an updated copy folding in the mentions. Two or more picks a
    canonical survivor and marks the rest for tombstoning.

    Args:
        existing_entities: Already-persisted entities this call reconciles.
        mentions: Fresh ExtractedEntity mentions to fold in.
        schema: Used to look up the entity type's declared properties for the
            canonical-id schema-completeness check.
        rules: Per-property conflict resolution. Defaults to keep_first.
        description_settings: LLM settings for description summarization.
        description_client: Injected LLM client for tests.
        job_id: The Cutover Job this merge runs under. A brand-new entity
            derives its id from (job_id, merge_key) instead of uuid4, so
            replaying the job after a crash reproduces the same id. None
            keeps today's random-id behavior for callers outside a job.

    Returns:
        The computed MergePlan and any description-LLM failures.

    Raises:
        ValueError: existing_entities and mentions are both empty, or their
            labels disagree.
    """
    if not existing_entities and not mentions:
        raise ValueError("compute_merge needs at least one entity or mention.")

    label = existing_entities[0].label if existing_entities else mentions[0].label
    if any(e.label != label for e in existing_entities) or any(
        m.label != label for m in mentions
    ):
        raise ValueError("compute_merge requires every input to share one label.")

    rules = rules or PropertyRules()
    entity_type = next((t for t in schema.entities if t.label == label), None)

    if len(existing_entities) >= 2:
        survivor_base, absorbed = select_canonical(existing_entities, entity_type)
    elif existing_entities:
        survivor_base, absorbed = existing_entities[0], []
    else:
        survivor_base, absorbed = None, []  # type: ignore[assignment]

    field_sources = [
        {"name": entity.name, **entity.properties} for entity in existing_entities
    ] + [{"name": mention.text, **mention.properties} for mention in mentions]

    resolved_fields, conflicts, desc_failures = await merge_properties(
        field_sources,
        rules,
        description_settings=description_settings,
        description_client=description_client,
    )
    name = resolved_fields.pop("name")
    properties = resolved_fields

    # Validate name type.
    if not isinstance(name, str):
        raise ValueError(f"Resolved name must be str, got {type(name)}")

    survivor_id = (
        survivor_base.id
        if survivor_base is not None
        else _new_survivor_id(label, name, job_id)
    )
    merged_from_vals: list[UUID] = []
    if survivor_base is not None:
        merged_from_vals.extend(survivor_base.merged_from)
    merged_from_vals.extend(entity.id for entity in absorbed)
    # Deduplicate while preserving order.
    merged_from = list(dict.fromkeys(merged_from_vals))

    base_merge_count = survivor_base.merge_count if survivor_base is not None else 0
    merge_count = (
        base_merge_count
        + sum(entity.merge_count for entity in absorbed)
        + len(mentions)
    )
    # Ensure at least 1.
    merge_count = max(merge_count, 1)

    source_ids: list[UUID] = []
    if survivor_base is not None:
        source_ids.extend(survivor_base.source_chunk_ids)
    for entity in absorbed:
        source_ids.extend(entity.source_chunk_ids)
    for mention in mentions:
        source_ids.append(mention.chunk_id)
    source_chunk_ids = list(dict.fromkeys(source_ids))

    # This call's own contribution, as opposed to source_chunk_ids above
    # (the full local union, kept on the Entity for reporting): apply_merge
    # writes this atomically against whatever the node currently has, so a
    # concurrent writer's own contribution is never lost to a full
    # overwrite from a snapshot taken before either write landed.
    new_source_ids: list[UUID] = []
    for entity in absorbed:
        new_source_ids.extend(entity.source_chunk_ids)
    for mention in mentions:
        new_source_ids.append(mention.chunk_id)
    new_source_chunk_ids = list(dict.fromkeys(new_source_ids))
    merge_count_delta = sum(entity.merge_count for entity in absorbed) + len(mentions)

    accepted_merge_keys = list(
        dict.fromkeys(
            [entity.merge_key for entity in existing_entities]
            + [f"{label}:{normalize_text(mention.text)}" for mention in mentions]
        )
    )

    # Preserve created_at from survivor_base if exists.
    created_at = survivor_base.created_at if survivor_base is not None else None
    if created_at is not None:
        survivor = Entity(
            id=survivor_id,
            created_at=created_at,
            label=label,
            name=name,  # type: ignore[arg-type]
            properties=properties,
            merged_from=merged_from,
            merge_count=merge_count,
            source_chunk_ids=source_chunk_ids,
        )
    else:
        survivor = Entity(
            id=survivor_id,
            label=label,
            name=name,  # type: ignore[arg-type]
            properties=properties,
            merged_from=merged_from,
            merge_count=merge_count,
            source_chunk_ids=source_chunk_ids,
        )

    plan = MergePlan(
        survivor=survivor,
        tombstone_ids=[entity.id for entity in absorbed],
        conflicts=conflicts,
        accepted_merge_keys=accepted_merge_keys,
        new_source_chunk_ids=new_source_chunk_ids,
        merge_count_delta=merge_count_delta,
    )
    return plan, desc_failures


@dataclass
class _TransferredRelationship:
    """One relationship row eligible for the post-merge dedup pass.

    Rows are built directly in tests.
    """

    other_id: UUID
    rel_type: str
    new_relationship_id: UUID
    source_chunk_ids: list[UUID]
    properties: dict[str, object]


def _parse_relationship_rows(
    rows: list[dict[str, object]],
) -> list[_TransferredRelationship]:
    """Parse relationship-query rows, skipping any that fail to parse.

    Args:
        rows: Relationship rows, each carrying one edge's other-end id,
            type, id, and full property map.

    Returns:
        The rows that parsed successfully. A row with an unreadable
        ``properties`` map still parses -- its identity fields are what
        dedup grouping needs, and losing extra-property enrichment for one
        row is a smaller defect than dropping a real duplicate.
    """
    parsed: list[_TransferredRelationship] = []
    for row in rows:
        try:
            other_id = UUID(str(row["other_id"]))
            rel_type = str(row["rel_type"])
            new_id = UUID(str(row["new_relationship_id"]))
        except (KeyError, ValueError, TypeError):
            continue
        raw_properties = row.get("properties")
        properties = raw_properties if isinstance(raw_properties, dict) else {}
        raw_chunk_ids = properties.get("source_chunk_ids") or []
        try:
            if not isinstance(raw_chunk_ids, list):
                raise TypeError("source_chunk_ids must be a list")
            chunk_ids = [UUID(str(cid)) for cid in raw_chunk_ids]
        except (ValueError, TypeError):
            chunk_ids = []
        parsed.append(
            _TransferredRelationship(
                other_id=other_id,
                rel_type=rel_type,
                new_relationship_id=new_id,
                source_chunk_ids=chunk_ids,
                properties=properties,
            )
        )
    return parsed


def _plan_relationship_dedup(
    rows: list[_TransferredRelationship],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Group relationships by (type, other_id) and plan dedup within one direction.

    A duplicate group's kept edge absorbs every field from the edges being
    deleted: ``source_chunk_ids`` is unioned, and every other property keeps
    the keeper's own value when it has one, otherwise falls back to the
    first duplicate that does, so a duplicate's answer is not silently lost
    just because the keeper happened to be picked first.

    Args:
        rows: Every relationship currently linking the survivor to another
            node in one direction. Constraints are per relationship type
            (see ``relation_id_constraint_query``), so an id collision across
            types is possible and each returned item carries its type to keep
            the dedup queries scoped to the right one.

    Returns:
        Updates and deletes ready for the dedup queries, each item keyed by
        relationship id and type.
    """
    groups: dict[tuple[str, UUID], list[_TransferredRelationship]] = {}
    for row in rows:
        groups.setdefault((row.rel_type, row.other_id), []).append(row)

    updates: list[dict[str, object]] = []
    deletes: list[dict[str, object]] = []
    for group in groups.values():
        if len(group) == 1:
            continue
        keeper, *extras = group
        merged_chunk_ids = list(
            dict.fromkeys(
                keeper.source_chunk_ids
                + [cid for extra in extras for cid in extra.source_chunk_ids]
            )
        )
        merged_properties = dict(keeper.properties)
        for extra in extras:
            for key, value in extra.properties.items():
                if key in ("id", "source_chunk_ids"):
                    continue
                if merged_properties.get(key) is None and value is not None:
                    merged_properties[key] = value
        merged_properties["source_chunk_ids"] = [str(cid) for cid in merged_chunk_ids]
        updates.append(
            {
                "id": str(keeper.new_relationship_id),
                "rel_type": keeper.rel_type,
                "properties": merged_properties,
            }
        )
        deletes.extend(
            {"id": str(extra.new_relationship_id), "rel_type": extra.rel_type}
            for extra in extras
        )
    return updates, deletes


def relation_id(source_id: UUID, target_id: UUID, rel_type: str) -> UUID:
    """Return the deterministic id for a domain relationship triple.

    Two concurrent ``add()`` calls resolving the same ``(source_id,
    target_id, rel_type)`` triple can both miss the existing-relation lookup
    and each try to create it; since this id depends only on the triple, both
    writers compute the same one, so ``upsert_relation_query``'s ``MERGE``
    converges to a single edge instead of two parallel ones with unrelated
    random ids. Mirrors ``mentioned_in_id``.

    Args:
        source_id: The relationship's source Entity id.
        target_id: The relationship's target Entity id.
        rel_type: The relationship's type.

    Returns:
        The relationship id. Same triple always returns the same id.
    """
    return uuid5(NAMESPACE_OID, f"{rel_type}:{source_id}:{target_id}")


def part_of_id(document_node_id: UUID, chunk_id: UUID, version_id: UUID | str) -> UUID:
    """Return the id for one versioned Document -[:PART_OF]-> Chunk edge.

    Args:
        document_node_id: The id of the Document graph node.
        chunk_id: The id of the Chunk.
        version_id: The identifier for this document version.

    Returns:
        The edge id. Each document version gets a separate relationship id.
    """
    return uuid5(NAMESPACE_OID, f"PART_OF:{document_node_id}:{chunk_id}:{version_id}")


def next_chunk_id(from_chunk_id: UUID, to_chunk_id: UUID) -> UUID:
    """Return the deterministic id for a Chunk -[:NEXT_CHUNK]-> Chunk edge.

    Args:
        from_chunk_id: The id of the earlier chunk in sequence.
        to_chunk_id: The id of the chunk that follows it.

    Returns:
        The edge id. Same pair always returns the same id.
    """
    return uuid5(NAMESPACE_OID, f"NEXT_CHUNK:{from_chunk_id}:{to_chunk_id}")


_MAX_ALIAS_OWNER_CHAIN_HOPS = 32


async def _resolve_alias_owner(owner_id: str, *, txn: GraphStoreTransaction) -> str:
    """Follow a merge-key alias owner's ``merged_into`` chain to its live id.

    ``upsert_merge_alias_query`` never rewrites an alias once created: if the
    entity it names is later absorbed by a separate, earlier-committed
    merge, the alias still points at that now-tombstoned id. Comparing an
    alias owner's raw id against a merge's own survivor and tombstone ids
    would then read that historical alias as a foreign conflict even though
    it resolves, through ``merged_into``, to the very entity this merge is
    writing.

    Args:
        owner_id: The alias row's raw ``entity_id``, possibly a tombstone.
        txn: The transaction to read within.

    Returns:
        The id of the live entity at the end of the chain. Returns
        ``owner_id`` unchanged when it already names a live node.

    Raises:
        GraphStoreDataIntegrityError: The chain cycles, points at a missing
            node, or exceeds ``_MAX_ALIAS_OWNER_CHAIN_HOPS`` hops without
            reaching a live node.
    """
    from agrag.cypher.entities import NODE_IDENTITY_LABEL  # noqa: PLC0415
    from agrag.graphdb.errors import GraphStoreDataIntegrityError  # noqa: PLC0415

    visited: set[str] = set()
    current_id = owner_id
    for _ in range(_MAX_ALIAS_OWNER_CHAIN_HOPS):
        if current_id in visited:
            raise GraphStoreDataIntegrityError(
                f"merged_into cycle detected resolving alias owner "
                f"{owner_id!r} (revisited {current_id!r})"
            )
        visited.add(current_id)
        rows = await txn.execute_read(
            f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: $id}}) "
            f"RETURN n.merged_into AS merged_into",
            {"id": current_id},
        )
        if not rows:
            raise GraphStoreDataIntegrityError(
                f"alias owner chain from {owner_id!r} points at missing "
                f"node {current_id!r}"
            )
        next_id = rows[0].get("merged_into")
        if not next_id:
            return current_id
        current_id = str(next_id)
    raise GraphStoreDataIntegrityError(
        f"alias owner chain from {owner_id!r} exceeded "
        f"{_MAX_ALIAS_OWNER_CHAIN_HOPS} hops without reaching a live node"
    )


async def apply_merge(
    plan: MergePlan,
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    pending_job_id: str | None = None,
) -> None:
    """Write a computed MergePlan to storage.

    Every call runs inside one GraphStore transaction: it upserts the
    survivor and records a merge-key alias for its current name. A
    failure partway through leaves no half-written state: no survivor
    without its alias.

    Destructive merging is retired: a plan with non-empty tombstone_ids
    is rejected before any write runs, and callers must persist the
    match through MATCHES edges and materialize a ResolvedEntity
    instead.

    Args:
        plan: The merge to write.
        graph_store: Where the merge is written.
        schema: The schema the survivor's label belongs to.
        pending_job_id: The in-flight Cutover Job's id, tagging the
            survivor node and its aliases until that job commits. None
            writes untagged, for callers outside a job.

    Raises:
        ValueError: plan.tombstone_ids is non-empty.
        GraphStoreAliasConflictError: An accepted merge_key is already owned
            by a live entity outside this merge's own survivor id -- a
            concurrent writer accepted that name as an alias of, or
            created it as the canonical name of, a different entity.
        GraphStoreDataIntegrityError: A candidate conflicting alias owner's
            merged_into chain cycles, points at a missing node, or does not
            reach a live node within the hop limit.
    """
    from agrag.common.data_models.graph_record import (  # noqa: PLC0415
        NodeRecord,
        tag_pending,
    )
    from agrag.cypher.entities import (  # noqa: PLC0415
        upsert_merge_alias_query,
        upsert_survivor_query,
        validate_identifier,
    )
    from agrag.graphdb.errors import GraphStoreAliasConflictError  # noqa: PLC0415
    from agrag.graphdb.serialize import node_params  # noqa: PLC0415

    if plan.tombstone_ids:
        raise ValueError(
            "Destructive merge is retired: apply_merge no longer absorbs "
            "entities. Persist the match with MATCHES edges and materialize "
            "a ResolvedEntity instead."
        )
    validate_identifier(plan.survivor.label)
    survivor_id = str(plan.survivor.id)

    async with graph_store.transaction() as txn:
        # Everything except source_chunk_ids/merged_from/merge_count is
        # applied as-is; those three go through upsert_survivor_query's
        # atomic accumulation instead, using node_params only to get their
        # driver-safe encoding, not their values.
        record = plan.survivor.to_node_record()
        survivor_properties = dict(record.properties)
        survivor_properties.pop("source_chunk_ids", None)
        survivor_properties.pop("merged_from", None)
        survivor_properties.pop("merge_count", None)
        params = node_params(
            tag_pending(
                NodeRecord(
                    id=record.id, labels=record.labels, properties=survivor_properties
                ),
                pending_job_id,
            )
        )
        params["new_source_chunk_ids"] = [str(cid) for cid in plan.new_source_chunk_ids]
        params["new_merged_from"] = [str(tid) for tid in plan.tombstone_ids]
        params["merge_count_delta"] = plan.merge_count_delta
        await txn.execute_write(
            upsert_survivor_query(plan.survivor.label), {"records": [params]}
        )
        accepted_merge_keys = plan.accepted_merge_keys or [plan.survivor.merge_key]
        alias_rows = await txn.execute_write(
            upsert_merge_alias_query(),
            {
                "merge_keys": accepted_merge_keys,
                "entity_id": survivor_id,
                "pending_job_id": pending_job_id,
            },
        )
        # An alias an earlier, unrelated merge accepted still points at
        # that merge's own survivor id even after that entity is itself
        # later absorbed elsewhere, since upsert_merge_alias_query never
        # rewrites an alias once created. Resolving the owner's
        # merged_into chain first tells that historical owner apart from
        # a genuinely different live entity that claimed the same name.
        known_ids = {survivor_id}
        candidate_conflicts = {
            row["merge_key"]: row["entity_id"]
            for row in alias_rows
            if isinstance(row, dict) and row.get("entity_id") not in known_ids
        }
        conflicts = {}
        for merge_key, owner_id in candidate_conflicts.items():
            live_owner_id = await _resolve_alias_owner(owner_id, txn=txn)
            if live_owner_id not in known_ids:
                conflicts[merge_key] = live_owner_id
        if conflicts:
            raise GraphStoreAliasConflictError(conflicts)


def mentioned_in_id(chunk_id: UUID, entity_id: UUID) -> UUID:
    """Return the deterministic id for a new Chunk -[:MENTIONED_IN]-> Entity edge.

    Only a fresh id for a pair with no persisted edge yet is guaranteed to equal
    this. A caller writing to an already-persisted pair should look up the
    edge by its endpoints first and fall back to this id only when none is
    found.

    Args:
        chunk_id: The Chunk's id.
        entity_id: The Entity's id.

    Returns:
        The edge id. Deterministic: same pair always returns same id.
    """
    return uuid5(NAMESPACE_OID, f"MENTIONED_IN:{chunk_id}:{entity_id}")
