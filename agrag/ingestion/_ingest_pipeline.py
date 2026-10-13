"""Shared per-batch ingestion core for ``Graph.add()`` and ``Graph.update()``.

This module is internal. It owns the extract-resolve-merge-write pipeline
that runs over already-chunked input, with every dependency passed
explicitly rather than read from ``Graph``. ``Graph.add()`` calls
``ingest_chunks`` once per call after its own walk/chunk loop;
``Graph.update()`` calls it directly for the fresh-content case. This
module has no ``Graph`` import and cannot reach into ``Graph``'s private
state.
"""

import asyncio
import contextlib
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from opentelemetry.trace import Tracer
from pydantic import BaseModel, ConfigDict

from agrag.chunking.chunker import ChunkPlacement
from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_record import DeferredWrites
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.stage_failure import StageFailure, cap_failures
from agrag.common.data_models.vector_record import VectorRecord
from agrag.common.graph_rows import node_properties, row_node
from agrag.cypher.entities import (
    clear_chunk_embedding_query,
    clear_property_query,
    load_chunks_by_id_query,
    set_chunk_embedding_query,
    set_embedding_query,
)
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion._deferred import write_or_defer
from agrag.ingestion._escalation import (
    accept_escalated,
    combine_results,
    kept_entities,
    labels_with_properties,
    plan_escalation,
)
from agrag.ingestion._merge_stage import MergeStageResult, merge_stage
from agrag.ingestion._resolve_stage import resolve_stage
from agrag.ingestion._stage_context import StageContext
from agrag.ingestion._storage import (
    WriteOutcome,
    write_nodes_stage,
    write_relations_stage,
)
from agrag.ingestion.extract import Extractor, LLMExtractor, validate_extraction
from agrag.ingestion.reports import AddResult
from agrag.ingestion.reports.escalation_report import EscalationReport
from agrag.ingestion.resolve.zone_classifier import MAX_LLM_PAIRS
from agrag.ingestion.resolved_entities import MatchComponent
from agrag.ingestion.settings import ExtractionSettings, effective_mode
from agrag.ingestion.stats import (
    ExtractionStats,
    IngestStats,
    MergeStats,
    ResolutionStats,
    StorageStats,
)
from agrag.loaders.types import ErrorPolicy
from agrag.observability import (
    get_tracer,
    record_stage_failure,
)
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


async def _run_extractor(
    chunks: Sequence[Chunk],
    *,
    extractor: Extractor | LLMExtractor,
    schema: GraphSchema,
    raise_errors: bool,
    tracer: Tracer,
    phase: str,
    candidates: Sequence[Sequence[ExtractedEntity]] | None = None,
) -> list[ExtractionResult | StageFailure]:
    """Run one extractor over chunks, keeping its own concurrency limit.

    Args:
        chunks: The chunks to read.
        extractor: The extractor to call. The first phase passes an
            ``Extractor``. The LLM phase passes an ``LLMExtractor``. Its
            ``max_concurrency`` sets the semaphore, so a phase never runs more
            calls than its extractor allows.
        schema: The schema to extract against.
        raise_errors: ``True`` raises the first error and cancels the other
            calls. ``False`` turns each error into a ``StageFailure``.
        tracer: The tracer for the per-chunk spans.
        phase: ``"primary"`` or ``"escalation"``, recorded on each span.
        candidates: For the escalation phase, the kept first-phase entities of
            each chunk, in the order of ``chunks``. Only an ``LLMExtractor``
            receives them. ``None`` calls every extractor with ``(chunk, schema)``.

    Returns:
        One result or failure per chunk, in the order of ``chunks``.
    """
    semaphore = asyncio.Semaphore(extractor.max_concurrency or 8)

    async def _extract_one(
        chunk: Chunk, position: int
    ) -> ExtractionResult | StageFailure:
        async with semaphore:
            with tracer.start_as_current_span(
                "agrag.extraction.extract_chunk",
                attributes={
                    "agrag.chunk_id": str(chunk.id),
                    "agrag.extraction.phase": phase,
                },
            ) as span:
                try:
                    if candidates is not None and isinstance(extractor, LLMExtractor):
                        result = await extractor.extract(
                            chunk, schema, candidates=candidates[position]
                        )
                    else:
                        result = await extractor.extract(chunk, schema)
                    # Every extractor goes through the schema check, so an LLM
                    # label the schema does not declare never reaches the graph.
                    result = validate_extraction(result, schema)
                except Exception as exc:
                    if raise_errors:
                        raise
                    trace_id, span_id = record_stage_failure(exc)
                    return StageFailure(
                        item_id=str(chunk.id),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        trace_id=trace_id,
                        span_id=span_id,
                    )
                span.set_attribute("agrag.entities_extracted", len(result.entities))
                span.set_attribute("agrag.relations_extracted", len(result.relations))
                return result

    tasks = [
        asyncio.ensure_future(_extract_one(chunk, position))
        for position, chunk in enumerate(chunks)
    ]
    try:
        return list(await asyncio.gather(*tasks))
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


