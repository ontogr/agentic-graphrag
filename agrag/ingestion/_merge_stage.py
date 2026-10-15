"""Entity merge stage of one ingestion batch.

Mentions that the resolver grouped are merged into one survivor per entity.
Relations and MENTIONED_IN edges are then mapped onto those survivors and
deduplicated against the edges the graph already holds.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.graph_record import RelationRecord
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.relation import Relation
from agrag.common.data_models.stage_failure import StageFailure, cap_failures
from agrag.cypher.entities import fetch_relations_between_query
from agrag.graphdb.base import GraphStore
from agrag.ingestion._stage_context import StageContext
from agrag.ingestion.merge import (
    apply_merge,
    compute_merge,
    mentioned_in_id,
    pending_relation_id,
    relation_id,
)
from agrag.ingestion.resolve.resolution import BatchResolution
from agrag.ingestion.resolved_embeddings import embed_resolved_entities
from agrag.ingestion.resolved_entities import (
    MatchComponent,
    decisions_by_component,
    write_matches_and_rebuild,
)
from agrag.ingestion.stats import MergeStats
from agrag.ingestion.stats.dropped import DroppedCount
from agrag.loaders.types import ErrorPolicy
from agrag.observability import record_stage_failure


@dataclass(frozen=True)
class MergeStageResult:
    """The entity and relation outcome of one batch.

    Attributes:
        stats: The merge counts and the capped merge failures.
        survivors: The merged entities this call wrote, keyed by id.
        created_entity_ids: The ids of survivors that no committed entity existed
            for, so this call created them.
        resolved_vector_failures: Failures from embedding resolved entities.
        relation_records: Domain relations between the batch's survivors, merged
            with the relations the graph already holds.
        mentioned_in_records: MENTIONED_IN edges from each real mention's chunk
            to the survivor it resolved to.
        mention_to_entity: The final entity id for each mention index.
    """

    stats: MergeStats
    survivors: dict[UUID, Entity]
    created_entity_ids: list[UUID]
    resolved_vector_failures: list[StageFailure]
    relation_records: list[RelationRecord]
    mentioned_in_records: list[RelationRecord]
    mention_to_entity: dict[int, UUID]


async def merge_stage(
    entities: list[ExtractedEntity],
    relations: list[ExtractedRelation],
    batch: BatchResolution,
    ctx: StageContext,
    *,
    graph_schema: GraphSchema,
    rebuilt_components: list[MatchComponent] | None,
) -> MergeStageResult:
    """Merge resolved mentions into survivors and map relations onto them.

    Each group of mentions becomes one merged entity. Resolver components are
    then rebuilt around their members. Mentions and relations that point at
    no survivor are left out of the relation records.

    Args:
        entities: The mentions extracted from this batch's chunks.
        relations: The relations extracted from this batch's chunks.
        batch: The resolver output for the same mentions.
        ctx: The store the merged entities are written to, the embedder, the
            error policy, the job and the tracer.
        graph_schema: The schema the merge and rebuild work against.
        rebuilt_components: When set, each rebuilt component is appended with
            its decisions and members.

    Returns:
        The survivors, relation records, merge counts and mention-to-entity map.

    Raises:
        Exception: The first failed merge or rebuild, when ``error_policy`` is
            ``RAISE``.
    """
    pending_job_id = str(ctx.job_id) if ctx.job_id is not None else None
    merge_failures: list[StageFailure] = list(batch.failures)
    (
        survivors,
        mention_to_entity,
        nodes_created,
        nodes_updated,
        conflicts_resolved,
        created_entity_ids,
    ) = await _merge_mention_groups(
        entities,
        batch,
        merge_failures,
        ctx,
        graph_schema=graph_schema,
    )
    resolved_vector_failures = await _rebuild_components(
        batch,
        survivors,
        mention_to_entity,
        merge_failures,
        ctx,
        graph_schema=graph_schema,
        pending_job_id=pending_job_id,
        rebuilt_components=rebuilt_components,
    )
    relation_records, relations_dropped = await _domain_relation_records(
        relations,
        mention_to_entity,
        graph_store=ctx.graph_store,
        pending_job_id=pending_job_id,
        error_policy=ctx.error_policy,
        failures=merge_failures,
    )
    mentioned_in_records = await _mentioned_in_records(
        entities,
        mention_to_entity,
        graph_store=ctx.graph_store,
        error_policy=ctx.error_policy,
        failures=merge_failures,
    )
    merge_failures_capped = cap_failures(merge_failures)
    stats = MergeStats(
        nodes_created=nodes_created,
        nodes_updated=nodes_updated,
        conflicts_resolved=conflicts_resolved,
        dropped=relations_dropped,
        failures=merge_failures_capped.items,
        failures_total=merge_failures_capped.total,
        failures_truncated=merge_failures_capped.truncated,
    )
    return MergeStageResult(
        stats=stats,
        survivors=survivors,
        created_entity_ids=created_entity_ids,
        resolved_vector_failures=resolved_vector_failures,
        relation_records=relation_records,
        mentioned_in_records=mentioned_in_records,
        mention_to_entity=mention_to_entity,
    )


async def _merge_mention_groups(
    entities: list[ExtractedEntity],
    batch: BatchResolution,
    merge_failures: list[StageFailure],
    ctx: StageContext,
    *,
    graph_schema: GraphSchema,
) -> tuple[dict[UUID, Entity], dict[int, UUID], int, int, int, list[UUID]]:
    """Merge each resolved group into a survivor and count the outcomes.

    Failed groups are appended to ``merge_failures`` and left out of the
    returned survivors. The returned counts are ``nodes_created``,
    ``nodes_updated`` and ``conflicts_resolved``. The returned
    ``created_entity_ids`` lists the survivors that had no existing entity.
    """
    pending_job_id = str(ctx.job_id) if ctx.job_id is not None else None
    resolved_tracer = ctx.tracer
    survivors: dict[UUID, Entity] = {}
    mention_to_entity: dict[int, UUID] = {}
    created_entity_ids: list[UUID] = []
    nodes_created = 0
    nodes_updated = 0
    conflicts_resolved = 0
    for group in batch.groups:
        group_indices = [
            index
            for index in group.entity_indices
            if index not in batch.unresolved_indices
        ]
        if not group_indices:
            continue
        group_mentions = [entities[i] for i in group_indices]
        with resolved_tracer.start_as_current_span(
            "agrag.merge.merge_group",
            attributes={"agrag.mention_count": len(group_mentions)},
        ) as span:
            existing_for_group: list[Entity] = []
            seen_ids: set[UUID] = set()
            for idx in group_indices:
                ent = batch.exact_matches.get(idx)
                if ent is not None and ent.id not in seen_ids:
                    seen_ids.add(ent.id)
                    existing_for_group.append(ent)

            try:
                plan, desc_failures = await compute_merge(
                    existing_entities=existing_for_group,
                    mentions=group_mentions,
                    schema=graph_schema,
                    job_id=ctx.job_id,
                    tracer=ctx.tracer,
                )
            except Exception as exc:  # noqa: BLE001
                if ctx.error_policy is ErrorPolicy.RAISE:
                    raise
                trace_id, span_id = record_stage_failure(exc)
                merge_failures.append(
                    StageFailure(
                        item_id=",".join(str(entities[i].text) for i in group_indices),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        trace_id=trace_id,
                        span_id=span_id,
                    )
                )
                continue

            if desc_failures:
                merge_failures.extend(desc_failures)
            try:
                await apply_merge(
                    plan,
                    graph_store=ctx.graph_store,
                    schema=graph_schema,
                    pending_job_id=pending_job_id,
                    deferred=ctx.deferred,
                )
            except Exception as exc:  # noqa: BLE001
                if ctx.error_policy is ErrorPolicy.RAISE:
                    raise
                trace_id, span_id = record_stage_failure(exc)
                merge_failures.append(
                    StageFailure(
                        item_id=str(plan.survivor.id),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        trace_id=trace_id,
                        span_id=span_id,
                    )
                )
                continue

            conflicts_resolved += len(plan.conflicts)
            if not existing_for_group:
                nodes_created += 1
                created_entity_ids.append(plan.survivor.id)
            else:
                nodes_updated += 1
            span.set_attribute("agrag.conflicts_resolved", len(plan.conflicts))
            survivors[plan.survivor.id] = plan.survivor
            for idx in group_indices:
                mention_to_entity[idx] = plan.survivor.id
    return (
        survivors,
        mention_to_entity,
        nodes_created,
        nodes_updated,
        conflicts_resolved,
        created_entity_ids,
    )


async def _rebuild_components(
    batch: BatchResolution,
    survivors: dict[UUID, Entity],
    mention_to_entity: dict[int, UUID],
    merge_failures: list[StageFailure],
    ctx: StageContext,
    *,
    graph_schema: GraphSchema,
    pending_job_id: str | None,
    rebuilt_components: list[MatchComponent] | None,
) -> list[StageFailure]:
    """Rebuild each resolver component around its merged members.

    Components that raise are appended to ``merge_failures``. Returns the
    resolved-entity embedding failures from the components that rebuilt.
    """
    if batch.result is None:
        return []
    resolved_tracer = ctx.tracer
    resolved_vector_failures: list[StageFailure] = []
    mention_to_entity.update(batch.persisted_ids)
    for decisions in decisions_by_component(batch.result.matches, mention_to_entity):
        member_ids = {decision.entity_a_id for decision in decisions} | {
            decision.entity_b_id for decision in decisions
        }
        members = [
            survivors.get(member_id) or batch.candidate_entities[member_id]
            for member_id in member_ids
        ]
        with resolved_tracer.start_as_current_span(
            "agrag.merge.rebuild_component",
            attributes={"agrag.member_count": len(members)},
        ):
            try:
                rebuild = await write_matches_and_rebuild(
                    decisions,
                    graph_store=ctx.graph_store,
                    schema=graph_schema,
                    members=members,
                    pending_job_id=pending_job_id,
                    deferred=ctx.deferred,
                    tracer=ctx.tracer,
                )
            except Exception as exc:  # noqa: BLE001
                if ctx.error_policy is ErrorPolicy.RAISE:
                    raise
                trace_id, span_id = record_stage_failure(exc)
                merge_failures.append(
                    StageFailure(
                        item_id=",".join(str(member_id) for member_id in member_ids),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        trace_id=trace_id,
                        span_id=span_id,
                    )
                )
                continue
            if rebuilt_components is not None:
                rebuilt_components.append((decisions, members))
            # Embedded per component, not batched after the loop, so a later
            # component's failure under ErrorPolicy.RAISE does not skip the
            # embeddings of components already committed above.
            resolved_vector_failures.extend(
                await embed_resolved_entities(
                    [rebuild.resolved_entity],
                    embedder=ctx.embedder,
                    graph_store=ctx.graph_store,
                    error_policy=ctx.error_policy,
                    pending_job_id=ctx.job_id,
                    deferred=ctx.deferred,
                )
            )
    return resolved_vector_failures


async def _domain_relation_records(
    relations: list[ExtractedRelation],
    mention_to_entity: dict[int, UUID],
    *,
    graph_store: GraphStore,
    pending_job_id: str | None,
    error_policy: ErrorPolicy,
    failures: list[StageFailure],
) -> tuple[list[RelationRecord], list[DroppedCount]]:
    """Map relations onto survivors and merge them with stored relations.

    A failed lookup is appended to ``failures`` and its triples are treated as
    having no stored relation, unless ``error_policy`` is ``RAISE``.

    Returns:
        Relation records and counts of relations with missing endpoints or
        endpoints that became one entity.
    """
    # Domain relation triples: (src_id, tgt_id, label) with the chunks that
    # asserted them, unioned within this call.
    triple_to_chunk_ids: dict[tuple[UUID, UUID, str], list[UUID]] = {}
    unmapped: Counter[str] = Counter()
    self_loops: Counter[str] = Counter()
    for rel in relations:
        src_id = mention_to_entity.get(rel.source_index)
        tgt_id = mention_to_entity.get(rel.target_index)
        if src_id is None or tgt_id is None:
            unmapped[rel.label] += 1
            continue
        if src_id == tgt_id:
            self_loops[rel.label] += 1
            continue
        key = (src_id, tgt_id, rel.label)
        lst = triple_to_chunk_ids.setdefault(key, [])
        if rel.chunk_id not in lst:
            lst.append(rel.chunk_id)

    existing_rel_map = await _global_relation_lookup(
        list(triple_to_chunk_ids.keys()),
        graph_store=graph_store,
        job_id=pending_job_id,
        error_policy=error_policy,
        failures=failures,
    )

    relation_records: list[RelationRecord] = []
    for (src_id, tgt_id, rel_type), chunk_ids in triple_to_chunk_ids.items():
        existing = existing_rel_map.get((src_id, tgt_id, rel_type))
        if existing is not None:
            existing_id, existing_scids = existing
            union_ids = list(dict.fromkeys([*existing_scids, *chunk_ids]))
            rel_id = existing_id
            canonical_id = None
        else:
            # A new relation is written under a job-scoped id; the commit folds
            # it into the canonical id.
            canonical_id = relation_id(src_id, tgt_id, rel_type)
            rel_id = (
                pending_relation_id(UUID(pending_job_id), canonical_id)
                if pending_job_id is not None
                else canonical_id
            )
            union_ids = list(dict.fromkeys(chunk_ids))

        relation_obj = Relation(
            id=rel_id,
            type=rel_type,
            source_id=src_id,
            target_id=tgt_id,
            source_chunk_ids=union_ids,
        )
        record = relation_obj.to_relation_record()
        if canonical_id is not None and pending_job_id is not None:
            record.properties["_canonical_id"] = str(canonical_id)
        relation_records.append(record)
    dropped = [
        *(
            DroppedCount(
                kind="relation", label=label, reason="unmapped_endpoint", count=count
            )
            for label, count in sorted(unmapped.items())
        ),
        *(
            DroppedCount(
                kind="relation", label=label, reason="merged_self_loop", count=count
            )
            for label, count in sorted(self_loops.items())
        ),
    ]
    return relation_records, dropped


async def _mentioned_in_records(
    entities: list[ExtractedEntity],
    mention_to_entity: dict[int, UUID],
    *,
    graph_store: GraphStore,
    error_policy: ErrorPolicy,
    failures: list[StageFailure],
) -> list[RelationRecord]:
    """Build one MENTIONED_IN edge per real mention, reusing stored edge ids."""
    # One edge per (chunk, entity) pair, for real mentions only. Synthetic
    # persisted-candidate indices (>= len(entities)) carry no chunk evidence
    # from this call: their chunks were never written.
    mentioned_pairs: set[tuple[UUID, UUID]] = set()
    for idx, entity_id in mention_to_entity.items():
        if idx >= len(entities):
            continue
        mentioned_pairs.add((entities[idx].chunk_id, entity_id))

    # Look up by endpoint rather than trusting mentioned_in_id() alone,
    # so an edge whose stored id differs from the recomputed one is
    # found instead of duplicated on re-ingest.
    existing_mentioned_map = await _global_relation_lookup(
        [
            (chunk_id, entity_id, "MENTIONED_IN")
            for chunk_id, entity_id in mentioned_pairs
        ],
        graph_store=graph_store,
        error_policy=error_policy,
        failures=failures,
    )

    mentioned_in_records: list[RelationRecord] = []
    for chunk_id, entity_id in mentioned_pairs:
        existing = existing_mentioned_map.get((chunk_id, entity_id, "MENTIONED_IN"))
        edge_id = (
            existing[0]
            if existing is not None
            else mentioned_in_id(chunk_id, entity_id)
        )
        mentioned_in_records.append(
            RelationRecord(
                id=edge_id,
                type="MENTIONED_IN",
                start_id=chunk_id,
                end_id=entity_id,
                properties={"created_at": datetime.now().isoformat()},
            )
        )
    return mentioned_in_records


async def _global_relation_lookup(
    triples: list[tuple[UUID, UUID, str]],
    *,
    graph_store: GraphStore,
    error_policy: ErrorPolicy,
    failures: list[StageFailure],
    job_id: UUID | str | None = None,
) -> dict[tuple[UUID, UUID, str], tuple[UUID, list[UUID]]]:
    """Return each triple's already-persisted relation id and source_chunk_ids.

    One batched read per distinct relation type present in triples. When a
    type's read or row parsing fails, the failure is appended to ``failures``
    and that type's triples are left out of the result, so they are treated as
    new relations.

    Args:
        triples: The (source_id, target_id, type) triples to look up.
        graph_store: Where the lookup runs.
        error_policy: ``RAISE`` propagates a failed read or parse. Any other
            policy records it and continues.
        failures: Receives one failure per relation type whose lookup failed.
        job_id: The active job whose pending relations are visible.

    Returns:
        A map from triple to its existing relation's (id, source_chunk_ids).
    """
    if not triples:
        return {}
    by_type: dict[str, list[tuple[UUID, UUID]]] = defaultdict(list)
    for src, tgt, typ in triples:
        by_type[typ].append((src, tgt))

    result: dict[tuple[UUID, UUID, str], tuple[UUID, list[UUID]]] = {}
    for rel_type, pairs in by_type.items():
        unique_pairs = list(dict.fromkeys(pairs))
        params = [{"source_id": str(s), "target_id": str(t)} for s, t in unique_pairs]
        query = fetch_relations_between_query(
            rel_type, job_id="job_id" if job_id is not None else None
        )
        read_params: dict[str, object] = {"pairs": params}
        if job_id is not None:
            read_params["job_id"] = str(job_id)
        try:
            rows = await graph_store.execute_read(query, read_params)
            type_result: dict[tuple[UUID, UUID, str], tuple[UUID, list[UUID]]] = {}
            for row in rows:
                src = UUID(str(row["source_id"]))
                tgt = UUID(str(row["target_id"]))
                rel_id = UUID(str(row["id"]))
                raw_scids = row.get("source_chunk_ids") or []
                scids = [UUID(str(x)) for x in raw_scids]
                type_result[(src, tgt, rel_type)] = (rel_id, scids)
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            trace_id, span_id = record_stage_failure(exc)
            failures.append(
                StageFailure(
                    item_id=rel_type,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    trace_id=trace_id,
                    span_id=span_id,
                )
            )
            continue
        result.update(type_result)
    return result
