"""Entity resolution stage of one ingestion batch.

The stage matches the batch's mentions against each other and against the
entities already in the graph. Its output feeds the merge stage.
"""

from dataclasses import dataclass

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.ingestion._stage_context import StageContext
from agrag.ingestion.resolve import resolve_batch
from agrag.ingestion.resolve.resolution import BatchResolution
from agrag.ingestion.stats import ResolutionStats
from agrag.retrieval.settings import RetrievalSettings


@dataclass(frozen=True)
class ResolveStageResult:
    """The resolver output for one batch and the stats derived from it.

    Attributes:
        batch: The matches, groups and failures the merge stage consumes.
        stats: The resolution counts reported in the AddResult.
    """

    batch: BatchResolution
    stats: ResolutionStats


async def resolve_stage(
    entities: list[ExtractedEntity],
    relations: list[ExtractedRelation],
    chunks: list[Chunk],
    ctx: StageContext,
    *,
    graph_schema: GraphSchema,
    retrieval_settings: RetrievalSettings,
    max_llm_pairs: int,
) -> ResolveStageResult:
    """Resolve the batch's mentions and count what the resolver decided.

    Args:
        entities: The mentions extracted from this batch's chunks.
        relations: The relations extracted from this batch's chunks.
        chunks: The chunks of this batch, used as context for the resolver.
        ctx: The store that holds persisted candidates, the embedder, the
            optional vector index, the error policy, the job and the tracer.
        graph_schema: The schema whose entity labels scope the resolver.
        retrieval_settings: Names the entity collection to search.
        max_llm_pairs: The cap on LLM verifications for this batch.

    Returns:
        The resolver output and its counts.
    """
    chunks_by_id = {chunk.id: chunk for chunk in chunks if chunk.id is not None}
    batch = await resolve_batch(
        entities,
        relations,
        chunks_by_id,
        graph_store=ctx.graph_store,
        embedder=ctx.embedder,
        vector_store=ctx.vector_store,
        vector_collection=retrieval_settings.entity_collection,
        entity_labels=[entity.label for entity in graph_schema.entities],
        tracer=ctx.tracer,
        max_llm_pairs=max_llm_pairs,
        error_policy=ctx.error_policy,
        job_id=ctx.job_id,
    )
    # Groups over the combined list include synthetic singletons, so only groups
    # holding a real mention count.
    semantic_groups = batch.result.groups if batch.result is not None else []
    stats = ResolutionStats(
        exact_match_hits=len(batch.exact_matches),
        in_batch_groups=sum(
            1
            for group in semantic_groups
            if any(index < len(entities) for index in group.entity_indices)
        ),
        ambiguous_count=(
            batch.result.ambiguous_count if batch.result is not None else 0
        ),
    )
    return ResolveStageResult(batch=batch, stats=stats)