async def _escalate(
    chunks: list[Chunk],
    outcomes: list[ExtractionResult | StageFailure],
    *,
    llm_extractor: LLMExtractor,
    schema: GraphSchema,
    settings: ExtractionSettings,
    tracer: Tracer,
) -> tuple[list[ExtractionResult | StageFailure], list[StageFailure], EscalationReport]:
    """Run the LLM extractor on the weakest eligible chunks of a batch.

    The LLM extractor gets the kept entities of the first result as candidates.
    Used in ``hybrid`` only. An error in an LLM call never raises out of this
    function, whatever the error policy: the chunk already has a good first
    result, and one failed call must not discard the paid results of the other
    chunks. A chunk whose call raised, or whose answer parsed to no entities
    while the first result had some, keeps its first result and counts in
    ``failed``.

    Args:
        chunks: The chunks of the batch.
        outcomes: The first extractor's result or failure for each chunk.
        llm_extractor: The LLM extractor.
        schema: The schema to extract against.
        settings: The thresholds and the budget.
        tracer: The tracer for the batch span and the per-chunk spans.

    Returns:
        The outcomes with each accepted LLM result combined in, the failures of
        the LLM calls, and the batch report (``primary_seconds`` is left for
        the caller).
    """
    results = [o if isinstance(o, ExtractionResult) else None for o in outcomes]
    with tracer.start_as_current_span("agrag.extraction.escalate") as span:
        plan = plan_escalation(
            results,
            settings,
            chunks=chunks,
            property_labels=labels_with_properties(schema),
        )
        report = plan.report(len(chunks))
        span.set_attribute("agrag.chunks_total", report.total)
        span.set_attribute("agrag.chunks_eligible", report.eligible)
        span.set_attribute("agrag.chunks_escalated", report.escalated)
        if not plan.selected:
            return outcomes, [], report
        # Weakest first: with a limit below the batch size the weakest chunks
        # start first, so an interrupted run has spent its calls where they
        # matter most.
        started = time.perf_counter()
        escalated = await _run_extractor(
            [chunks[position] for position in plan.selected],
            extractor=llm_extractor,
            schema=schema,
            raise_errors=False,
            tracer=tracer,
            phase="escalation",
            candidates=[
                kept_entities(first, settings)
                if (first := results[position]) is not None
                else []
                for position in plan.selected
            ],
        )
        seconds = time.perf_counter() - started
        merged = list(outcomes)
        failures: list[StageFailure] = []
        failed = 0
        for position, outcome in zip(plan.selected, escalated, strict=True):
            first = results[position]
            if isinstance(outcome, StageFailure):
                failures.append(outcome)
                failed += 1
            elif first is not None:
                if accept_escalated(first, outcome):
                    merged[position] = validate_extraction(
                        combine_results(first, outcome), schema
                    )
                else:
                    failed += 1
        span.set_attribute("agrag.chunks_failed", failed)
    report = report.model_copy(update={"failed": failed, "escalation_seconds": seconds})
    return merged, failures, report


async def _extract_llm_only(
    chunks: list[Chunk],
    *,
    schema: GraphSchema,
    error_policy: ErrorPolicy,
    settings: ExtractionSettings,
    llm_extractor: LLMExtractor,
    tracer: Tracer,
) -> tuple[list[ExtractionResult | StageFailure], list[StageFailure], EscalationReport]:
    """Run the LLM extractor on every chunk long enough, with no candidates.

    Chunks under ``settings.min_escalation_words`` words are not sent. They get
    an empty result and count in ``skipped_short``. A failed call follows
    ``error_policy``: under ``RAISE`` the error propagates and the batch stops;
    under ``SKIP`` and ``QUARANTINE`` it becomes a ``StageFailure`` and counts
    in ``failed``. A parsed empty answer is a valid empty result.

    Args:
        chunks: The chunks of the batch.
        schema: The schema to extract against.
        error_policy: The run's error policy.
        settings: The minimum word count for a chunk to be sent.
        llm_extractor: The LLM extractor.
        tracer: The tracer for the per-chunk spans.

    Returns:
        One outcome per chunk in order, the failures of the LLM calls, and the
        batch report (``primary_seconds`` is left for the caller).
    """
    selected = [
        position
        for position, chunk in enumerate(chunks)
        if len(chunk.text.split()) >= settings.min_escalation_words
    ]
    started = time.perf_counter()
    answers = await _run_extractor(
        [chunks[position] for position in selected],
        extractor=llm_extractor,
        schema=schema,
        raise_errors=error_policy is ErrorPolicy.RAISE,
        tracer=tracer,
        phase="escalation",
    )
    seconds = time.perf_counter() - started
    outcomes: list[ExtractionResult | StageFailure] = [
        ExtractionResult(entities=[], relations=[], extractor_name="llm")
        for _ in chunks
    ]
    failures: list[StageFailure] = []
    for position, answer in zip(selected, answers, strict=True):
        if isinstance(answer, StageFailure):
            failures.append(answer)
        else:
            outcomes[position] = answer
    report = EscalationReport(
        mode="llm",
        total=len(chunks),
        skipped_short=len(chunks) - len(selected),
        escalated=len(selected),
        failed=len(failures),
        escalation_seconds=seconds,
    )
    return outcomes, failures, report


