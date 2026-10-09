"""The post-commit work of a Cutover Job.

``finish_job`` is the one definition of what a job does after it commits. The
live calls run it right after the commit and crash recovery runs it for a
job that died after its commit, so both leave the same graph.
"""

import contextlib
from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.stage_failure import StageFailure
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion._ingest_pipeline import _delete_vectors
from agrag.ingestion.resolved_embeddings import _synchronize_resolved_entity_vectors
from agrag.ingestion.resolved_entities import (
    prune_orphaned_entities,
    rebuild_resolved_entities,
)
from agrag.loaders.types import ErrorPolicy
from agrag.observability import record_stage_failure
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


async def finish_job(
    affected_entity_ids: list[UUID],
    component_seed_ids: list[UUID],
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    embedder: Embedder,
    vector_store: VectorStore | None,
    retrieval_settings: RetrievalSettings,
    tracer: Tracer,
    error_policy: ErrorPolicy = ErrorPolicy.RAISE,
) -> list[StageFailure]:
    """Run the cleanup phase of one committed Cutover Job.

    A pending job never deletes the resolved entity it supersedes, so
    after the commit this rebuilds the resolved entity of each component
    the job rebuilt, then prunes the entities that lost their last
    evidence. The live calls and crash recovery both run it, with the
    lists the job recorded. Running it again changes nothing.

    Args:
        affected_entity_ids: Entities that may have lost their last
            evidence; the only ones pruning may remove.
        component_seed_ids: One member id per component to rebuild.
        graph_store: The store the job wrote to.
        schema: The graph schema.
        embedder: Embeds rebuilt resolved entities.
        vector_store: The optional second write target for embeddings.
        retrieval_settings: Collection names for the VectorStore writes.
        tracer: A tracer to record spans.
        error_policy: RAISE propagates the first failure; any other
            policy records it and continues. Recovery uses RAISE, so a
            failure leaves the job in ``cleaning`` for a later open.

    Returns:
        The failures recorded while rebuilding components.
    """
    failures = await rebuild_seeded_components(
        component_seed_ids,
        graph_store=graph_store,
        schema=schema,
        embedder=embedder,
        vector_store=vector_store,
        retrieval_settings=retrieval_settings,
        tracer=tracer,
        error_policy=error_policy,
    )
    await prune_document_entities(
        affected_entity_ids,
        graph_store=graph_store,
        schema=schema,
        vector_store=vector_store,
        retrieval_settings=retrieval_settings,
        tracer=tracer,
    )
    return failures


async def rebuild_seeded_components(
    component_seed_ids: list[UUID],
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    embedder: Embedder,
    vector_store: VectorStore | None,
    retrieval_settings: RetrievalSettings,
    tracer: Tracer,
    error_policy: ErrorPolicy,
) -> list[StageFailure]:
    """Rebuild committed components' resolved entities and sync vectors.

    The replaced resolved entities' vectors are deleted and the new ones
    written to the graph and the external vector store. Persisted vector
    deletions from earlier passes are retried even when no seed is given.

    Args:
        component_seed_ids: One member id per component to rebuild.
        graph_store: The store the job wrote to.
        schema: The graph schema.
        embedder: Embeds rebuilt resolved entities.
        vector_store: The optional second write target for embeddings.
        retrieval_settings: Collection names for the VectorStore writes.
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
        replaced_ids: list[UUID] = []
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
                    replaced_ids.extend(result.removed_entity_ids)
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
        return failures


async def prune_document_entities(
    candidates: list[UUID],
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    vector_store: VectorStore | None,
    retrieval_settings: RetrievalSettings,
    tracer: Tracer,
) -> None:
    """Prune orphaned candidates and drop their stale vectors.

    Best effort: a vector-store failure never fails the document
    operation that already committed its graph writes.

    Args:
        candidates: Entity ids that may have lost their last evidence.
            Empty skips the pruning pass entirely.
        graph_store: The store the job wrote to.
        schema: The graph schema.
        vector_store: The optional second write target for embeddings.
        retrieval_settings: Collection names for the VectorStore writes.
        tracer: A tracer to record spans.
    """
    if not candidates:
        return
    pruning = await prune_orphaned_entities(
        candidates,
        graph_store=graph_store,
        schema=schema,
        tracer=tracer,
    )
    with contextlib.suppress(Exception):
        await _delete_vectors(
            vector_store,
            retrieval_settings.entity_collection,
            pruning.removed_entity_ids,
        )
    with contextlib.suppress(Exception):
        await _delete_vectors(
            vector_store,
            retrieval_settings.resolved_entity_collection,
            pruning.removed_resolved_entity_ids,
        )
