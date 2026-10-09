"""Maintenance of persisted entity matches: consolidate, reevaluate, deactivate.

These calls rewrite MATCHES edges and the resolved entities derived from
them, outside any Cutover Job.
"""

from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.stage_failure import StageFailure
from agrag.common.text import normalize_text
from agrag.cypher.entities import fetch_all_by_label_query
from agrag.cypher.resolution_read import fetch_active_matches_among_ids_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.graphdb.entities import load_entities
from agrag.graphdb.serialize import parse_entity_node
from agrag.ingestion.reports import ConsolidationReport, ReevaluationReport
from agrag.ingestion.resolve import resolve_among, resolve_persisted
from agrag.ingestion.resolved_embeddings import _synchronize_resolved_entity_vectors
from agrag.ingestion.resolved_entities import (
    MatchComponent,
    MatchDecision,
    deactivate_match_and_rebuild,
    match_decision_components,
    matches_id,
    write_matches_and_rebuild,
)
from agrag.loaders.types import ErrorPolicy
from agrag.observability import record_stage_failure
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


async def all_entities_by_label(graph_store: GraphStore, label: str) -> list[Entity]:
    """Return every persisted entity with label, for consolidate().

    Plain pagination through GraphStore.

    Args:
        graph_store: The store to read from.
        label: The entity label to fetch.

    Returns:
        All entities with that label.
    """
    entities: list[Entity] = []
    skip = 0
    limit = 256
    while True:
        query = fetch_all_by_label_query(label)
        rows = await graph_store.execute_read(query, {"skip": skip, "limit": limit})
        if not rows:
            break
        for row in rows:
            ent = parse_entity_node(row.get("n"))
            if ent is not None:
                entities.append(ent)
        if len(rows) < limit:
            break
        skip += limit
    return entities


async def load_input_entities(
    graph_store: GraphStore, unique_ids: list[UUID], *, tracer: Tracer
) -> list[Entity]:
    """Fetch live entities for the given ids, preserving input order.

    Args:
        graph_store: The store to read from.
        unique_ids: Deduped entity ids to fetch.
        tracer: A tracer to record spans.

    Returns:
        The live entities in input order.

    Raises:
        ValueError: An id has no live persisted entity.
    """
    entities_by_id = await load_entities(graph_store, unique_ids, tracer=tracer)
    missing = [e for e in unique_ids if e not in entities_by_id]
    if missing:
        raise ValueError("Unknown entity ids: " + ", ".join(str(m) for m in missing))
    return [entities_by_id[e] for e in unique_ids]


async def write_and_rebuild_components(
    components: list[MatchComponent],
    *,
    schema: GraphSchema,
    graph_store: GraphStore,
    embedder: Embedder,
    vector_store: VectorStore | None,
    retrieval_settings: RetrievalSettings,
    tracer: Tracer,
    error_policy: ErrorPolicy,
) -> tuple[list[ResolvedEntity], list[StageFailure]]:
    """Rebuild committed match components and sync their vectors.

    Runs outside any Cutover Job, so each write replaces the previous
    rebuild of the components it grows or merges, including its
    ``RESOLVED_AS`` edges. The replaced vectors are then deleted and the
    new ones written to the graph and the external vector store.

    Args:
        components: The match decisions and raw members of each
            component to rebuild.
        schema: The graph schema.
        graph_store: The store the matches live in.
        embedder: Embeds rebuilt resolved entities.
        vector_store: The optional second write target for embeddings.
        retrieval_settings: Collection names for the VectorStore writes.
        tracer: A tracer to record spans.
        error_policy: RAISE propagates the first failure; any other
            policy records it and continues.

    Returns:
        The resolved-entities and the recorded failures.
    """
    with tracer.start_as_current_span(
        "agrag.merge.rebuild_components",
        attributes={"agrag.component_count": len(components)},
    ):
        failures: list[StageFailure] = []
        rebuilt: list[ResolvedEntity] = []
        replaced_ids: list[UUID] = []
        for decisions, members in components:
            with tracer.start_as_current_span(
                "agrag.merge.rebuild_component",
                attributes={"agrag.member_count": len(members)},
            ):
                try:
                    rebuild = await write_matches_and_rebuild(
                        decisions,
                        graph_store=graph_store,
                        schema=schema,
                        members=members,
                        tracer=tracer,
                    )
                except Exception as exc:  # noqa: BLE001
                    if error_policy is ErrorPolicy.RAISE:
                        raise
                    trace_id, span_id = record_stage_failure(exc)
                    failures.append(
                        StageFailure(
                            item_id=",".join(str(member.id) for member in members),
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                            trace_id=trace_id,
                            span_id=span_id,
                        )
                    )
                    continue
            rebuilt.append(rebuild.resolved_entity)
            replaced_ids.extend(rebuild.removed_entity_ids)
        failures.extend(
            await _synchronize_resolved_entity_vectors(
                rebuilt,
                replaced_ids,
                embedder=embedder,
                graph_store=graph_store,
                vector_store=vector_store,
                vector_collection=retrieval_settings.resolved_entity_collection,
                error_policy=error_policy,
            )
        )
        return rebuilt, failures