class ExtractionBatch(BaseModel):
    """What the extractors found in one batch of chunks.

    Attributes:
        entities: The mentions of every chunk that extracted, in chunk order.
        relations: The relations, with indices shifted by the batch offset.
        failures: One StageFailure per chunk, escalation call or relation that
            failed. The first extractor's failures come first.
        report: How the escalation tier treated the batch.
    """

    model_config = ConfigDict(frozen=True)

    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]
    failures: list[StageFailure]
    report: EscalationReport


async def extract_chunks(
    chunks: list[Chunk],
    *,
    start_index: int,
    extractor: Extractor | LLMExtractor,
    schema: GraphSchema,
    error_policy: ErrorPolicy,
    settings: ExtractionSettings,
    llm_extractor: LLMExtractor | None = None,
    tracer: Tracer | None = None,
) -> ExtractionBatch:
    """Extract a batch in the mode that the settings and the LLM slot resolve to.

    The mode comes from ``effective_mode``. In ``gliner`` the first extractor
    reads every chunk and nothing else runs. In ``hybrid`` the weakest eligible
    chunks then go to ``llm_extractor``, up to ``settings.escalation_budget`` of
    the batch, with the first result as candidates. In ``llm`` the first
    extractor is skipped, and every chunk with at least
    ``settings.min_escalation_words`` words goes to ``llm_extractor`` with no
    candidates. The budget and the threshold apply only in ``hybrid``.

    ``error_policy`` applies to the first extractor in ``gliner`` and
    ``hybrid``, and to the LLM extractor in ``llm``. In ``hybrid`` an error in
    the LLM extractor never raises: the chunk keeps its first result.

    The caller decides the batch: a walk batch for ``Graph.add`` and one
    document for ``Graph.update``.

    Args:
        chunks: The chunks of the batch.
        start_index: The entity index offset of this batch in the whole call.
        extractor: The first extractor, run on every chunk in ``gliner`` and
            ``hybrid``.
        schema: The schema to extract against.
        error_policy: How to treat a failed call of the extractor that the mode
            runs first (the first extractor, or the LLM extractor in ``llm``).
        settings: The mode, the escalation thresholds and the budget.
        llm_extractor: The LLM extractor, or ``None`` when the mode has no LLM.
        tracer: The tracer for the extraction spans.

    Returns:
        The batch: entities and relations in chunk order, the failures in phase
        order (first extractor, then LLM), and the report. The report names the
        effective mode and the time of each phase that ran.

    Raises:
        ValueError: If the settings mode is ``llm`` and ``llm_extractor`` is
            ``None``.
    """
    resolved_tracer = get_tracer(tracer)
    mode = effective_mode(settings, llm_available=llm_extractor is not None)
    escalation_failures: list[StageFailure] = []
    if mode == "llm":
        if llm_extractor is None:
            raise ValueError("extraction mode 'llm' needs an llm_extractor")
        outcomes, escalation_failures, report = await _extract_llm_only(
            chunks,
            schema=schema,
            error_policy=error_policy,
            settings=settings,
            llm_extractor=llm_extractor,
            tracer=resolved_tracer,
        )
        primary_seconds = 0.0
    else:
        started = time.perf_counter()
        outcomes = await _run_extractor(
            chunks,
            extractor=extractor,
            schema=schema,
            raise_errors=error_policy is ErrorPolicy.RAISE,
            tracer=resolved_tracer,
            phase="primary",
        )
        primary_seconds = time.perf_counter() - started
        report = EscalationReport(total=len(chunks))
        if llm_extractor is not None and mode == "hybrid":
            outcomes, escalation_failures, report = await _escalate(
                chunks,
                outcomes,
                llm_extractor=llm_extractor,
                schema=schema,
                settings=settings,
                tracer=resolved_tracer,
            )
    report = report.model_copy(
        update={"mode": mode, "primary_seconds": primary_seconds}
    )
    entities: list[ExtractedEntity] = []
    relations: list[ExtractedRelation] = []
    failures: list[StageFailure] = []
    for chunk, outcome in zip(chunks, outcomes, strict=True):
        if isinstance(outcome, StageFailure):
            failures.append(outcome)
            continue
        offset = start_index + len(entities)
        entities.extend(outcome.entities)
        for rel in outcome.relations:
            try:
                new_rel = ExtractedRelation(
                    chunk_id=rel.chunk_id,
                    label=rel.label,
                    source_index=rel.source_index + offset,
                    target_index=rel.target_index + offset,
                    confidence=rel.confidence,
                )
            except Exception as exc:  # noqa: BLE001
                if error_policy is ErrorPolicy.RAISE:
                    raise
                with resolved_tracer.start_as_current_span(
                    "agrag.extraction.remap_relations",
                    attributes={"agrag.chunk_id": str(chunk.id)},
                ):
                    trace_id, span_id = record_stage_failure(exc)
                failures.append(
                    StageFailure(
                        item_id=str(chunk.id),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        trace_id=trace_id,
                        span_id=span_id,
                    )
                )
                continue
            relations.append(new_rel)
    failures.extend(escalation_failures)
    return ExtractionBatch(
        entities=entities,
        relations=relations,
        failures=failures,
        report=report,
    )


