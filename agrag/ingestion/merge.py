"""Merge mechanics: computing how a resolved group of mentions and entities combine.

This module is storage-agnostic: it decides what a merge should look like,
but never touches GraphStore itself. Applying a computed MergePlan is a
separate step.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import NAMESPACE_OID, UUID, uuid4, uuid5

from pydantic import BaseModel

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.text import normalize_text


if TYPE_CHECKING:
    from agrag.graphdb.base import GraphStore


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


def _select_canonical(
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


async def _resolve_description(
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

        if client is not None:
            baml_options: dict[str, Any] = {}
            retry = NO_RETRY
            active_client = client
        else:
            baml_options = {}
            retry_obj = None
            try:
                active_settings = settings or ExtractionLLMSettings()  # type: ignore[call-arg]
                registry = build_client_registry(
                    active_settings.clients, strategy=active_settings.strategy
                )
                baml_options = {"client_registry": registry}
                retry_obj = active_settings.retry
            except Exception:
                raise
            try:
                from agrag.llm.baml_client import b as default_client  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError("llm extra not installed") from exc
            active_client = default_client
            retry = retry_obj if retry_obj is not None else NO_RETRY

        summarize = getattr(active_client, "SummarizeDescriptions", None)
        if summarize is None:
            summarize = getattr(active_client, "SummarizeDescription", None)
        if summarize is None:
            raise AttributeError("No summarization function on BAML client")

        try:
            result = await call_with_retry(
                lambda: summarize(distinct, baml_options),
                retry,  # type: ignore[misc]
            )
        except TypeError:
            result = await call_with_retry(
                lambda: summarize(descriptions=distinct, baml_options=baml_options),  # type: ignore[misc]
                retry,
            )
        return result, True, None
    except Exception as exc:  # noqa: BLE001
        fallback = " | ".join(str(v) for v in distinct)
        try:
            from agrag.ingestion.types import StageFailure  # noqa: PLC0415
        except ImportError:
            return fallback, True, None
        failure = StageFailure(
            item_id="description",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return fallback, True, failure


async def _merge_properties(
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
            value, conflicted, failure = await _resolve_description(
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


async def compute_merge(  # noqa: PLR0912
    *,
    existing_entities: list[Entity],
    mentions: list[ExtractedEntity],
    schema: GraphSchema,
    rules: PropertyRules | None = None,
    description_settings: Any | None = None,
    description_client: Any | None = None,
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
        survivor_base, absorbed = _select_canonical(existing_entities, entity_type)
    elif existing_entities:
        survivor_base, absorbed = existing_entities[0], []
    else:
        survivor_base, absorbed = None, []  # type: ignore[assignment]

    field_sources = [
        {"name": entity.name, **entity.properties} for entity in existing_entities
    ] + [{"name": mention.text} for mention in mentions]

    resolved_fields, conflicts, desc_failures = await _merge_properties(
        field_sources,  # ty: ignore[invalid-argument-type]
        rules,
        description_settings=description_settings,
        description_client=description_client,
    )
    name = resolved_fields.pop("name")
    properties = resolved_fields

    # Validate name type.
    if not isinstance(name, str):
        raise ValueError(f"Resolved name must be str, got {type(name)}")

    survivor_id = survivor_base.id if survivor_base is not None else uuid4()
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

    Rows come from either ``fetch_node_relationships_query`` (the survivor's
    neighbourhood after all transfers land) or, in tests, directly.
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
        rows: Rows from ``fetch_node_relationships_query``, each carrying one
            edge's other-end id, type, id, and full property map.

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


async def apply_merge(
    plan: MergePlan, *, graph_store: GraphStore, schema: GraphSchema
) -> None:
    """Write a computed MergePlan to storage.

    Every call runs inside one GraphStore transaction: when tombstone_ids is
    non-empty, it first clears merge_key from every entity about to be
    absorbed, since canonical selection can pick a different node as
    survivor than the one a property rule (e.g. KEEP_FIRST) resolves the
    name from, so the survivor's resolved merge_key can equal a still-live
    tombstone's own merge_key -- writing the survivor before clearing that
    would collide with the per-label merge_key uniqueness constraint. It
    then always upserts the survivor and records a merge-key alias for its
    current name, and, when tombstone_ids is non-empty, also tombstones,
    deletes edges that would become meaningless self-links, transfers what
    remains, and dedupes the survivor's resulting neighbourhood. A failure
    partway through leaves no half-written state: no survivor without its
    alias, no tombstone without its edges transferred, no transferred edge
    without its duplicate cleaned up.

    Args:
        plan: The merge to write.
        graph_store: Where the merge is written.
        schema: The schema the survivor's label belongs to.
    """
    from agrag.common.data_models.graph_record import NodeRecord  # noqa: PLC0415
    from agrag.cypher.entities import (  # noqa: PLC0415
        upsert_merge_alias_query,
        upsert_survivor_query,
        validate_identifier,
    )
    from agrag.cypher.merge import (  # noqa: PLC0415
        apply_relationship_dedup_delete_query,
        apply_relationship_dedup_update_query,
        clear_tombstone_merge_keys_query,
        delete_internal_relationships_query,
        fetch_node_relationships_query,
        tombstone_query,
        transfer_relationships_query,
    )
    from agrag.graphdb.serialize import node_params  # noqa: PLC0415

    validate_identifier(plan.survivor.label)
    survivor_id = str(plan.survivor.id)
    tombstone_ids = [str(tid) for tid in plan.tombstone_ids]

    async with graph_store.transaction() as txn:
        if tombstone_ids:
            await txn.execute_write(
                clear_tombstone_merge_keys_query(plan.survivor.label),
                {"tombstone_ids": tombstone_ids},
            )

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
            NodeRecord(
                id=record.id, labels=record.labels, properties=survivor_properties
            )
        )
        params["new_source_chunk_ids"] = [str(cid) for cid in plan.new_source_chunk_ids]
        params["new_merged_from"] = [str(tid) for tid in plan.tombstone_ids]
        params["merge_count_delta"] = plan.merge_count_delta
        await txn.execute_write(
            upsert_survivor_query(plan.survivor.label), {"records": [params]}
        )
        accepted_merge_keys = plan.accepted_merge_keys or [plan.survivor.merge_key]
        await txn.execute_write(
            upsert_merge_alias_query(),
            {"merge_keys": accepted_merge_keys, "entity_id": survivor_id},
        )

        if not tombstone_ids:
            return

        await txn.execute_write(
            tombstone_query(plan.survivor.label),
            {"tombstone_ids": tombstone_ids, "survivor_id": survivor_id},
        )

        # Edges wholly inside the absorbed set, and edges directly between an
        # absorbed node and the survivor itself, must go before any transfer
        # runs: transferring either would create a meaningless self-loop, or
        # (for the former) a stale survivor -> tombstone edge once the first
        # transfer moves the other end.
        await txn.execute_write(
            delete_internal_relationships_query(),
            {"tombstone_ids": tombstone_ids, "survivor_id": survivor_id},
        )

        for tombstone_id in tombstone_ids:
            for outgoing in (True, False):
                await txn.execute_write(
                    transfer_relationships_query(outgoing=outgoing),
                    {"tombstone_id": tombstone_id, "survivor_id": survivor_id},
                )

        # Re-fetch the survivor's whole neighbourhood, one direction at a
        # time, rather than deduping each transfer's own return rows: a
        # duplicate can pair a freshly transferred edge against one the
        # survivor already had, or against another tombstone's transfer.
        for outgoing in (True, False):
            rows = await txn.execute_write(
                fetch_node_relationships_query(outgoing=outgoing),
                {"node_id": survivor_id},
            )
            updates, deletes = _plan_relationship_dedup(_parse_relationship_rows(rows))
            if updates:
                await txn.execute_write(
                    apply_relationship_dedup_update_query(), {"updates": updates}
                )
            if deletes:
                await txn.execute_write(
                    apply_relationship_dedup_delete_query(), {"delete_ids": deletes}
                )


def mentioned_in_id(chunk_id: UUID, entity_id: UUID) -> UUID:
    """Return the deterministic id for a Chunk -[:MENTIONED_IN]-> Entity edge.

    Args:
        chunk_id: The Chunk's id.
        entity_id: The Entity's id.

    Returns:
        The edge id. Deterministic: same pair always returns same id.
    """
    return uuid5(NAMESPACE_OID, f"MENTIONED_IN:{chunk_id}:{entity_id}")
