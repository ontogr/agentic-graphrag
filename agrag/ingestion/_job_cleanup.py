"""The post-commit work of a Cutover Job.

``finish_job`` is the one definition of what a job does after it commits. The
live calls run it right after the commit and crash recovery runs it for a
job that died after its commit, so both leave the same graph.
"""

from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.stage_failure import StageFailure
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion._resolution_maintenance import reconcile_created_entities
from agrag.ingestion.resolved_embeddings import embed_resolved_entities
from agrag.ingestion.resolved_entities import (
    prune_orphaned_entities,
    rebuild_resolved_entities,
)
from agrag.loaders.types import ErrorPolicy
from agrag.observability import record_stage_failure


async def finish_job(
    affected_entity_ids: list[UUID],
    component_seed_ids: list[UUID],
    created_entity_ids: list[UUID],
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    embedder: Embedder,
    tracer: Tracer,
    max_llm_pairs: int,
    error_policy: ErrorPolicy = ErrorPolicy.RAISE,
) -> list[StageFailure]:
    """Run the cleanup phase of one committed Cutover Job.

    A pending job never deletes the resolved entity it supersedes, so
    after the commit this rebuilds the resolved entity of each component
    the job rebuilt, resolves the entities the job created against
    everything committed since, then prunes the entities that lost their
    last evidence. The live calls and crash recovery both run it, with the
    lists the job recorded. Running it again changes nothing.

    Args:
        affected_entity_ids: Entities that may have lost their last
            evidence; the only ones pruning may remove.
        component_seed_ids: One member id per component to rebuild.
        created_entity_ids: Entities the job created, to resolve against
            the committed graph. A failure here is recorded, never raised.
        graph_store: The store the job wrote to.
        schema: The graph schema.
        embedder: Embeds rebuilt resolved entities.
        tracer: A tracer to record spans.
        max_llm_pairs: The most ambiguous pairs per label sent to the LLM.
        error_policy: RAISE propagates the first failure; any other
            policy records it and continues. Recovery uses RAISE, so a
            failure leaves the job in ``cleaning`` for a later open.

    Returns:
        The failures recorded while rebuilding and reconciling.
    """
    failures = await rebuild_seeded_components(
        component_seed_ids,
        graph_store=graph_store,
        schema=schema,
        embedder=embedder,
        tracer=tracer,
        error_policy=error_policy,
    )
    failures.extend(
        await reconcile_created_entities(
            created_entity_ids,
            schema=schema,
            graph_store=graph_store,
            embedder=embedder,
            tracer=tracer,
            max_llm_pairs=max_llm_pairs,
        )
    )
    await prune_document_entities(
        affected_entity_ids,
        graph_store=graph_store,
        schema=schema,
        tracer=tracer,
    )
    return failures


async def rebuild_seeded_components(
    component_seed_ids: list[UUID],
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    embedder: Embedder,
    tracer: Tracer,
    error_policy: ErrorPolicy,
) -> list[StageFailure]:
    """Rebuild committed components' resolved entities and embed them.

    Args:
        component_seed_ids: One member id per component to rebuild.
        graph_store: The store the job wrote to.
        schema: The graph schema.
        embedder: Embeds rebuilt resolved entities.
        tracer: A tracer to record spans.
        error_policy: RAISE propagates the first failure; any other
            policy records it and continues.

    Returns:
        The recorded failures.
    """
    with tracer.start_as_current_span(
        "agrag.merge.rebuild_components",
        attributes={"agrag.component_count": len(component_seed_ids)},
    ):
        failures: list[StageFailure] = []
        rebuilt: list[ResolvedEntity] = []
        for seed_id in component_seed_ids:
            with tracer.start_as_current_span("agrag.merge.rebuild_component") as span:
                try:
                    results = await rebuild_resolved_entities(
                        [seed_id],
                        graph_store=graph_store,
                        schema=schema,
                        tracer=tracer,
                    )
                except Exception as exc:  # noqa: BLE001
                    if error_policy is ErrorPolicy.RAISE:
                        raise
                    trace_id, span_id = record_stage_failure(exc)
                    failures.append(
                        StageFailure(
                            item_id=str(seed_id),
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                            trace_id=trace_id,
                            span_id=span_id,
                        )
                    )
                    continue
                for result in results:
                    span.set_attribute(
                        "agrag.member_count", len(result.resolved_entity.member_ids)
                    )
                    rebuilt.append(result.resolved_entity)
        failures.extend(
            await embed_resolved_entities(
                rebuilt,
                embedder=embedder,
                graph_store=graph_store,
                error_policy=error_policy,
            )
        )
        return failures


async def prune_document_entities(
    candidates: list[UUID],
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    tracer: Tracer,
) -> None:
    """Prune entities that lost their last evidence.

    Args:
        candidates: Entity ids that may have lost their last evidence.
            Empty skips the pruning pass entirely.
        graph_store: The store the job wrote to.
        schema: The graph schema.
        tracer: A tracer to record spans.
    """
    if not candidates:
        return
    await prune_orphaned_entities(
        candidates,
        graph_store=graph_store,
        schema=schema,
        tracer=tracer,
    )