@dataclass(frozen=True)
class EmbedStageResult:
    """The failures of one embedding stage.

    Attributes:
        failures: One StageFailure per embed or vector write that raised under
            an error policy other than RAISE.
    """

    failures: list[StageFailure]


@dataclass(frozen=True)
class BatchResult:
    """The stats of one batch and the structure nodes its write touched.

    Attributes:
        add_result: The stats of every stage of the batch.
        structure_node_ids: The Section, Table and Figure ids of the batch.
            A document update keeps these nodes when it closes the old version.
    """

    add_result: AddResult
    structure_node_ids: list[UUID]


async def embed_chunks_stage(
    chunks: list[Chunk],
    chunk_ids: set[UUID],
    chunk_writes: WriteOutcome,
    ctx: StageContext,
    *,
    vector_collection: str,
    embed_heading_path: bool,
) -> EmbedStageResult:
    """Embed the chunks of this batch that the graph holds, and write vectors.

    When the Chunk node write failed, upsert_nodes may still have committed its
    earlier batches. The stage then embeds whichever of this call's chunks the
    graph holds, so they do not stay unsearchable until the source is
    re-ingested.

    Args:
        chunks: The chunks of this batch.
        chunk_ids: The ids of the chunks this batch tried to write.
        chunk_writes: The outcome of the Chunk node write.
        ctx: The stores, embedder, error policy, job and tracer.
        vector_collection: The VectorStore collection to write into.
        embed_heading_path: Whether the embedder gets each heading path above
            the chunk text.

    Returns:
        The failures of the lookup, embed and vector writes.

    Raises:
        Exception: The lookup, embed or a write failed and the error policy is
            ``RAISE``.
    """
    embeddable_ids = chunk_ids - chunk_writes.failed_ids
    failures: list[StageFailure] = []
    if not chunk_writes.wrote_any:
        embeddable_ids, lookup_failures = await _persisted_chunk_ids(ctx, chunk_ids)
        failures.extend(lookup_failures)
    if not embeddable_ids:
        return EmbedStageResult(failures=failures)
    with ctx.tracer.start_as_current_span(
        "agrag.storage.embed_chunks",
        attributes={"agrag.embedding.heading_context": embed_heading_path},
    ):
        embed_failures = await _embed_and_upsert_chunks(
            [chunk for chunk in chunks if chunk.id in embeddable_ids],
            embedder=ctx.embedder,
            graph_store=ctx.graph_store,
            error_policy=ctx.error_policy,
            vector_store=ctx.vector_store,
            vector_collection=vector_collection,
            pending_job_id=ctx.job_id,
            deferred=ctx.deferred,
            embed_heading_path=embed_heading_path,
        )
    return EmbedStageResult(failures=[*failures, *embed_failures])


async def embed_survivors_stage(
    survivors: dict[UUID, Entity],
    ctx: StageContext,
    *,
    vector_collection: str,
) -> EmbedStageResult:
    """Refresh the embedding of each survivor that this batch merged.

    Args:
        survivors: The merged entities written by this call, keyed by id.
        ctx: The stores, embedder, error policy, job and tracer. The tracer
            opens its span only when there are survivors.
        vector_collection: The VectorStore collection to write into.

    Returns:
        The failures of the embed and vector writes.

    Raises:
        Exception: The embed or a write failed and the error policy is
            ``RAISE``.
    """
    if not survivors:
        return EmbedStageResult(failures=[])
    with ctx.tracer.start_as_current_span("agrag.storage.embed_survivors"):
        failures = await _embed_and_upsert_survivors(
            survivors,
            embedder=ctx.embedder,
            graph_store=ctx.graph_store,
            error_policy=ctx.error_policy,
            vector_store=ctx.vector_store,
            vector_collection=vector_collection,
            labels_by_id={ent.id: ent.label for ent in survivors.values()},
            pending_job_id=ctx.job_id,
            deferred=ctx.deferred,
        )
    return EmbedStageResult(failures=failures)


async def _resolve_and_merge(
    entities: list[ExtractedEntity],
    relations: list[ExtractedRelation],
    chunks: list[Chunk],
    ctx: StageContext,
    *,
    graph_schema: GraphSchema,
    retrieval_settings: RetrievalSettings,
    rebuilt_components: list[MatchComponent] | None,
    max_llm_pairs: int,
) -> tuple[ResolutionStats, MergeStageResult]:
    """Resolve and merge the mentions of a batch.

    A batch with no chunks has no mentions, so the resolver and the merge are
    skipped and their empty results are returned.
    """
    if not chunks:
        return ResolutionStats(), MergeStageResult(
            stats=MergeStats(),
            survivors={},
            resolved_vector_failures=[],
            relation_records=[],
            mentioned_in_records=[],
        )
    resolution = await resolve_stage(
        entities,
        relations,
        chunks,
        ctx,
        graph_schema=graph_schema,
        retrieval_settings=retrieval_settings,
        max_llm_pairs=max_llm_pairs,
    )
    merge = await merge_stage(
        entities,
        relations,
        resolution.batch,
        ctx,
        graph_schema=graph_schema,
        resolved_entity_collection=retrieval_settings.resolved_entity_collection,
        rebuilt_components=rebuilt_components,
    )
    return resolution.stats, merge


