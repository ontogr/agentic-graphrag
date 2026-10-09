"""The bodies of ``Graph.add``, ``Graph.update``, and ``Graph.delete_document``.

Each call runs one Cutover Job per document. The job's post-commit work
arrives as ``cleanup``, so the live calls and crash recovery run the same
definition.
"""

import asyncio
import contextlib
import hashlib
import logging
from collections.abc import Awaitable, Callable, Iterable, Sequence
from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.chunking import Chunker
from agrag.chunking.chunker import ChunkedDocument, ChunkPlacement
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import (
    Document,
    SourceFormat,
)
from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.stage_failure import StageFailure, cap_failures
from agrag.cypher.relations import entities_in_documents_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion._cutover import run_cutover_job
from agrag.ingestion._document_lifecycle import find_document
from agrag.ingestion._ingest_pipeline import extract_chunks, ingest_chunks
from agrag.ingestion._structure import placement_map
from agrag.ingestion._walk import SourcesType, chunk_documents, iter_document_batches
from agrag.ingestion.extract import Extractor
from agrag.ingestion.reports import AddResult, UpdateResult
from agrag.ingestion.resolved_entities import MatchComponent
from agrag.ingestion.settings import CutoverJobSettings
from agrag.ingestion.stats import (
    ChunkingStats,
    ExtractionStats,
    IngestStats,
    MergeStats,
    ResolutionStats,
    StorageStats,
)
from agrag.loaders.base import Loader
from agrag.loaders.common import build_prose_document, text_sections
from agrag.loaders.loader_registry import LoaderRegistry
from agrag.loaders.types import ErrorPolicy, LoadStats, ReadOptions, SourceRef
from agrag.loaders.walk import normalize_inline_text
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


logger = logging.getLogger(__name__)

CleanupStep = Callable[[list[UUID], list[UUID]], Awaitable[list[StageFailure]]]


def _vector_collections(retrieval_settings: RetrievalSettings) -> tuple[str, str, str]:
    """Name the collections a job's pending writes can reach."""
    return (
        retrieval_settings.entity_collection,
        retrieval_settings.chunk_collection,
        retrieval_settings.resolved_entity_collection,
    )


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


def _group_by_document(
    chunks: list[Chunk],
    documents: list[Document],
    entities: list[ExtractedEntity],
    relations: list[ExtractedRelation],
    extraction_failures: list[StageFailure],
) -> list[
    tuple[
        str,
        list[Chunk],
        list[Document],
        list[ExtractedEntity],
        list[ExtractedRelation],
        list[StageFailure],
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
    failures_by_key: dict[str, list[StageFailure]] = {key: [] for key in ordered_keys}
    for failure in extraction_failures:
        try:
            failure_key = key_by_chunk_id.get(UUID(str(failure.item_id)))
        except ValueError:
            failure_key = None
        failures_by_key.setdefault(
            _or_first(failure_key, kind=f"Failure {failure.item_id}"), []
        ).append(failure)
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
            failures_by_key[key],
        )
        for key in ordered_keys
    ]