async def deactivate_match(
    match_id: UUID,
    *,
    schema: GraphSchema,
    graph_store: GraphStore,
    embedder: Embedder,
    vector_store: VectorStore | None,
    retrieval_settings: RetrievalSettings,
    tracer: Tracer,
) -> list[ResolvedEntity]:
    """Deactivate a semantic match and synchronize replacement retrieval vectors."""
    with tracer.start_as_current_span(
        "agrag.ingestion.deactivate_match",
        attributes={"agrag.match_id": str(match_id)},
    ):
        result = await deactivate_match_and_rebuild(
            match_id,
            graph_store=graph_store,
            schema=schema,
            tracer=tracer,
        )
        await _synchronize_resolved_entity_vectors(
            result.resolved_entities,
            result.removed_entity_ids,
            embedder=embedder,
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collection=retrieval_settings.resolved_entity_collection,
            error_policy=ErrorPolicy.RAISE,
        )
        return result.resolved_entities


async def consolidate(
    *,
    apply: bool,
    schema: GraphSchema,
    graph_store: GraphStore,
    embedder: Embedder,
    vector_store: VectorStore | None,
    retrieval_settings: RetrievalSettings,
    tracer: Tracer,
    max_llm_pairs: int,
) -> ConsolidationReport:
    """Run resolution against every persisted entity. See ``Graph.consolidate``."""
    with tracer.start_as_current_span("agrag.ingestion.consolidate"):
        would_match: list[MatchDecision] = []
        ambiguous_count = 0
        entities_by_id: dict[UUID, Entity] = {}
        candidate_read_failures: list[StageFailure] = []
        # For each label, fetch all entities, then pairwise compare via Resolver
        for entity_type in schema.entities:
            label = entity_type.label
            all_entities = await all_entities_by_label(graph_store, label)
            if len(all_entities) < 2:
                continue
            resolution_result, candidate_failures = await resolve_persisted(
                all_entities,
                graph_store=graph_store,
                embedder=embedder,
                vector_store=vector_store,
                vector_collection=retrieval_settings.entity_collection,
                entity_labels=[entity.label for entity in schema.entities],
                tracer=tracer,
                max_llm_pairs=max_llm_pairs,
                error_policy=ErrorPolicy.SKIP,
            )
            candidate_read_failures.extend(candidate_failures)
            ambiguous_count += resolution_result.ambiguous_count
            entities_by_id.update({entity.id: entity for entity in all_entities})
            for match in resolution_result.matches:
                would_match.append(
                    MatchDecision(
                        entity_a_id=all_entities[match.left_index].id,
                        entity_b_id=all_entities[match.right_index].id,
                        comparator=match.comparator,
                        score=match.score,
                        reasoning=match.reasoning,
                        decided_at=match.decided_at,
                    )
                )

        consolidation_failures: list[StageFailure] = list(candidate_read_failures)
        rebuilt_entities: list[ResolvedEntity] = []
        if apply:
            components: list[MatchComponent] = []
            for decisions in match_decision_components(would_match):
                member_ids = {decision.entity_a_id for decision in decisions} | {
                    decision.entity_b_id for decision in decisions
                }
                components.append(
                    (
                        decisions,
                        [entities_by_id[member_id] for member_id in member_ids],
                    )
                )
            (
                rebuilt_entities,
                rebuild_failures,
            ) = await write_and_rebuild_components(
                components,
                schema=schema,
                graph_store=graph_store,
                embedder=embedder,
                vector_store=vector_store,
                retrieval_settings=retrieval_settings,
                tracer=tracer,
                error_policy=ErrorPolicy.SKIP,
            )
            consolidation_failures.extend(rebuild_failures)

        return ConsolidationReport(
            would_match=would_match,
            applied=apply and bool(rebuilt_entities),
            failures=consolidation_failures,
            ambiguous_count=ambiguous_count,
        )