async def ingest_chunks(
    chunks: list[Chunk],
    documents: list[Document],
    entities: list[ExtractedEntity],
    relations: list[ExtractedRelation],
    extraction_failures: list[StageFailure],
    *,
    graph_store: GraphStore,
    embedder: Embedder,
    vector_store: VectorStore | None,
    graph_schema: GraphSchema,
    retrieval_settings: RetrievalSettings,
    error_policy: ErrorPolicy,
    ingestion: IngestStats,
    placements: Mapping[UUID, ChunkPlacement],
    return_chunks: bool = False,
    job_id: UUID | str | None = None,
    rebuilt_components: list[MatchComponent] | None = None,
    tracer: Tracer | None = None,
    embed_heading_path: bool = True,
    max_llm_pairs: int = MAX_LLM_PAIRS,
    deferred: DeferredWrites | None = None,
    reuse_chunks: bool = False,
) -> BatchResult:
    """Resolve, merge, write and embed one batch of extracted chunks.

    With ``reuse_chunks`` the chunks already exist in the graph and stay as
    they are. Only the Document node, entities, relations and MENTIONED_IN
    edges are written, and the chunks are not embedded again.

    Args:
        chunks: The chunks of this batch.
        documents: The documents the chunks belong to.
        entities: The mentions extracted from the chunks.
        relations: The relations extracted from the chunks.
        extraction_failures: Failures recorded before this stage.
        graph_store: The store every stage reads and writes.
        embedder: Embeds chunks, mentions and survivors.
        vector_store: Optional vector index mirrored by the embedding stages.
        graph_schema: The schema the resolver and merge work against.
        retrieval_settings: Names the collections the stages write to.
        error_policy: How a failed record, write or embed is reported.
        ingestion: The ingestion stats carried into the result.
        placements: Where each chunk sits in its document's structure.
        return_chunks: Whether the result carries the chunks.
        job_id: The in-flight cutover job, if any.
        rebuilt_components: When set, each rebuilt resolver component is
            appended with its decisions and members.
        tracer: Opens the spans. None disables them.
        embed_heading_path: Whether the chunk embedder gets each heading path.
        max_llm_pairs: The cap on LLM verifications for this batch.
        deferred: Receives the writes over committed rows that a job must not
            apply itself. Required when ``job_id`` is set; the caller replays
            it in the job's commit transaction.
        reuse_chunks: Whether the chunks already exist in the graph and keep
            their current nodes. The chunk and structure nodes are not written
            and the chunks are not embedded.

    Returns:
        The stats of every stage, the chunks when ``return_chunks`` is set, and
        the structure node ids the batch wrote.

    Raises:
        ValueError: ``job_id`` is set and ``deferred`` is None.
        Exception: The first failure of any stage when ``error_policy`` is
            ``RAISE``.
    """
    if job_id is not None and deferred is None:
        raise ValueError("deferred is required when job_id is set")
    job_uuid = UUID(str(job_id)) if job_id is not None else None
    ctx = StageContext(
        graph_store=graph_store,
        embedder=embedder,
        vector_store=vector_store,
        error_policy=error_policy,
        tracer=get_tracer(tracer),
        job_id=job_uuid,
        deferred=deferred,
    )
    with ctx.tracer.start_as_current_span("agrag.ingestion.ingest_chunks"):
        resolution_stats, merge = await _resolve_and_merge(
            entities,
            relations,
            chunks,
            ctx,
            graph_schema=graph_schema,
            retrieval_settings=retrieval_settings,
            rebuilt_components=rebuilt_components,
            max_llm_pairs=max_llm_pairs,
        )
        nodes = await write_nodes_stage(
            chunks, documents, placements, ctx, document_only=reuse_chunks
        )
        if reuse_chunks:
            chunk_embeds = EmbedStageResult(failures=[])
        else:
            chunk_embeds = await embed_chunks_stage(
                chunks,
                nodes.chunk_ids,
                nodes.chunk_writes,
                ctx,
                vector_collection=retrieval_settings.chunk_collection,
                embed_heading_path=embed_heading_path,
            )
        relation_writes = await write_relations_stage(
            [*merge.relation_records, *nodes.structure_relation_records],
            merge.mentioned_in_records,
            ctx,
        )
        survivor_embeds = await embed_survivors_stage(
            merge.survivors,
            ctx,
            vector_collection=retrieval_settings.entity_collection,
        )
        storage_capped = cap_failures(
            [
                *nodes.record_failures,
                *merge.resolved_vector_failures,
                *nodes.node_failures,
                *chunk_embeds.failures,
                *relation_writes.failures,
                *survivor_embeds.failures,
            ]
        )
        storage = StorageStats(
            nodes_written=nodes.nodes_written + len(merge.survivors),
            relationships_written=relation_writes.written,
            failures=storage_capped.items,
            failures_total=storage_capped.total,
            failures_truncated=storage_capped.truncated,
        )

    extraction_failures_capped = cap_failures(list(extraction_failures))
    extraction = ExtractionStats(
        chunks_processed=len(chunks),
        entities_extracted=len(entities),
        relations_extracted=len(relations),
        failures=extraction_failures_capped.items,
        failures_total=extraction_failures_capped.total,
        failures_truncated=extraction_failures_capped.truncated,
    )
    add_result = AddResult(
        ingestion=ingestion,
        extraction=extraction,
        resolution=resolution_stats,
        merge=merge.stats,
        storage=storage,
        chunks=list(chunks) if return_chunks else [],
    )
    return BatchResult(
        add_result=add_result,
        structure_node_ids=nodes.structure_node_ids,
    )