def _merge_add_results(
    results: list[AddResult], *, ingestion: IngestStats, chunking: ChunkingStats
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
        )
    if len(results) == 1:
        return results[0].model_copy(
            update={"ingestion": ingestion, "chunking": chunking}
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
        ),
        merge=MergeStats(
            nodes_created=sum(result.merge.nodes_created for result in results),
            nodes_updated=sum(result.merge.nodes_updated for result in results),
            conflicts_resolved=sum(
                result.merge.conflicts_resolved for result in results
            ),
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
    graph_store: GraphStore,
    embedder: Embedder,
    extractor: Extractor,
    vector_store: VectorStore | None,
    retrieval_settings: RetrievalSettings,
    cutover_settings: CutoverJobSettings,
    chunker: Chunker,
    registry: LoaderRegistry,
    embed_heading_path: bool,
    max_llm_pairs: int,
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
        entities: list[ExtractedEntity] = []
        relations: list[ExtractedRelation] = []
        extraction_failures: list[StageFailure] = []

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
                quarantined=final_stats.quarantined,
                quarantined_items=list(final_stats.quarantined_items),
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
            return AddResult(
                ingestion=ingest,
                chunking=ChunkingStats.from_documents(documents_seen, chunks),
                extraction=extraction,
                resolution=ResolutionStats(),
                merge=MergeStats(),
                storage=StorageStats(),
                chunks=list(chunks) if return_chunks else [],
            )

        async for batch, stats in iter_document_batches(
            source=source,
            text=text,
            documents=documents,
            registry=registry,
            opts=opts,
            error_policy=error_policy,
            loader=loader,
            tracer=tracer,
        ):
            _record_document_keys(batch)
            final_stats.documents = stats.documents
            final_stats.sources = stats.sources
            final_stats.skipped = stats.skipped
            final_stats.quarantined = stats.quarantined
            final_stats.quarantined_items = list(stats.quarantined_items)
            chunk_batch = await asyncio.to_thread(
                chunk_documents, batch, chunker=chunker, tracer=tracer
            )
            flat_batch = [chunk for cd in chunk_batch for chunk in cd.chunks]
            placements_by_id.update(_placements_of(chunk_batch))
            chunks.extend(flat_batch)
            documents_seen.extend(batch)
            (
                batch_entities,
                batch_relations,
                batch_failures,
            ) = await extract_chunks(
                flat_batch,
                start_index=len(entities),
                extractor=extractor,
                schema=schema,
                error_policy=error_policy,
                tracer=tracer,
            )
            entities.extend(batch_entities)
            relations.extend(batch_relations)
            extraction_failures.extend(batch_failures)
            if on_progress is not None:
                with contextlib.suppress(Exception):
                    on_progress(_build_partial_add_result())

        # Assemble the ingestion summary from this call's own walk, then run
        # each document's slice as its own Cutover Job through the shared
        # pipeline core. A job holds only its own document's lease and
        # commits only its own slice; a lease failure aborts the documents
        # still queued while documents that already committed stay
        # committed.
        ingestion = IngestStats(
            documents=final_stats.documents,
            sources=final_stats.sources,
            skipped=final_stats.skipped,
            quarantined=final_stats.quarantined,
            quarantined_items=list(final_stats.quarantined_items),
        )
        vector_collections = _vector_collections(retrieval_settings)
        partials: list[AddResult] = []
        for (
            document_key,
            doc_chunks,
            doc_documents,
            doc_entities,
            doc_relations,
            doc_failures,
        ) in _group_by_document(
            chunks, documents_seen, entities, relations, extraction_failures
        ):
            components: list[MatchComponent] = []

            async def _pending(
                job_id: UUID,
                _components: list[MatchComponent] = components,
                _slice: tuple[
                    list[Chunk],
                    list[Document],
                    list[ExtractedEntity],
                    list[ExtractedRelation],
                    list[StageFailure],
                ] = (
                    doc_chunks,
                    doc_documents,
                    doc_entities,
                    doc_relations,
                    doc_failures,
                ),
            ) -> AddResult:
                (
                    slice_chunks,
                    slice_documents,
                    slice_entities,
                    slice_relations,
                    slice_failures,
                ) = _slice
                batch = await ingest_chunks(
                    slice_chunks,
                    slice_documents,
                    slice_entities,
                    slice_relations,
                    slice_failures,
                    graph_store=graph_store,
                    embedder=embedder,
                    vector_store=vector_store,
                    graph_schema=schema,
                    retrieval_settings=retrieval_settings,
                    error_policy=error_policy,
                    ingestion=IngestStats(documents=1),
                    return_chunks=return_chunks,
                    job_id=job_id,
                    rebuilt_components=_components,
                    placements=placements_by_id,
                    tracer=tracer,
                    embed_heading_path=embed_heading_path,
                    max_llm_pairs=max_llm_pairs,
                )
                return batch.add_result

            partial, cleanup_failures, _ = await run_cutover_job(
                verb="add",
                document_key=document_key,
                affected_entity_ids=[],
                graph_store=graph_store,
                vector_store=vector_store,
                vector_collections=vector_collections,
                settings=cutover_settings,
                pending_write=_pending,
                cleanup=cleanup,
                components=components,
                tracer=tracer,
            )
            partials.append(_with_cleanup_failures(partial, cleanup_failures))
        result = _merge_add_results(
            partials,
            ingestion=ingestion,
            chunking=ChunkingStats.from_documents(documents_seen, chunks),
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
    loader: Loader | None,
    error_policy: ErrorPolicy,
    read_options: ReadOptions | None,
    schema: GraphSchema,
    graph_store: GraphStore,
    embedder: Embedder,
    extractor: Extractor,
    vector_store: VectorStore | None,
    retrieval_settings: RetrievalSettings,
    cutover_settings: CutoverJobSettings,
    chunker: Chunker,
    registry: LoaderRegistry,
    embed_heading_path: bool,
    max_llm_pairs: int,
    cleanup: CleanupStep,
    tracer: Tracer,
) -> UpdateResult:
    """Replace one document version. ``Graph.update`` documents the arguments."""
    with tracer.start_as_current_span("agrag.ingestion.update"):
        if (text is None) == (source is None):
            raise ValueError("Provide exactly one of 'text' or 'source'.")

        opts = read_options or ReadOptions()
        if text is not None:
            normalized, normalization = normalize_inline_text(text, opts)
            content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            document = build_prose_document(
                source=SourceRef(uri=document_key, extension=".txt"),
                text=normalized,
                encoding="utf-8",
                source_format=SourceFormat.TXT,
                loader_name="inline",
                opts=opts,
                title="inline",
                sections=text_sections(normalized),
                content_hash=content_hash,
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
                update={"document_key": document_key}
            )

        found = await find_document(graph_store, document_key=document_key)
        if (
            found is not None
            and found.current_content_hash == document.content_hash
            and found.current_chunker_hash in (None, chunker.fingerprint)
        ):
            return UpdateResult(
                document_key=document_key,
                no_op=True,
                previous_content_hash=found.current_content_hash,
                new_content_hash=document.content_hash,
            )

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
        entities, relations, extraction_failures = await extract_chunks(
            chunks,
            start_index=0,
            extractor=extractor,
            schema=schema,
            error_policy=error_policy,
            tracer=tracer,
        )

        components: list[MatchComponent] = []
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
                vector_store=vector_store,
                graph_schema=schema,
                retrieval_settings=retrieval_settings,
                error_policy=error_policy,
                ingestion=IngestStats(documents=1),
                return_chunks=False,
                job_id=job_id,
                rebuilt_components=components,
                placements=placements,
                tracer=tracer,
                embed_heading_path=embed_heading_path,
                max_llm_pairs=max_llm_pairs,
            )
            keep_node_ids.extend(batch.structure_node_ids)
            return batch.add_result

        add_result, cleanup_failures, chunks_closed = await run_cutover_job(
            verb="update",
            document_key=document_key,
            affected_entity_ids=candidates,
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collections=_vector_collections(retrieval_settings),
            settings=cutover_settings,
            pending_write=_pending,
            cleanup=cleanup,
            components=components,
            close_document_node_id=(
                found.document_node_id if found is not None else None
            ),
            keep_node_ids=keep_node_ids,
            tracer=tracer,
        )
        return UpdateResult(
            document_key=document_key,
            no_op=False,
            previous_content_hash=(found.current_content_hash if found else None),
            new_content_hash=document.content_hash,
            chunks_closed=chunks_closed,
            add_result=_with_cleanup_failures(add_result, cleanup_failures).model_copy(
                update={"chunking": ChunkingStats.from_documents([document], chunks)}
            ),
        )


async def delete_document(  # noqa: PLR0913
    document_key: str,
    *,
    graph_store: GraphStore,
    vector_store: VectorStore | None,
    retrieval_settings: RetrievalSettings,
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

        _, _, chunks_closed = await run_cutover_job(
            verb="delete_document",
            document_key=document_key,
            affected_entity_ids=candidates,
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collections=_vector_collections(retrieval_settings),
            settings=cutover_settings,
            pending_write=_no_pending_write,
            cleanup=cleanup,
            close_document_node_id=found.document_node_id,
            tracer=tracer,
        )
        return UpdateResult(
            document_key=document_key,
            no_op=False,
            previous_content_hash=found.current_content_hash,
            chunks_closed=chunks_closed,
        )
