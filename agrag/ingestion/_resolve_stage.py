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
    max_llm_pairs: int,
) -> ResolveStageResult:
    """Resolve the batch's mentions and count what the resolver decided.

    Args:
        entities: The mentions extracted from this batch's chunks.
        relations: The relations extracted from this batch's chunks.
        chunks: The chunks of this batch, used as context for the resolver.
        ctx: The store that holds persisted candidates, the embedder, the
            error policy, the job and the tracer.
        graph_schema: The schema whose entity labels scope the resolver.
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
        entity_labels=[entity.label for entity in graph_schema.entities],
        tracer=ctx.tracer,
        max_llm_pairs=max_llm_pairs,
        error_policy=ctx.error_policy,
        job_id=ctx.job_id,
    )
    result = batch.result
    in_batch_groups = (
        sum(
            1
            for group in result.groups
            if sum(index < len(entities) for index in group.entity_indices) >= 2
        )
        if result is not None
        else 0
    )
    stats = ResolutionStats(
        exact_match_hits=len(batch.exact_matches),
        in_batch_groups=in_batch_groups,
        ambiguous_count=result.ambiguous_count if result is not None else 0,
        failed_llm_requests=result.failed_llm_requests if result is not None else 0,
        cap_truncated_pairs=result.cap_truncated_pairs if result is not None else 0,
        llm_unavailable_pairs=(
            result.llm_unavailable_pairs if result is not None else 0
        ),
    )
    return ResolveStageResult(batch=batch, stats=stats)