def _vector_record(
    record_id: UUID,
    vector: list[float],
    *,
    label: str,
    text: str,
    properties: dict[str, object] | None = None,
) -> VectorRecord:
    """Build a VectorRecord whose payload matches the retrievers' reads.

    ``label`` lets SearchFilters.to_payload_filter scope a search;
    ``text`` is the field the VectorStore backends sparse-embed for
    hybrid_search's keyword arm.

    Args:
        record_id: The domain object's id.
        vector: The dense embedding.
        label: The graph label the domain object carries.
        text: The embedding_text the vector was computed from.
        properties: Additional payload fields for metadata filtering.

    Returns:
        The record ready for VectorStore.upsert.
    """
    payload = {"label": label, "text": text}
    if properties:
        payload.update(properties)
    return VectorRecord(id=record_id, vector=vector, payload=payload)


async def _upsert_vectors(
    vector_store: VectorStore | None,
    collection: str,
    records: list[VectorRecord],
    *,
    pending_job_id: UUID | str | None = None,
) -> None:
    """Upsert records to the VectorStore when one is configured.

    Records whose vector is empty are skipped: an embed failure leaves
    None on the domain object, and an empty vector cannot be searched, so
    writing it would only corrupt the collection.

    Args:
        vector_store: The store to write to, or None to do nothing.
        collection: The collection name to write into.
        records: The records to upsert.
        pending_job_id: The in-flight Cutover Job staging these records. None
            writes committed records, for callers outside a job.
    """
    if vector_store is None:
        return
    writable = [record for record in records if record.vector]
    if not writable:
        return
    await vector_store.upsert(
        collection,
        writable,
        pending_job_id=UUID(str(pending_job_id)) if pending_job_id else None,
    )


async def _delete_vectors(
    vector_store: VectorStore | None, collection: str, ids: Sequence[UUID]
) -> None:
    """Delete records from the VectorStore when one is configured.

    Args:
        vector_store: The store to delete from, or None to do nothing.
        collection: The collection name to delete from.
        ids: The record ids to delete.
    """
    if vector_store is None or not ids:
        return
    await vector_store.delete(collection, list(ids))


async def _persisted_chunk_ids(
    ctx: StageContext, chunk_ids: set[UUID]
) -> tuple[set[UUID], list[StageFailure]]:
    """Return the subset of chunk_ids that exist as Chunk nodes.

    ``upsert_nodes`` writes its batches in sequence, so a failure partway
    through leaves the earlier batches committed. Embedding only the ids the
    graph really holds keeps those chunks searchable and keeps a chunk that
    never landed out of the VectorStore.

    Args:
        ctx: Where the chunk nodes are read. The job id counts chunks this same
            job just wrote, which still carry its pending tag. With no job,
            only committed chunks are read.
        chunk_ids: The ids this call tried to write.

    Returns:
        The ids found, and one failure when the read fails under a policy
        other than RAISE. The found ids are empty after such a failure, so the
        caller skips the embedding stage.

    Raises:
        Exception: The read failed and the error policy is ``RAISE``.
    """
    if not chunk_ids:
        return set(), []
    try:
        rows = await ctx.graph_store.execute_read(
            load_chunks_by_id_query(),
            {
                "ids": [str(cid) for cid in chunk_ids],
                "job_id": str(ctx.job_id) if ctx.job_id is not None else None,
            },
        )
    except Exception as exc:
        if ctx.error_policy is ErrorPolicy.RAISE:
            raise
        trace_id, span_id = record_stage_failure(exc)
        return set(), [
            StageFailure(
                item_id="chunk_lookup",
                error_type=type(exc).__name__,
                error_message=str(exc),
                trace_id=trace_id,
                span_id=span_id,
            )
        ]
    found: set[UUID] = set()
    for row in rows:
        node_id = node_properties(row_node(row)).get("id")
        if node_id is not None:
            with contextlib.suppress(ValueError):
                found.add(UUID(str(node_id)))
    return found, []


def _embedding_guard_fields(entity: Entity) -> dict[str, str]:
    """Return the id/name/description fields the embedding writes guard on.

    set_embedding_query and clear_property_query only apply a record when a
    node's current name/description still match these values, so a slower
    call cannot overwrite or clear a newer call's vector for different text.
    Mirrors ``coalesce(n.description, '')`` on the Cypher side.
    """
    description = entity.properties.get("description")
    return {
        "id": str(entity.id),
        "expected_name": entity.name,
        "expected_description": str(description) if description else "",
    }