async def reevaluate(
    entity_ids: list[UUID],
    *,
    schema: GraphSchema,
    graph_store: GraphStore,
    embedder: Embedder,
    vector_store: VectorStore | None,
    retrieval_settings: RetrievalSettings,
    tracer: Tracer,
    max_llm_pairs: int,
) -> ReevaluationReport:
    """Reevaluate matches among the given entities. See ``Graph.reevaluate``."""
    with tracer.start_as_current_span(
        "agrag.ingestion.reevaluate",
        attributes={"agrag.entity_count": len(entity_ids)},
    ):
        unique_ids = list(dict.fromkeys(entity_ids))
        if not unique_ids:
            return ReevaluationReport()
        entities_by_id = {
            entity.id: entity
            for entity in await load_input_entities(
                graph_store, unique_ids, tracer=tracer
            )
        }
        entities = [entities_by_id[e] for e in unique_ids]
        resolution = await resolve_among(
            entities,
            embedder=embedder,
            tracer=tracer,
            max_llm_pairs=max_llm_pairs,
        )
        confirmed = {
            frozenset((unique_ids[m.left_index], unique_ids[m.right_index])): m
            for m in resolution.matches
        }
        exact_pairs = {
            frozenset((unique_ids[left], unique_ids[right]))
            for left in range(len(entities))
            for right in range(left + 1, len(entities))
            if normalize_text(entities[left].name)
            == normalize_text(entities[right].name)
        }
        edge_rows = await graph_store.execute_read(
            fetch_active_matches_among_ids_query(),
            {"ids": [str(e) for e in unique_ids], "job_id": None},
        )
        active: dict[frozenset[UUID], UUID] = {}
        for row in edge_rows:
            if not isinstance(row, dict):
                continue
            try:
                pair = frozenset((UUID(str(row["a_id"])), UUID(str(row["b_id"]))))
                match_id = UUID(str(row["match_id"]))
            except (KeyError, TypeError, ValueError):
                continue
            if len(pair) == 2:
                active.setdefault(pair, match_id)
        decisions = sorted(
            (
                MatchDecision(
                    entity_a_id=first,
                    entity_b_id=second,
                    comparator=match.comparator,
                    score=match.score,
                    reasoning=match.reasoning,
                    decided_at=match.decided_at,
                )
                for pair, match in confirmed.items()
                if pair not in active
                for first, second in (sorted(pair, key=str),)
            ),
            key=lambda d: str(matches_id(d.entity_a_id, d.entity_b_id)),
        )
        rebuilt: list[ResolvedEntity] = []
        replaced: list[UUID] = []
        matches_added: list[MatchDecision] = []
        for component in match_decision_components(decisions):
            member_ids = {d.entity_a_id for d in component} | {
                d.entity_b_id for d in component
            }
            with tracer.start_as_current_span(
                "agrag.merge.rebuild_component",
                attributes={"agrag.member_count": len(member_ids)},
            ):
                rebuild = await write_matches_and_rebuild(
                    component,
                    graph_store=graph_store,
                    schema=schema,
                    members=[entities_by_id[m] for m in member_ids],
                    tracer=tracer,
                )
            rebuilt.append(rebuild.resolved_entity)
            replaced.extend(rebuild.removed_entity_ids)
            matches_added.extend(component)
        matches_removed: list[UUID] = []
        removed_pairs: set[frozenset[UUID]] = set()
        for pair, match_id in sorted(active.items(), key=lambda item: str(item[1])):
            if pair in confirmed or pair in exact_pairs:
                continue
            with tracer.start_as_current_span(
                "agrag.merge.deactivate_component",
                attributes={"agrag.match_id": str(match_id)},
            ):
                deactivation = await deactivate_match_and_rebuild(
                    match_id,
                    graph_store=graph_store,
                    schema=schema,
                    tracer=tracer,
                )
            rebuilt.extend(deactivation.resolved_entities)
            replaced.extend(deactivation.removed_entity_ids)
            matches_removed.append(match_id)
            removed_pairs.add(pair)
        await _synchronize_resolved_entity_vectors(
            rebuilt,
            list(dict.fromkeys(replaced)),
            embedder=embedder,
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collection=retrieval_settings.resolved_entity_collection,
            error_policy=ErrorPolicy.SKIP,
        )
        touched = {e for d in matches_added for e in (d.entity_a_id, d.entity_b_id)}
        touched |= {e for pair in removed_pairs for e in pair}
        return ReevaluationReport(
            entities_reevaluated=unique_ids,
            matches_added=matches_added,
            matches_removed=matches_removed,
            unchanged_count=sum(1 for e in unique_ids if e not in touched),
        )
