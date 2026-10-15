"""The bodies of the ``Graph`` document operations.

Each call runs one Cutover Job per document. The job's post-commit work
arrives as ``cleanup``, so the live calls and crash recovery run the same
definition.
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from functools import partial as bind
from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.chunking import Chunker
from agrag.chunking.chunker import ChunkedDocument, ChunkPlacement
from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import (
    Document,
    SourceFormat,
)
from agrag.common.data_models.dropped import DroppedCount
from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.graph_record import DeferredWrites
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.stage_failure import StageFailure, cap_failures
from agrag.common.data_models.structure import version_id
from agrag.common.data_models.update_decision import UpdateDecision
from agrag.common.schema_fingerprint import RunRecord
from agrag.cypher.documents import (
    document_chunk_count_query,
    document_cited_relation_endpoints_query,
    document_mentioned_entities_query,
    update_document_dates_query,
)
from agrag.cypher.relations import entities_in_documents_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.ingestion._cutover import InPlaceRefresh, run_cutover_job
from agrag.ingestion._document_lifecycle import (
    DocumentChange,
    find_document,
)
from agrag.ingestion._ingest_pipeline import (
    ExtractionBatch,
    extract_chunks,
    ingest_chunks,
)
from agrag.ingestion._structure import placement_map
from agrag.ingestion._walk import SourcesType, chunk_documents, iter_document_batches
from agrag.ingestion.extract import Extractor, LLMExtractor
from agrag.ingestion.reports import AddResult, EscalationReport, UpdateResult
from agrag.ingestion.resolved_entities import MatchComponent
from agrag.ingestion.settings import CutoverJobSettings, ExtractionSettings
from agrag.ingestion.stats import (
    ChunkingStats,
    ExtractionStats,
    IngestStats,
    MergeStats,
    ResolutionStats,
    StorageStats,
)
from agrag.ingestion.stats.dropped import sum_dropped
from agrag.loaders.base import Loader
from agrag.loaders.common import build_prose_document, text_sections
from agrag.loaders.loader_registry import LoaderRegistry
from agrag.loaders.types import ErrorPolicy, LoadStats, ReadOptions, SourceRef
from agrag.loaders.walk import normalize_inline_text


logger = logging.getLogger(__name__)

CleanupStep = Callable[
    [list[UUID], list[UUID], list[UUID]], Awaitable[list[StageFailure]]
]


def _placements_of(
    chunked_documents: Iterable[ChunkedDocument],
) -> dict[UUID, ChunkPlacement]:
    """Return the placement of every chunk across the chunked documents."""
    return {
        chunk_id: placement
        for chunked in chunked_documents
        for chunk_id, placement in placement_map(chunked).items()
    }


async def _no_pending_write(job_id: UUID) -> None:
    """Pending-write step for delete_document, which writes nothing new."""


def _with_cleanup_failures(
    result: AddResult, failures: list[StageFailure]
) -> AddResult:
    """Record post-commit rebuild failures in the storage stats.

    Args:
        result: The pending-write result of one document job.
        failures: Failures the cleanup phase recorded under a non-RAISE policy.

    Returns:
        The result with ``failures`` appended under the per-stage cap, or the
        same result when there are none.
    """
    if not failures:
        return result
    capped = cap_failures([*result.storage.failures, *failures])
    storage = result.storage.model_copy(
        update={
            "failures": capped.items,
            "failures_total": result.storage.failures_total + len(failures),
            "failures_truncated": result.storage.failures_truncated or capped.truncated,
        }
    )
    return result.model_copy(update={"storage": storage})


def _without_extraction_stamps(
    chunks: list[Chunk], documents: list[Document]
) -> tuple[list[Chunk], list[Document]]:
    """Copy chunks and documents with the extraction stamp cleared.

    A version with a failed extraction must not read as current. Without the
    stamp, the next update sees a missing fingerprint and extracts the document
    again.

    Args:
        chunks: The chunks of the version whose extraction failed.
        documents: The documents of the same version.

    Returns:
        Copies of the chunks and the documents with no extraction fingerprint.
    """
    return (
        [chunk.model_copy(update={"extraction_fingerprint": None}) for chunk in chunks],
        [
            document.model_copy(update={"extraction_fingerprint": None})
            for document in documents
        ],
    )


def _group_by_document(  # noqa: PLR0912,PLR0917
    chunks: list[Chunk],
    documents: list[Document],
    entities: list[ExtractedEntity],
    relations: list[ExtractedRelation],
    candidates: list[CandidateRecord],
    extraction_failures: list[StageFailure],
    dropped: Sequence[DroppedCount] = (),
) -> list[
    tuple[
        str,
        list[Chunk],
        list[Document],
        list[ExtractedEntity],
        list[ExtractedRelation],
        list[CandidateRecord],
        list[StageFailure],
        list[DroppedCount],
    ]
]:
    ordered_keys: list[str] = []
    for document in documents:
        key = document.resolved_document_key
        if key not in ordered_keys:
            ordered_keys.append(key)
    if not ordered_keys and chunks:
        first_link = chunks[0].document_id
        ordered_keys = [str(first_link)]
    key_by_node_id = {
        Document.node_id_for(document_key=key): key for key in ordered_keys
    }

    def _or_first(found: str | None, *, kind: str) -> str:
        if found is None:
            logger.warning(
                "%s maps to no listed document; joining the first slice.", kind
            )
            return ordered_keys[0]
        return found

    chunks_by_key: dict[str, list[Chunk]] = {key: [] for key in ordered_keys}
    for chunk in chunks:
        chunks_by_key.setdefault(
            _or_first(key_by_node_id.get(chunk.document_id), kind=f"Chunk {chunk.id}"),
            [],
        ).append(chunk)
    chunk_ids_by_key = {
        key: {chunk.id for chunk in group if chunk.id is not None}
        for key, group in chunks_by_key.items()
    }
    key_by_chunk_id: dict[UUID, str] = {}
    for key, chunk_ids in chunk_ids_by_key.items():
        for chunk_id in chunk_ids:
            key_by_chunk_id[chunk_id] = key
    entities_by_key: dict[str, list[ExtractedEntity]] = {
        key: [] for key in ordered_keys
    }
    slice_position: list[tuple[str, int]] = []
    for entity in entities:
        entity_key = _or_first(
            key_by_chunk_id.get(entity.chunk_id),
            kind=f"Mention of chunk {entity.chunk_id}",
        )
        group = entities_by_key.setdefault(entity_key, [])
        slice_position.append((entity_key, len(group)))
        group.append(entity)
    relations_by_key: dict[str, list[ExtractedRelation]] = {
        key: [] for key in ordered_keys
    }
    for relation in relations:
        source_key, source_index = slice_position[relation.source_index]
        target_key, target_index = slice_position[relation.target_index]
        if source_key != target_key:
            logger.warning(
                "Dropping relation %r across slices %r and %r.",
                relation.label,
                source_key,
                target_key,
            )
            continue
        relations_by_key[source_key].append(
            relation.model_copy(
                update={"source_index": source_index, "target_index": target_index}
            )
        )
    candidates_by_key: dict[str, list[CandidateRecord]] = {
        key: [] for key in ordered_keys
    }
    for candidate in candidates:
        owner_key = _or_first(
            key_by_chunk_id.get(candidate.chunk_id),
            kind=f"Candidate of chunk {candidate.chunk_id}",
        )
        candidates_by_key.setdefault(owner_key, []).append(candidate)
    failures_by_key: dict[str, list[StageFailure]] = {key: [] for key in ordered_keys}
    for failure in extraction_failures:
        try:
            failure_key = key_by_chunk_id.get(UUID(str(failure.item_id)))
        except ValueError:
            failure_key = None
        failures_by_key.setdefault(
            _or_first(failure_key, kind=f"Failure {failure.item_id}"), []
        ).append(failure)
    dropped_by_key: dict[str, list[DroppedCount]] = {key: [] for key in ordered_keys}
    for item in dropped:
        owner_key = _or_first(
            key_by_chunk_id.get(item.chunk_id) if item.chunk_id is not None else None,
            kind=f"Dropped {item.kind} {item.label}",
        )
        dropped_by_key.setdefault(owner_key, []).append(item)
    documents_by_key: dict[str, list[Document]] = {key: [] for key in ordered_keys}
    for document in documents:
        documents_by_key[document.resolved_document_key].append(document)
    return [
        (
            key,
            chunks_by_key[key],
            documents_by_key[key],
            entities_by_key[key],
            relations_by_key[key],
            candidates_by_key[key],
            failures_by_key[key],
            dropped_by_key[key],
        )
        for key in ordered_keys
    ]


def _sum_chunking(parts: Sequence[ChunkingStats]) -> ChunkingStats:
    """Add the chunking summaries of several parts of one call."""
    return ChunkingStats(
        chunks=sum(part.chunks for part in parts),
        sections=sum(part.sections for part in parts),
        tables=sum(part.tables for part in parts),
        figures=sum(part.figures for part in parts),
    )


def _merge_add_results(
    results: list[AddResult],
    *,
    ingestion: IngestStats,
    chunking: ChunkingStats,
    escalation: EscalationReport,
) -> AddResult:
    """Combine per-document job results into one call-level summary.

    Each document in an add() call commits as its own Cutover Job. The
    caller still gets a single AddResult shaped exactly like a one-job
    call. Counters sum, failure lists concatenate re-capped against the
    per-stage cap with true totals preserved, and chunks concatenate in
    job order. The call-level ingestion and chunking summaries passed in replace
    the per-slice placeholders.

    Args:
        results: One AddResult per document job, in job order.
        ingestion: The call-level ingestion summary from the walk.
        chunking: The call-level chunking summary.
        escalation: The call-level escalation report, merged across the
            extraction batches. Escalation runs before the per-document jobs,
            so the per-job results carry none.

    Returns:
        The merged summary, or a zero-stage summary when no job ran.
    """

    def _combine(
        item_lists: list[list[StageFailure]], totals: list[int], truncs: list[bool]
    ) -> tuple[list[StageFailure], int, bool]:
        combined = [failure for items in item_lists for failure in items]
        capped = cap_failures(combined)
        return capped.items, sum(totals), any(truncs) or capped.truncated

    if not results:
        return AddResult(
            ingestion=ingestion,
            chunking=chunking,
            extraction=ExtractionStats(),
            resolution=ResolutionStats(),
            merge=MergeStats(),
            storage=StorageStats(),
            chunks=[],
            escalation=escalation,
        )
    if len(results) == 1:
        return results[0].model_copy(
            update={
                "ingestion": ingestion,
                "chunking": chunking,
                "escalation": escalation,
            }
        )
    extraction_items, extraction_total, extraction_truncated = _combine(
        [result.extraction.failures for result in results],
        [result.extraction.failures_total for result in results],
        [result.extraction.failures_truncated for result in results],
    )
    merge_items, merge_total, merge_truncated = _combine(
        [result.merge.failures for result in results],
        [result.merge.failures_total for result in results],
        [result.merge.failures_truncated for result in results],
    )
    storage_items, storage_total, storage_truncated = _combine(
        [result.storage.failures for result in results],
        [result.storage.failures_total for result in results],
        [result.storage.failures_truncated for result in results],
    )
    return AddResult(
        ingestion=ingestion,
        chunking=chunking,
        extraction=ExtractionStats(
            chunks_processed=sum(
                result.extraction.chunks_processed for result in results
            ),
            entities_extracted=sum(
                result.extraction.entities_extracted for result in results
            ),
            relations_extracted=sum(
                result.extraction.relations_extracted for result in results
            ),
            dropped=sum_dropped(result.extraction.dropped for result in results),
            candidates_written=sum(
                result.extraction.candidates_written for result in results
            ),
            candidates_skipped=sum(
                result.extraction.candidates_skipped for result in results
            ),
            failures=extraction_items,
            failures_total=extraction_total,
            failures_truncated=extraction_truncated,
        ),
        resolution=ResolutionStats(
            exact_match_hits=sum(
                result.resolution.exact_match_hits for result in results
            ),
            in_batch_groups=sum(
                result.resolution.in_batch_groups for result in results
            ),
            ambiguous_count=sum(
                result.resolution.ambiguous_count for result in results
            ),
            failed_llm_requests=sum(
                result.resolution.failed_llm_requests for result in results
            ),
            cap_truncated_pairs=sum(
                result.resolution.cap_truncated_pairs for result in results
            ),
            llm_unavailable_pairs=sum(
                result.resolution.llm_unavailable_pairs for result in results
            ),
        ),
        merge=MergeStats(
            nodes_created=sum(result.merge.nodes_created for result in results),
            nodes_updated=sum(result.merge.nodes_updated for result in results),
            conflicts_resolved=sum(
                result.merge.conflicts_resolved for result in results
            ),
            dropped=sum_dropped(result.merge.dropped for result in results),
            failures=merge_items,
            failures_total=merge_total,
            failures_truncated=merge_truncated,
        ),
        storage=StorageStats(
            nodes_written=sum(result.storage.nodes_written for result in results),
            relationships_written=sum(
                result.storage.relationships_written for result in results
            ),
            failures=storage_items,
            failures_total=storage_total,
            failures_truncated=storage_truncated,
        ),
        chunks=[chunk for result in results for chunk in result.chunks],
        escalation=escalation,
    )


async def document_entity_candidates(
    graph_store: GraphStore, document_node_id: UUID
) -> list[UUID]:
    """Return live entity ids mentioned by a document's open chunks.

    Args:
        graph_store: The store to read from.
        document_node_id: The persisted Document node's id.

    Returns:
        The mentioned entity ids in first-seen order.
    """
    rows = await graph_store.execute_read(
        entities_in_documents_query(),
        {
            "document_ids": [str(document_node_id)],
            "job_id": None,
        },
    )
    candidates: list[UUID] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            candidate = UUID(str(row["id"]))
        except (KeyError, TypeError, ValueError):
            continue
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


async def _commit_batch(  # noqa: PLR0913
    flat_batch: list[Chunk],
    batch: list[Document],
    extracted: ExtractionBatch,
    *,
    graph_store: GraphStore,
    embedder: Embedder,
    schema: GraphSchema,
    cutover_settings: CutoverJobSettings,
    error_policy: ErrorPolicy,
    return_chunks: bool,
    placements_by_id: dict[UUID, ChunkPlacement],
    tracer: Tracer,
    embed_heading_path: bool,
    max_llm_pairs: int,
    write_candidates: bool,
    cleanup: CleanupStep,
    previous_hashes: Mapping[str, str | None],
) -> list[AddResult]:
    """Write one extracted walk batch as one Cutover Job per document.

    Args:
        flat_batch: The chunks of the walk batch.
        batch: The stamped documents of the walk batch.
        extracted: The extraction output for ``flat_batch``. Its relation
            indices are positions within its own entity list.
        graph_store: The store that receives the graph writes.
        embedder: The embedder for chunk and entity vectors.
        schema: The graph schema the entities are written against.
        cutover_settings: The settings for each Cutover Job.
        error_policy: How a failed write or embedding is treated.
        return_chunks: Whether each result carries its chunks.
        placements_by_id: The chunk placements, keyed by chunk id.
        tracer: The tracer for the write spans.
        embed_heading_path: Whether chunk vectors include the heading path.
        max_llm_pairs: The cap on LLM-judged entity pairs per document.
        write_candidates: Whether candidates are written to the graph.
        cleanup: The post-commit cleanup step of each Cutover Job.
        previous_hashes: The content hash each key held before this call, for
            keys that have a stored Document node. Keys missing from the
            mapping are first adds.

    Returns:
        One AddResult per document, in document order.
    """
    partials: list[AddResult] = []
    for (
        document_key,
        doc_chunks,
        doc_documents,
        doc_entities,
        doc_relations,
        doc_candidates,
        doc_failures,
        doc_dropped,
    ) in _group_by_document(
        flat_batch,
        batch,
        extracted.entities,
        extracted.relations,
        extracted.candidates,
        extracted.failures,
        extracted.dropped,
    ):
        written_chunks, written_documents = (
            _without_extraction_stamps(doc_chunks, doc_documents)
            if doc_failures
            else (doc_chunks, doc_documents)
        )
        components: list[MatchComponent] = []
        deferred = DeferredWrites()
        created_entity_ids: list[UUID] = []

        async def _pending(
            job_id: UUID,
            *,
            created_ids: list[UUID],
            _components: list[MatchComponent] = components,
            _deferred: DeferredWrites = deferred,
            _slice: tuple[
                list[Chunk],
                list[Document],
                list[ExtractedEntity],
                list[ExtractedRelation],
                list[CandidateRecord],
                list[StageFailure],
                list[DroppedCount],
            ] = (
                written_chunks,
                written_documents,
                doc_entities,
                doc_relations,
                doc_candidates,
                doc_failures,
                doc_dropped,
            ),
        ) -> AddResult:
            (
                slice_chunks,
                slice_documents,
                slice_entities,
                slice_relations,
                slice_candidates,
                slice_failures,
                slice_dropped,
            ) = _slice
            ingested = await ingest_chunks(
                slice_chunks,
                slice_documents,
                slice_entities,
                slice_relations,
                slice_failures,
                graph_store=graph_store,
                embedder=embedder,
                graph_schema=schema,
                error_policy=error_policy,
                ingestion=IngestStats(documents=1),
                return_chunks=return_chunks,
                job_id=job_id,
                rebuilt_components=_components,
                placements=placements_by_id,
                tracer=tracer,
                embed_heading_path=embed_heading_path,
                max_llm_pairs=max_llm_pairs,
                candidates=slice_candidates,
                dropped=slice_dropped,
                write_candidates=write_candidates,
                deferred=_deferred,
            )
            created_ids.extend(ingested.created_entity_ids)
            return ingested.add_result

        pending_write = bind(_pending, created_ids=created_entity_ids)
        added = doc_documents[0]
        document_node_id = Document.node_id_for(document_key=document_key)
        partial, cleanup_failures, _ = await run_cutover_job(
            verb="add",
            document_key=document_key,
            affected_entity_ids=[],
            graph_store=graph_store,
            settings=cutover_settings,
            pending_write=pending_write,
            cleanup=cleanup,
            components=components,
            deferred=deferred,
            created_entity_ids=created_entity_ids,
            candidate_document_node_id=document_node_id,
            change=DocumentChange(
                document_node_id=document_node_id,
                document_key=document_key,
                verb="add",
                content_hash=added.content_hash,
                previous_content_hash=previous_hashes.get(document_key),
                version_id=version_id(added),
            ),
            tracer=tracer,
        )
        partials.append(_with_cleanup_failures(partial, cleanup_failures))
    return partials


async def add_documents(  # noqa: PLR0912,PLR0915,PLR0913
    source: SourcesType | None,
    *,
    text: str | None,
    documents: Sequence[Document] | None,
    loader: Loader | None,
    error_policy: ErrorPolicy,
    on_progress: Callable[[AddResult], None] | None,
    return_chunks: bool,
    read_options: ReadOptions | None,
    schema: GraphSchema,
    run: RunRecord,
    graph_store: GraphStore,
    embedder: Embedder,
    extractor: Extractor | LLMExtractor,
    llm_extractor: LLMExtractor | None,
    extraction_settings: ExtractionSettings,
    cutover_settings: CutoverJobSettings,
    chunker: Chunker,
    registry: LoaderRegistry,
    embed_heading_path: bool,
    max_llm_pairs: int,
    write_candidates: bool,
    cleanup: CleanupStep,
    tracer: Tracer,
) -> AddResult:
    """Add content to the graph. ``Graph.add`` documents the arguments."""
    with tracer.start_as_current_span("agrag.ingestion.add"):
        opts = read_options or ReadOptions()
        given = sum(x is not None for x in (source, text, documents))
        if given != 1:
            raise ValueError(
                f"Provide exactly one of 'source', 'text', or 'documents'; got {given}."
            )
        if loader is not None and source is None:
            raise ValueError(
                "A loader override requires 'source'; it has no effect on "
                "'text' or 'documents'."
            )

        chunks: list[Chunk] = []
        documents_seen: list[Document] = []
        placements_by_id: dict[UUID, ChunkPlacement] = {}
        document_keys_seen: set[str] = set()
        escalation_reports: list[EscalationReport] = []
        partials: list[AddResult] = []
        routed_chunking: list[ChunkingStats] = []
        unchanged_documents = 0

        def _call_chunking() -> ChunkingStats:
            return _sum_chunking(
                [ChunkingStats.from_documents(documents_seen, chunks), *routed_chunking]
            )

        def _record_document_keys(batch: Sequence[Document]) -> None:
            for document in batch:
                document_key = document.resolved_document_key
                if document_key in document_keys_seen:
                    raise ValueError(
                        "Each add call requires distinct document keys; "
                        f"duplicate: {document_key!r}."
                    )
                document_keys_seen.add(document_key)

        # For ingestion stats accumulation
        final_stats = LoadStats()

        # For on_progress partial result helper
        def _build_partial_add_result() -> AddResult:
            ingest = IngestStats(
                documents=final_stats.documents,
                sources=final_stats.sources,
                skipped=final_stats.skipped,
                unchanged=unchanged_documents,
                quarantined=final_stats.quarantined,
                quarantined_items=list(final_stats.quarantined_items),
            )
            return _merge_add_results(
                partials,
                ingestion=ingest,
                chunking=_call_chunking(),
                escalation=EscalationReport.merge(escalation_reports),
            )

        async for loaded_batch, stats in iter_document_batches(
            source=source,
            text=text,
            documents=documents,
            registry=registry,
            opts=opts,
            error_policy=error_policy,
            loader=loader,
            tracer=tracer,
        ):
            _record_document_keys(loaded_batch)
            final_stats.documents = stats.documents
            final_stats.sources = stats.sources
            final_stats.skipped = stats.skipped
            final_stats.quarantined = stats.quarantined
            final_stats.quarantined_items = list(stats.quarantined_items)
            # A key that already has a current version is an update, so the
            # decision the update path makes decides whether anything is written.
            previous_hashes: dict[str, str | None] = {}
            new_documents: list[Document] = []
            for document in loaded_batch:
                document_key = document.resolved_document_key
                found = await find_document(graph_store, document_key=document_key)
                if found is None:
                    new_documents.append(document)
                    continue
                previous_hashes[document_key] = found.current_content_hash
                if not found.has_open_chunks:
                    new_documents.append(document)
                    continue
                updated = await update_document(
                    document_key,
                    text=None,
                    source=None,
                    document=document,
                    loader=None,
                    error_policy=error_policy,
                    read_options=read_options,
                    force=False,
                    schema=schema,
                    run=run,
                    graph_store=graph_store,
                    embedder=embedder,
                    extractor=extractor,
                    llm_extractor=llm_extractor,
                    extraction_settings=extraction_settings,
                    cutover_settings=cutover_settings,
                    chunker=chunker,
                    registry=registry,
                    embed_heading_path=embed_heading_path,
                    max_llm_pairs=max_llm_pairs,
                    write_candidates=write_candidates,
                    cleanup=cleanup,
                    tracer=tracer,
                )
                if updated.no_op:
                    unchanged_documents += 1
                if updated.add_result is not None:
                    partials.append(updated.add_result)
                    routed_chunking.append(updated.add_result.chunking)
                    escalation_reports.append(updated.add_result.escalation)
            # Stamp before chunking: the schema fingerprint is part of the version id.
            batch = [run.stamp(document) for document in new_documents]
            chunk_batch = await asyncio.to_thread(
                chunk_documents, batch, chunker=chunker, tracer=tracer
            )
            flat_batch = [chunk for cd in chunk_batch for chunk in cd.chunks]
            placements_by_id.update(_placements_of(chunk_batch))
            chunks.extend(flat_batch)
            documents_seen.extend(batch)
            extracted = await extract_chunks(
                flat_batch,
                start_index=0,
                extractor=extractor,
                schema=schema,
                error_policy=error_policy,
                settings=extraction_settings,
                llm_extractor=llm_extractor,
                tracer=tracer,
            )
            escalation_reports.append(extracted.report)
            # Each walk batch commits before the next one is extracted, so a
            # failure late in a large call keeps the work already written. Each
            # document's slice is its own Cutover Job with its own lease; a lease
            # failure aborts the documents still queued while committed documents
            # stay committed.
            partials.extend(
                await _commit_batch(
                    flat_batch,
                    batch,
                    extracted,
                    graph_store=graph_store,
                    embedder=embedder,
                    schema=schema,
                    cutover_settings=cutover_settings,
                    error_policy=error_policy,
                    return_chunks=return_chunks,
                    placements_by_id=placements_by_id,
                    tracer=tracer,
                    embed_heading_path=embed_heading_path,
                    max_llm_pairs=max_llm_pairs,
                    write_candidates=write_candidates,
                    cleanup=cleanup,
                    previous_hashes=previous_hashes,
                )
            )
            if on_progress is not None:
                with contextlib.suppress(Exception):
                    on_progress(_build_partial_add_result())

        # Assemble the ingestion summary from this call's own walk.
        ingestion = IngestStats(
            documents=final_stats.documents,
            sources=final_stats.sources,
            skipped=final_stats.skipped,
            unchanged=unchanged_documents,
            quarantined=final_stats.quarantined,
            quarantined_items=list(final_stats.quarantined_items),
        )
        result = _merge_add_results(
            partials,
            ingestion=ingestion,
            chunking=_call_chunking(),
            escalation=EscalationReport.merge(escalation_reports),
        )

        if on_progress is not None:
            with contextlib.suppress(Exception):
                on_progress(result)

        return result


async def update_document(  # noqa: PLR0913
    document_key: str,
    *,
    text: str | None,
    source: SourcesType | None,
    document: Document | None,
    loader: Loader | None,
    error_policy: ErrorPolicy,
    read_options: ReadOptions | None,
    force: bool,
    schema: GraphSchema,
    run: RunRecord,
    graph_store: GraphStore,
    embedder: Embedder,
    extractor: Extractor | LLMExtractor,
    llm_extractor: LLMExtractor | None,
    extraction_settings: ExtractionSettings,
    cutover_settings: CutoverJobSettings,
    chunker: Chunker,
    registry: LoaderRegistry,
    embed_heading_path: bool,
    max_llm_pairs: int,
    write_candidates: bool,
    cleanup: CleanupStep,
    tracer: Tracer,
) -> UpdateResult:
    """Replace one document version. ``Graph.update`` documents the arguments."""
    with tracer.start_as_current_span("agrag.ingestion.update"):
        given = sum(x is not None for x in (text, source, document))
        if given != 1:
            raise ValueError(
                f"Provide exactly one of 'text', 'source', or 'document'; got {given}."
            )

        opts = read_options or ReadOptions()
        if document is not None:
            if document.resolved_document_key != document_key:
                raise ValueError(
                    f"The document key {document.resolved_document_key!r} does not "
                    f"match the update key {document_key!r}."
                )
        elif text is not None:
            normalized, normalization = normalize_inline_text(text, opts)
            document = build_prose_document(
                source=SourceRef(uri=document_key, extension=".txt"),
                text=normalized,
                encoding="utf-8",
                source_format=SourceFormat.TXT,
                loader_name="inline",
                opts=opts,
                title="inline",
                sections=text_sections(normalized),
            ).model_copy(
                update={"normalization": normalization, "document_key": document_key}
            )
        else:
            documents_from_source: list[Document] = []
            async for batch, _stats in iter_document_batches(
                source=source,
                registry=registry,
                opts=opts,
                error_policy=error_policy,
                loader=loader,
                tracer=tracer,
            ):
                documents_from_source.extend(batch)
            if len(documents_from_source) != 1:
                raise ValueError("The source must produce exactly one document.")
            document = documents_from_source[0].model_copy(
                update={
                    "document_key": document_key,
                    "id": Document.node_id_for(document_key=document_key),
                }
            )
        document = run.stamp(document)

        found = await find_document(graph_store, document_key=document_key)
        decision = (
            UpdateDecision.NEW_VERSION
            if found is None
            else found.decide(
                content_hash=document.content_hash,
                version_id=version_id(document),
                chunker_hash=chunker.fingerprint,
                run=run,
                force=force,
                published_at=document.published_at,
                content_date=document.content_date,
            )
        )
        if found is not None and decision is UpdateDecision.NO_OP:
            return UpdateResult(
                document_key=document_key,
                no_op=True,
                previous_content_hash=found.current_content_hash,
                new_content_hash=document.content_hash,
                decision=decision,
            )
        if found is not None and decision is UpdateDecision.METADATA_ONLY:

            async def write_dates(transaction: GraphStoreTransaction) -> None:
                await transaction.execute_write(
                    update_document_dates_query(),
                    {
                        "document_node_id": str(found.document_node_id),
                        "published_at": (
                            document.published_at.isoformat()
                            if document.published_at is not None
                            else None
                        ),
                        "content_date": (
                            document.content_date.isoformat()
                            if document.content_date is not None
                            else None
                        ),
                    },
                )

            await graph_store.run_in_transaction(write_dates)
            return UpdateResult(
                document_key=document_key,
                no_op=False,
                previous_content_hash=found.current_content_hash,
                new_content_hash=document.content_hash,
                decision=decision,
            )
        in_place = decision is UpdateDecision.IN_PLACE

        candidates: list[UUID] = []
        if found is not None:
            candidates = await document_entity_candidates(
                graph_store, found.document_node_id
            )
        chunked = await asyncio.to_thread(
            chunk_documents, [document], chunker=chunker, tracer=tracer
        )
        chunks = [chunk for cd in chunked for chunk in cd.chunks]
        placements = _placements_of(chunked)
        extracted = await extract_chunks(
            chunks,
            start_index=0,
            extractor=extractor,
            schema=schema,
            error_policy=error_policy,
            settings=extraction_settings,
            llm_extractor=llm_extractor,
            tracer=tracer,
        )
        entities = extracted.entities
        relations = extracted.relations
        extraction_failures = extracted.failures
        # A version with a failed chunk must not read as current. Dropping the
        # stamps makes the next update extract the document again instead of
        # returning a no-op.
        failed_chunk_ids = {failure.item_id for failure in extraction_failures}
        if failed_chunk_ids:
            chunks, [document] = _without_extraction_stamps(chunks, [document])

        components: list[MatchComponent] = []
        deferred = DeferredWrites()
        # The pending write fills the structure ids, and run_cutover_job reads
        # them only after that write, so the list is shared rather than copied.
        keep_node_ids: list[UUID] = [
            chunk.id for chunk in chunks if chunk.id is not None
        ]

        async def _pending(job_id: UUID) -> AddResult:
            batch = await ingest_chunks(
                chunks,
                [document],
                entities,
                relations,
                extraction_failures,
                graph_store=graph_store,
                embedder=embedder,
                graph_schema=schema,
                error_policy=error_policy,
                ingestion=IngestStats(documents=1),
                return_chunks=False,
                job_id=job_id,
                rebuilt_components=components,
                placements=placements,
                tracer=tracer,
                embed_heading_path=embed_heading_path,
                max_llm_pairs=max_llm_pairs,
                candidates=extracted.candidates,
                dropped=extracted.dropped,
                write_candidates=write_candidates,
                deferred=deferred,
                reuse_chunks=in_place,
            )
            keep_node_ids.extend(batch.structure_node_ids)
            return batch.add_result

        change = (
            None
            if in_place
            else DocumentChange(
                document_node_id=Document.node_id_for(document_key=document_key),
                document_key=document_key,
                verb="add" if found is None else "update",
                content_hash=document.content_hash,
                previous_content_hash=(
                    found.current_content_hash if found is not None else None
                ),
                version_id=version_id(document),
            )
        )
        add_result, cleanup_failures, parts_closed = await run_cutover_job(
            verb="update",
            document_key=document_key,
            affected_entity_ids=candidates,
            graph_store=graph_store,
            settings=cutover_settings,
            pending_write=_pending,
            cleanup=cleanup,
            components=components,
            deferred=deferred,
            # The node id depends on the key only, so the close also reaches a
            # version that a racing writer committed after the lookup above.
            close_document_node_id=(
                None if in_place else Document.node_id_for(document_key=document_key)
            ),
            keep_node_ids=keep_node_ids,
            tracer=tracer,
            in_place=(
                InPlaceRefresh(
                    document_node_id=found.document_node_id,
                    chunk_ids=[
                        chunk.id
                        for chunk in chunks
                        if chunk.id is not None
                        and str(chunk.id) not in failed_chunk_ids
                    ],
                    extraction_fingerprint=(
                        run.extraction_fingerprint if not failed_chunk_ids else None
                    ),
                )
                if in_place and found is not None
                else None
            ),
            candidate_document_node_id=(
                found.document_node_id
                if found is not None
                else Document.node_id_for(document_key=document_key)
            ),
            change=change,
        )
        return UpdateResult(
            document_key=document_key,
            no_op=False,
            previous_content_hash=(found.current_content_hash if found else None),
            new_content_hash=document.content_hash,
            parts_closed=parts_closed,
            decision=decision,
            add_result=_with_cleanup_failures(add_result, cleanup_failures).model_copy(
                update={
                    "chunking": ChunkingStats.from_documents([document], chunks),
                    "escalation": extracted.report,
                }
            ),
        )


async def delete_document(  # noqa: PLR0913
    document_key: str,
    *,
    graph_store: GraphStore,
    cutover_settings: CutoverJobSettings,
    cleanup: CleanupStep,
    tracer: Tracer,
) -> UpdateResult:
    """Soft-delete one document. ``Graph.delete_document`` documents the arguments."""
    with tracer.start_as_current_span("agrag.ingestion.delete_document"):
        found = await find_document(graph_store, document_key=document_key)
        if found is None:
            return UpdateResult(document_key=document_key, no_op=True)
        candidates = await document_entity_candidates(
            graph_store, found.document_node_id
        )

        change = (
            DocumentChange(
                document_node_id=found.document_node_id,
                document_key=document_key,
                verb="delete",
                content_hash=None,
                previous_content_hash=found.current_content_hash,
                version_id=None,
            )
            if found.has_open_chunks
            else None
        )
        _, _, parts_closed = await run_cutover_job(
            verb="delete_document",
            document_key=document_key,
            affected_entity_ids=candidates,
            graph_store=graph_store,
            settings=cutover_settings,
            pending_write=_no_pending_write,
            cleanup=cleanup,
            deferred=DeferredWrites(),
            close_document_node_id=found.document_node_id,
            candidate_document_node_id=found.document_node_id,
            change=change,
            tracer=tracer,
        )
        return UpdateResult(
            document_key=document_key,
            no_op=False,
            previous_content_hash=found.current_content_hash,
            parts_closed=parts_closed,
        )


async def purge_document(  # noqa: PLR0913
    document_key: str,
    *,
    graph_store: GraphStore,
    cutover_settings: CutoverJobSettings,
    cleanup: CleanupStep,
    tracer: Tracer,
) -> UpdateResult:
    """Hard-delete one document. ``Graph.purge_document`` documents the arguments."""
    with tracer.start_as_current_span("agrag.ingestion.purge_document"):
        found = await find_document(graph_store, document_key=document_key)
        if found is None:
            return UpdateResult(document_key=document_key, no_op=True)
        document_params = {"document_node_id": str(found.document_node_id)}
        counted = await graph_store.execute_read(
            document_chunk_count_query(), document_params
        )
        if not counted or not counted[0]["chunks"]:
            return UpdateResult(document_key=document_key, no_op=True)
        mentioned = await graph_store.execute_read(
            document_mentioned_entities_query(), document_params
        )
        cited = await graph_store.execute_read(
            document_cited_relation_endpoints_query(), document_params
        )
        affected = list(
            dict.fromkeys(UUID(str(row["id"])) for row in [*mentioned, *cited])
        )
        change = DocumentChange(
            document_node_id=found.document_node_id,
            document_key=document_key,
            verb="purge",
            content_hash=None,
            previous_content_hash=found.current_content_hash,
            version_id=None,
        )
        _, _, parts_closed = await run_cutover_job(
            verb="purge_document",
            document_key=document_key,
            affected_entity_ids=affected,
            graph_store=graph_store,
            settings=cutover_settings,
            pending_write=_no_pending_write,
            cleanup=cleanup,
            deferred=DeferredWrites(),
            close_document_node_id=found.document_node_id,
            candidate_document_node_id=found.document_node_id,
            change=change,
            tracer=tracer,
        )
        return UpdateResult(
            document_key=document_key,
            no_op=False,
            previous_content_hash=found.current_content_hash,
            parts_closed=parts_closed,
        )