async def _embed_and_upsert_chunks(
    chunks: list[Chunk],
    *,
    embedder: Embedder,
    graph_store: GraphStore,
    error_policy: ErrorPolicy,
    vector_store: VectorStore | None = None,
    vector_collection: str = "",
    pending_job_id: UUID | str | None = None,
    deferred: DeferredWrites | None = None,
    embed_heading_path: bool = False,
) -> list[StageFailure]:
    """Embed every chunk's text and write the vectors back onto their nodes.

    With ``embed_heading_path``, the embedder gets each chunk's heading path above
    its text. The stored text, the ``expected_text`` guard and the vector payload
    text stay the raw chunk text.

    On failure, clears any embedding already written to the chunk nodes
    rather than leaving one computed for stale text in place: vector
    search must not keep ranking a chunk by outdated content just because
    this re-embed failed. The clear is guarded by ``expected_text`` the
    same way the write is, so a concurrent update that changed a chunk's
    text between this call's embed and its clear does not accidentally
    wipe a newer vector.

    When vector_store is set, every successfully written vector is also
    upserted there so SearchEngine's VectorStore path matches the
    GraphStore-native path. Each record carries its chunk's
    ``document_id``, which is what a document-scoped SearchFilters
    compiles to, so filtering by document works on both paths. A
    VectorStore failure honors error_policy: RAISE propagates, otherwise
    it is recorded as a StageFailure and the native search path keeps
    working without it. The failure leaves the collection untouched: the
    mirror has no conditional write, so deleting the records this call
    failed to replace would race a concurrent re-ingest and could remove
    the newer vector it just wrote. The stored record keeps its previous
    text until the next successful ingest rewrites it, and retrieval
    loads every hit from the graph, so only that record's score is
    stale.

    Args:
        chunks: The chunks this call wrote to graph_store already.
        embedder: Produces one vector per chunk text.
        graph_store: Where the embedding, and on failure the cleared
            embedding property, are written.
        error_policy: RAISE propagates the failure after clearing; any
            other policy returns it instead.
        vector_store: Optional second write target; None does nothing.
        vector_collection: The VectorStore collection to write into.
            Ignored when vector_store is None.
        pending_job_id: The in-flight job's id, mirrored into vector
            payloads until that job commits. None writes untagged
            payloads, for callers outside a job.
        deferred: Receives the vector writes over committed chunks. None
            outside a job.
        embed_heading_path: Whether the embedder gets each chunk's heading path
            above its text.

    Returns:
        One StageFailure per chunk whose embed or write step raised.

    Raises:
        Exception: Whatever embed() or the write raised, when
            error_policy is RAISE.
    """
    job = str(pending_job_id) if pending_job_id is not None else None
    try:
        texts = [ch.contextual_text if embed_heading_path else ch.text for ch in chunks]
        vectors = await embedder.embed(texts)
        records = []
        for ch, vec in zip(chunks, vectors, strict=True):
            ch.embedding = vec
            records.append(
                {
                    "id": str(ch.id),
                    "pending_job_id": job,
                    "vector": vec,
                    "expected_text": ch.text,
                }
            )
        matched_rows = await write_or_defer(
            graph_store,
            set_chunk_embedding_query("embedding"),
            records,
            deferred=deferred,
        )
    except Exception as exc:  # noqa: BLE001
        with contextlib.suppress(Exception):
            await graph_store.execute_write(
                clear_chunk_embedding_query("embedding"),
                {
                    "records": [
                        {
                            "id": str(ch.id),
                            "pending_job_id": job,
                            "expected_text": ch.text,
                        }
                        for ch in chunks
                    ]
                },
            )
        if error_policy is ErrorPolicy.RAISE:
            raise
        trace_id, span_id = record_stage_failure(exc)
        return [
            StageFailure(
                item_id="chunk_embeddings",
                error_type=type(exc).__name__,
                error_message=str(exc),
                trace_id=trace_id,
                span_id=span_id,
            )
        ]
    if vector_store is not None:
        vector_records = []
        # A deferred row still matches: the commit applies it, so its vector
        # belongs in the mirror.
        matched_ids = {
            UUID(str(row["id"]))
            for row in matched_rows
            if isinstance(row, dict) and row.get("id")
        }
        for ch in chunks:
            if ch.id not in matched_ids:
                ch.embedding = None
                continue
            if ch.id is None or not ch.embedding:
                continue
            vector_records.append(
                _vector_record(
                    ch.id,
                    ch.embedding,
                    label=CHUNK_LABEL,
                    text=ch.text,
                    properties={"document_id": str(ch.document_id)},
                )
            )
        try:
            await _upsert_vectors(
                vector_store,
                vector_collection,
                vector_records,
                pending_job_id=pending_job_id,
            )
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            trace_id, span_id = record_stage_failure(exc)
            return [
                StageFailure(
                    item_id="chunk_vector_store",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    trace_id=trace_id,
                    span_id=span_id,
                )
            ]
    return []


async def _embed_and_upsert_survivors(
    survivors: dict[UUID, Entity],
    *,
    embedder: Embedder,
    graph_store: GraphStore,
    error_policy: ErrorPolicy,
    vector_store: VectorStore | None = None,
    vector_collection: str = "",
    labels_by_id: dict[UUID, str] | None = None,
    pending_job_id: UUID | str | None = None,
    deferred: DeferredWrites | None = None,
) -> list[StageFailure]:
    """Embed every survivor's current text and write only the vector.

    Shared by add() and consolidate(apply=True): both write a survivor's
    node before this call, so its embedding must be refreshed for whatever
    text that write left it with. Writing only the embedding property
    (set_embedding_query), rather than a full node upsert from the in-memory
    Entity, matters here specifically: a concurrent writer could update this
    same entity's provenance or properties while this call's embed() is in
    flight, and a full overwrite from a snapshot taken before that update
    would discard it, not just deliver the new vector.

    Both the write and the failure-path clear below are guarded by
    _embedding_guard_fields: a record only applies when the node's current
    name/description still match what this call started with. Concurrent
    add() calls can interleave against the same entity, so without this
    guard an older, slower call's write or clear can land after a newer
    call's and leave a vector computed for stale text, or wipe a vector
    the newer call just wrote.

    On failure, clears any embedding already on the survivor nodes rather
    than leaving one computed for their prior text in place: vector search
    must not keep ranking an entity by outdated content just because this
    re-embed failed. ``zip(..., strict=True)`` turns an embedder returning
    too few vectors into the same failure path, rather than silently
    leaving the trailing entities' embeddings stale.

    When vector_store is set, each mirrored record also carries the
    survivor's own properties, since a SearchFilters property filter is
    compiled into the payload there but into a node-property match on the
    GraphStore-native path. A failed mirror upsert leaves the collection
    untouched, for the reason _embed_and_upsert_chunks gives: removing the
    records this call failed to replace would race a concurrent call that
    owns them.

    Args:
        survivors: The entities to embed, keyed by id.
        embedder: Computes one vector per entity's embedding_text.
        graph_store: Where the embedding, and on failure the cleared
            embedding property, are written.
        error_policy: RAISE propagates the failure after clearing; any
            other policy returns it instead.
        vector_store: Optional second write target; None does nothing.
        vector_collection: The VectorStore collection to write into.
            Ignored when vector_store is None.
        labels_by_id: Maps each survivor id to its label for the
            VectorStore payload. Survivors missing from the map are
            written with an empty label. Ignored when vector_store is
            None.
        pending_job_id: The in-flight job's id, mirrored into vector
            payloads until that job commits. None writes untagged
            payloads, for callers outside a job.
        deferred: Receives the vector writes over committed entities. None
            outside a job.

    Returns:
        A single-item list with the failure, or empty on success.

    Raises:
        Exception: Whatever embed() or the write raised, when error_policy
            is RAISE.
    """
    job = str(pending_job_id) if pending_job_id is not None else None
    try:
        texts = [ent.embedding_text for ent in survivors.values()]
        vectors = await embedder.embed(texts)
        records = []
        for ent, vec in zip(survivors.values(), vectors, strict=True):
            ent.embedding = vec
            records.append(
                {**_embedding_guard_fields(ent), "pending_job_id": job, "vector": vec}
            )
        matched_rows = await write_or_defer(
            graph_store,
            set_embedding_query("embedding"),
            records,
            deferred=deferred,
        )
    except Exception as exc:  # noqa: BLE001
        # Best-effort: a failure here must not mask error_policy.
        with contextlib.suppress(Exception):
            await graph_store.execute_write(
                clear_property_query("embedding"),
                {
                    "records": [
                        {**_embedding_guard_fields(ent), "pending_job_id": job}
                        for ent in survivors.values()
                    ]
                },
            )
        if error_policy is ErrorPolicy.RAISE:
            raise
        trace_id, span_id = record_stage_failure(exc)
        return [
            StageFailure(
                item_id="embeddings",
                error_type=type(exc).__name__,
                error_message=str(exc),
                trace_id=trace_id,
                span_id=span_id,
            )
        ]
    if vector_store is not None:
        label_map = labels_by_id or {}
        # A deferred row still matches: the commit applies it, so its vector
        # belongs in the mirror.
        matched_ids = {
            UUID(str(row["id"]))
            for row in matched_rows
            if isinstance(row, dict) and row.get("id")
        }
        vector_records = [
            _vector_record(
                ent.id,
                ent.embedding or [],
                label=label_map.get(ent.id, ""),
                text=ent.embedding_text,
                properties=dict(ent.properties),
            )
            for ent in survivors.values()
            if ent.id in matched_ids
        ]
        try:
            await _upsert_vectors(
                vector_store,
                vector_collection,
                vector_records,
                pending_job_id=pending_job_id,
            )
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            trace_id, span_id = record_stage_failure(exc)
            return [
                StageFailure(
                    item_id="entity_vector_store",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    trace_id=trace_id,
                    span_id=span_id,
                )
            ]
    return []
