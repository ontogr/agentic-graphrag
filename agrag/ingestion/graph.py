"""The public Graph API for ingestion."""

import asyncio
import contextlib
import functools
import glob
import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Union
from uuid import UUID, uuid4

from opentelemetry.trace import Tracer

import agrag.loaders.docling  # noqa: F401  (registers the docling loaders)
from agrag.chunking import DEFAULT_CHUNKING, Chunking
from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.community import COMMUNITY_LABEL
from agrag.common.data_models.document import (
    DOCUMENT_LABEL,
    Document,
    DocumentFamily,
    SourceFormat,
)
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.relation import Relation
from agrag.common.data_models.resolved_entity import (
    RESOLVED_ENTITY_LABEL,
    ResolvedEntity,
)
from agrag.common.data_models.stage_failure import StageFailure, cap_failures
from agrag.common.text import normalize_text
from agrag.cypher.entities import (
    fetch_all_by_label_query,
)
from agrag.cypher.relations import entities_in_documents_query
from agrag.cypher.resolution_read import fetch_active_matches_among_ids_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.graphdb.entities import load_entities
from agrag.graphdb.serialize import parse_entity_node
from agrag.ingestion._cutover import run_cutover_job
from agrag.ingestion._document_lifecycle import find_document
from agrag.ingestion._ingest_pipeline import (
    _delete_vectors,
    _upsert_vectors,
    _vector_record,
    extract_chunks,
    ingest_chunks,
)
from agrag.ingestion._resume import resume_incomplete_jobs
from agrag.ingestion.extract import Extractor
from agrag.ingestion.reports import (
    AddResult,
    CommunityDetectionReport,
    ConsolidationReport,
    ReevaluationReport,
    UpdateResult,
)
from agrag.ingestion.resolve import (
    SYSTEM_RELATION_TYPES,
    resolve_among,
    resolve_persisted,
)
from agrag.ingestion.resolve.zone_classifier import MAX_LLM_PAIRS
from agrag.ingestion.resolved_embeddings import _synchronize_resolved_entity_vectors
from agrag.ingestion.resolved_entities import (
    MatchComponent,
    MatchDecision,
    deactivate_match_and_rebuild,
    match_decision_components,
    matches_id,
    prune_orphaned_entities,
    rebuild_resolved_entities,
    write_matches_and_rebuild,
)
from agrag.ingestion.settings import CutoverJobSettings
from agrag.ingestion.stats import (
    ChunkingMatch,
    ChunkingStats,
    ExtractionStats,
    IngestStats,
    MergeStats,
    ResolutionStats,
    StorageStats,
)
from agrag.loaders.corpus import registry as _corpus_registry
from agrag.loaders.corpus._walk import (
    _CorpusWalk,
    _InMemoryWalk,
    normalize_inline_text,
)
from agrag.loaders.corpus.base import Loader
from agrag.loaders.corpus.types import ErrorPolicy, LoadStats, ReadOptions
from agrag.observability import get_tracer, record_stage_failure
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


SourceType = Union[str, Path]
SourcesType = Union[SourceType, Sequence[SourceType]]


def _resolve_paths(source: SourcesType) -> tuple[list[Path], bool]:
    """Expand a source argument into concrete file paths.

    Args:
        source: A file path, a directory, a glob, or a list of these.

    Returns:
        The resolved file paths in sorted order and whether the input was a single plain
        file (not a directory or glob).
    """
    items = source if isinstance(source, (list, tuple)) else [source]
    paths: list[Path] = []
    single_file = len(items) == 1
    for item in items:
        text = str(item)
        path = Path(text)
        if path.is_dir():
            single_file = False
            paths.extend(sorted(p for p in path.rglob("*") if p.is_file()))
        elif any(ch in text for ch in "*?["):
            single_file = False
            paths.extend(
                sorted(
                    Path(m)
                    for m in glob.glob(text, recursive=True)
                    if Path(m).is_file()
                )
            )
        else:
            paths.append(path)
    return paths, single_file


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
    """Split one call's pipeline inputs into per-document slices.

    Each slice carries one document's chunks, mentions, relations, and
    extraction failures, so it can ingest as its own Cutover Job. Order
    follows the documents' first occurrence. A chunk, mention, or failure
    that maps to no listed document joins the first slice rather than
    being dropped; with no documents at all but stray chunks, the first
    chunk's document linkage keys the single slice.

    Args:
        chunks: The call's chunks, in document then chunk order.
        documents: The call's documents, possibly repeating.
        entities: Mentions addressing chunks by id.
        relations: Relations whose indices address ``entities``. Each slice
            rebases them to its own entity list; a relation whose endpoints
            fall in different slices is dropped.
        extraction_failures: Failures keyed by chunk id.

    Returns:
        One (document_key, chunks, documents, entities, relations,
        failures) tuple per document.
    """
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
    chunks_by_key: dict[str, list[Chunk]] = {key: [] for key in ordered_keys}
    for chunk in chunks:
        chunks_by_key.setdefault(
            key_by_node_id.get(chunk.document_id, ordered_keys[0]), []
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
        entity_key = key_by_chunk_id.get(entity.chunk_id, ordered_keys[0])
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
        failures_by_key.setdefault(failure_key or ordered_keys[0], []).append(failure)
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

    Each document in an add() call commits as its own Cutover Job; the
    caller still gets a single AddResult shaped exactly like a one-job
    call's. Counters sum, failure lists concatenate re-capped against the
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


class Graph:
    """A knowledge graph that a caller can open and add content to.

    When an optional VectorStore is configured, every embedding this
    graph writes to graph_store is also upserted there, so SearchEngine's
    VectorStore path finds the same vectors the GraphStore-native path
    does. Collections follow RetrievalSettings' names and are provisioned
    by ``open()`` when missing.
    """

    def __init__(
        self,
        *,
        schema: GraphSchema,
        graph_store: GraphStore,
        embedder: Embedder,
        extractor: Extractor,
        tracer: Tracer | None = None,
        vector_store: VectorStore | None = None,
        retrieval_settings: RetrievalSettings | None = None,
        cutover_settings: CutoverJobSettings | None = None,
        chunking: Chunking = DEFAULT_CHUNKING,
        embed_heading_path: bool = True,
        max_llm_pairs: int = MAX_LLM_PAIRS,
    ) -> None:
        """Create a graph bound to a schema, store, embedder, and extractor.

        Args:
            schema: The entity/relation types this graph validates every
                extraction against.
            graph_store: Where entities, relations, chunks, and MENTIONED_IN
                edges are written.
            embedder: Populates entity embeddings for native vector search.
            extractor: Runs against each chunk.
            tracer: A tracer to record spans for every step. Pass None for none.
            vector_store: Optional second write target for embeddings. When
                set, every embedding the pipeline writes to graph_store is
                also upserted here, so SearchEngine's VectorStore path finds
                the same vectors the GraphStore-native path does. Also gets
                old community vectors removed on each
                detect_communities(apply=True) cycle.
            retrieval_settings: Collection names for the VectorStore writes.
                None uses RetrievalSettings defaults. Ignored when
                vector_store is None.
            cutover_settings: Lease configuration for the Cutover Jobs
                add/update/delete_document run through. None uses
                CutoverJobSettings defaults.
            chunking: The rules that pick a chunker for each document. The
                default is ``DEFAULT_CHUNKING``.
            embed_heading_path: Whether chunk embeddings include the chunk's
                heading path above its text. The stored text does not change.
                Existing embeddings stay until a document is re-chunked with
                ``update()``.
            max_llm_pairs: The most ambiguous entity pairs that resolution sends
                to the LLM for each label. A lower value bounds the number of
                verification calls and leaves more pairs undecided.
        """
        self._schema = schema
        self._graph_store = graph_store
        self._embedder = embedder
        self._extractor = extractor
        self._tracer = get_tracer(tracer)
        self._registry = _corpus_registry
        self._chunking = chunking
        self._embed_heading_path = embed_heading_path
        self._max_llm_pairs = max_llm_pairs
        self._vector_store = vector_store
        self._retrieval_settings = retrieval_settings or RetrievalSettings()
        self._cutover_settings = cutover_settings or CutoverJobSettings()

    @classmethod
    async def open(
        cls,
        *,
        schema: GraphSchema,
        graph_store: GraphStore,
        embedder: Embedder,
        extractor: Extractor,
        tracer: Tracer | None = None,
        vector_store: VectorStore | None = None,
        retrieval_settings: RetrievalSettings | None = None,
        cutover_settings: CutoverJobSettings | None = None,
        chunking: Chunking = DEFAULT_CHUNKING,
        embed_heading_path: bool = True,
        max_llm_pairs: int = MAX_LLM_PAIRS,
    ) -> "Graph":
        """Open a graph, connecting and fully provisioning graph_store.

        Provisioning order: connect, then register every label/relation type
        this graph will ever write (schema's own labels/types plus the fixed
        system names CHUNK_LABEL/SYSTEM_RELATION_TYPES), then
        setup_constraints(), then setup_indexes(), then vector indexes for
        every schema entity label — so a brand-new database is fully ready,
        including the merge_key uniqueness constraints the global exact-match
        tier relies on and the embedding vector indexes native search needs,
        before this call returns. When vector_store is set, the entity, chunk,
        and community collections are provisioned there too (created when
        missing) so the dual writes never hit an absent collection.

        Args:
            schema: The entity/relation types this graph validates every
                extraction against.
            graph_store: Where entities, relations, chunks, and MENTIONED_IN
                edges are written.
            embedder: Populates entity embeddings for native vector search.
            extractor: Runs against each chunk.
            tracer: A tracer to record spans for every step. Pass None for none.
            vector_store: Optional second write target for embeddings; see
                __init__.
            retrieval_settings: Collection names for the VectorStore writes.
                None uses RetrievalSettings defaults.
            cutover_settings: Lease configuration for the Cutover Jobs
                add/update/delete_document run through. None uses
                CutoverJobSettings defaults.
            chunking: The rules that pick a chunker for each document; see
                __init__.
            embed_heading_path: Whether chunk embeddings include the heading path;
                see __init__.
            max_llm_pairs: The most ambiguous entity pairs sent to the LLM for each
                label during resolution; see __init__.

        Returns:
            A graph connected to graph_store and ready to accept add() calls.

        Raises:
            EmbeddingDimensionMismatchError: A vector index in graph_store
                already exists with a different dimension than the embedder
                produces.
            CollectionDimensionMismatchError: A vector_store collection
                already exists with a different dimension than the embedder
                produces.
            Exception: Whatever connect(), registration, constraint/index
                setup, or vector-index provisioning raises. graph_store is
                closed first, so a failed open() never leaks a connection.
        """
        resolved_tracer = get_tracer(tracer)
        with resolved_tracer.start_as_current_span("agrag.ingestion.open"):
            try:
                await graph_store.connect()
                entity_labels = [entity_type.label for entity_type in schema.entities]
                relation_types = [
                    relation_type.label for relation_type in schema.relations
                ]
                await graph_store.register_labels(
                    [
                        *entity_labels,
                        CHUNK_LABEL,
                        COMMUNITY_LABEL,
                        DOCUMENT_LABEL,
                        RESOLVED_ENTITY_LABEL,
                    ]
                )
                await graph_store.register_relation_types(
                    [*relation_types, *SYSTEM_RELATION_TYPES]
                )
                await graph_store.setup_constraints()
                await graph_store.setup_indexes()
                dimensions = await embedder.dimensions()
                distance = embedder.distance
                for label in entity_labels:
                    await graph_store.ensure_vector_index(
                        label=label,
                        vector_property="embedding",
                        dimensions=dimensions,
                        distance=distance,
                    )
                await graph_store.ensure_vector_index(
                    label=CHUNK_LABEL,
                    vector_property="embedding",
                    dimensions=dimensions,
                    distance=distance,
                )
                await graph_store.ensure_vector_index(
                    label=COMMUNITY_LABEL,
                    vector_property="embedding",
                    dimensions=dimensions,
                    distance=distance,
                )
                await graph_store.ensure_vector_index(
                    label=RESOLVED_ENTITY_LABEL,
                    vector_property="embedding",
                    dimensions=dimensions,
                    distance=distance,
                )
                recovery_collections: tuple[str, ...] = ()
                if vector_store is not None:
                    settings = retrieval_settings or RetrievalSettings()
                    recovery_collections = (
                        settings.entity_collection,
                        settings.chunk_collection,
                        settings.resolved_entity_collection,
                    )
                    await vector_store.initialize()
                    # Wait for every task even after a failure so none still uses
                    # the store when the except block below closes it.
                    outcomes = await asyncio.gather(
                        *(
                            vector_store.ensure_collection(
                                collection,
                                dimensions=dimensions,
                                distance=distance,
                                hybrid=True,
                            )
                            for collection in (
                                settings.entity_collection,
                                settings.resolved_entity_collection,
                                settings.chunk_collection,
                                settings.community_collection,
                            )
                        ),
                        return_exceptions=True,
                    )
                    for outcome in outcomes:
                        if isinstance(outcome, BaseException):
                            raise outcome
                graph = cls(
                    schema=schema,
                    graph_store=graph_store,
                    embedder=embedder,
                    extractor=extractor,
                    tracer=tracer,
                    vector_store=vector_store,
                    retrieval_settings=retrieval_settings,
                    cutover_settings=cutover_settings,
                    chunking=chunking,
                    embed_heading_path=embed_heading_path,
                    max_llm_pairs=max_llm_pairs,
                )
                # Crash recovery, last: every index and collection the
                # recovery paths rely on now exists. A pending job (its worker
                # died pre-commit) rolls back; a committed or cleaning job
                # rolls forward, rerunning the cleanup phase this graph's own
                # calls run after their commit. A recovery failure is
                # swallowed: opening the graph must not break because a
                # leftover job could not be finished, and the pending filters
                # keep any tagged writes invisible to retrieval until a later
                # open succeeds.
                with contextlib.suppress(Exception):
                    await resume_incomplete_jobs(
                        graph_store,
                        vector_store=vector_store,
                        vector_collections=recovery_collections,
                        roll_forward=graph._finish_job,
                        lease_ttl_seconds=graph._cutover_settings.lease_ttl_seconds,
                        tracer=resolved_tracer,
                    )
            except Exception:
                await graph_store.close()
                if vector_store is not None:
                    with contextlib.suppress(Exception):
                        await vector_store.close()
                raise
        return graph

    @property
    def chunking(self) -> Chunking:
        """The rules that pick a chunker for each document."""
        return self._chunking

    async def add(  # noqa: PLR0912,PLR0915,PLR0913
        self,
        source: SourcesType | None = None,
        *,
        text: str | None = None,
        documents: Sequence[Document] | None = None,
        loader: Loader | None = None,
        error_policy: ErrorPolicy = ErrorPolicy.RAISE,
        on_progress: Callable[[AddResult], None] | None = None,
        return_chunks: bool = False,
        read_options: ReadOptions | None = None,
    ) -> AddResult:
        """Add content to the graph.

        Give exactly one of ``source``, ``text``, and ``documents``.

        Args:
            source: A file path, a directory, a glob, or a list of these.
            text: Raw text to add as one document.
            documents: Already-built documents to add directly.
            loader: A loader to use instead of the registry default. Requires a
                single-file ``source``; a directory, glob, or list of sources raises an
                error.
            error_policy: The action to take on a per-source error.
            on_progress: A callback the call runs after each batch and once more
                at the end with the fully-populated result.
            return_chunks: Whether to include the produced chunks in the
                returned AddResult. False by default to avoid holding full text
                for a large corpus when not needed.
            read_options: How loaders read sources, including the normalization of
                decoded text. None uses ``ReadOptions()`` defaults.

        Returns:
            A summary of what was added per pipeline stage. Resolution runs
            automatically: exact identity plus fuzzy, embedding, and
            capped LLM zones over one combined mention list, with
            confirmed matches persisted as MATCHES edges and derived
            ResolvedEntity nodes. LLM verification calls stay bounded
            at ceil(L * MAX_LLM_PAIRS / 10) requests for L labels;
            inspect result.resolution.ambiguous_count for the pairs no
            tier could decide.

        Raises:
            ValueError: The call got zero, or more than one, of ``source``, ``text``,
                and ``documents``. Also raised when ``loader`` is set without
                ``source``, or with a source that can match more than one file.
            UnsupportedFormatError: No loader is registered for a source's format.
            MissingExtraError: A loader is registered for a source's format, but its
                package extra is not installed. This error follows ``error_policy``
                instead of always stopping the call.
            ValueError: The input contains multiple documents with the same
                ``document_key``.
        """
        with self._tracer.start_as_current_span("agrag.ingestion.add"):
            opts = read_options or ReadOptions()
            given = sum(x is not None for x in (source, text, documents))
            if given != 1:
                raise ValueError(
                    "Provide exactly one of 'source', 'text', or 'documents'; "
                    f"got {given}."
                )
            if loader is not None and source is None:
                raise ValueError(
                    "A loader override requires 'source'; it has no effect on "
                    "'text' or 'documents'."
                )

            chunks: list[Chunk] = []
            chunk_matches: list[ChunkingMatch] = []
            documents_seen: list[Document] = []
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
                    chunks_processed=sum(c.parent_id is None for c in chunks),
                    entities_extracted=len(entities),
                    relations_extracted=len(relations),
                    failures=extraction_failures_capped.items,
                    failures_total=extraction_failures_capped.total,
                    failures_truncated=extraction_failures_capped.truncated,
                )
                return AddResult(
                    ingestion=ingest,
                    chunking=ChunkingStats.from_matches(list(chunk_matches)),
                    extraction=extraction,
                    resolution=ResolutionStats(),
                    merge=MergeStats(),
                    storage=StorageStats(),
                    chunks=list(chunks) if return_chunks else [],
                )

            # Stream ingestion + extraction per walk-batch, collecting all mentions
            if documents is not None:
                # Single synthetic batch from provided documents
                docs_list = list(documents)
                _record_document_keys(docs_list)
                final_stats.documents = len(docs_list)
                final_stats.sources = 0
                # Chunk all at once (still via thread)
                chunk_batch, batch_matches = await asyncio.to_thread(
                    self._chunk_documents, docs_list
                )
                chunks.extend(chunk_batch)
                chunk_matches.extend(batch_matches)
                documents_seen.extend(docs_list)
                batch_entities, batch_relations, batch_failures = await extract_chunks(
                    chunk_batch,
                    start_index=len(entities),
                    extractor=self._extractor,
                    schema=self._schema,
                    error_policy=error_policy,
                    tracer=self._tracer,
                )
                entities.extend(batch_entities)
                relations.extend(batch_relations)
                extraction_failures.extend(batch_failures)
                # Fire on_progress once for the synthetic batch (partial)
                if on_progress is not None:
                    with contextlib.suppress(Exception):
                        on_progress(_build_partial_add_result())
            elif text is not None:
                walk = _InMemoryWalk(text, opts=opts)
                batches = walk.iter_batches()
                async for batch, _cursor, stats in batches:
                    _record_document_keys(batch)
                    # Stats is LoadStats
                    final_stats.documents = stats.documents
                    final_stats.sources = stats.sources
                    final_stats.skipped = stats.skipped
                    final_stats.quarantined = stats.quarantined
                    final_stats.quarantined_items = list(stats.quarantined_items)
                    # Chunk this batch
                    chunk_batch, batch_matches = await asyncio.to_thread(
                        self._chunk_documents, batch
                    )
                    chunks.extend(chunk_batch)
                    chunk_matches.extend(batch_matches)
                    documents_seen.extend(batch)
                    (
                        batch_entities,
                        batch_relations,
                        batch_failures,
                    ) = await extract_chunks(
                        chunk_batch,
                        start_index=len(entities),
                        extractor=self._extractor,
                        schema=self._schema,
                        error_policy=error_policy,
                        tracer=self._tracer,
                    )
                    entities.extend(batch_entities)
                    relations.extend(batch_relations)
                    extraction_failures.extend(batch_failures)
                    if on_progress is not None:
                        with contextlib.suppress(Exception):
                            on_progress(_build_partial_add_result())
            else:
                assert source is not None
                paths, single_file = _resolve_paths(source)
                if loader is not None and not single_file:
                    raise ValueError(
                        "A loader override requires a single-file source, not a "
                        "directory, glob, or list of sources."
                    )
                walk = _CorpusWalk(
                    paths,
                    registry=self._registry,
                    opts=opts,
                    error_policy=error_policy,
                    loader=loader,
                    tracer=self._tracer,
                )
                batches = walk.iter_batches()
                async for batch, _cursor, stats in batches:
                    _record_document_keys(batch)
                    final_stats.documents = stats.documents
                    final_stats.sources = stats.sources
                    final_stats.skipped = stats.skipped
                    final_stats.quarantined = stats.quarantined
                    final_stats.quarantined_items = list(stats.quarantined_items)
                    chunk_batch, batch_matches = await asyncio.to_thread(
                        self._chunk_documents, batch
                    )
                    chunks.extend(chunk_batch)
                    chunk_matches.extend(batch_matches)
                    documents_seen.extend(batch)
                    (
                        batch_entities,
                        batch_relations,
                        batch_failures,
                    ) = await extract_chunks(
                        chunk_batch,
                        start_index=len(entities),
                        extractor=self._extractor,
                        schema=self._schema,
                        error_policy=error_policy,
                        tracer=self._tracer,
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
            vector_collections = (
                self._retrieval_settings.entity_collection,
                self._retrieval_settings.chunk_collection,
                self._retrieval_settings.resolved_entity_collection,
            )
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
                    return await ingest_chunks(
                        slice_chunks,
                        slice_documents,
                        slice_entities,
                        slice_relations,
                        slice_failures,
                        graph_store=self._graph_store,
                        embedder=self._embedder,
                        vector_store=self._vector_store,
                        graph_schema=self._schema,
                        retrieval_settings=self._retrieval_settings,
                        error_policy=error_policy,
                        ingestion=IngestStats(documents=1),
                        return_chunks=return_chunks,
                        job_id=job_id,
                        rebuilt_components=_components,
                        tracer=self._tracer,
                        embed_heading_path=self._embed_heading_path,
                        max_llm_pairs=self._max_llm_pairs,
                    )

                partial, cleanup_failures, _ = await run_cutover_job(
                    verb="add",
                    document_key=document_key,
                    affected_entity_ids=[],
                    graph_store=self._graph_store,
                    vector_store=self._vector_store,
                    vector_collections=vector_collections,
                    settings=self._cutover_settings,
                    pending_write=_pending,
                    cleanup=functools.partial(
                        self._finish_job, error_policy=error_policy
                    ),
                    components=components,
                    tracer=self._tracer,
                )
                partials.append(_with_cleanup_failures(partial, cleanup_failures))
            result = _merge_add_results(
                partials,
                ingestion=ingestion,
                chunking=ChunkingStats.from_matches(chunk_matches),
            )

            if on_progress is not None:
                with contextlib.suppress(Exception):
                    on_progress(result)

            return result

    async def update(
        self,
        document_key: str,
        *,
        text: str | None = None,
        source: SourcesType | None = None,
        loader: Loader | None = None,
        error_policy: ErrorPolicy = ErrorPolicy.RAISE,
        read_options: ReadOptions | None = None,
    ) -> UpdateResult:
        """Replace one document version, closing its former PART_OF edges.

        Looks up the persisted ``Document`` node by ``document_key``. An
        unchanged content hash is a no-op returning before any chunking,
        extraction, or writes, unless the chunker that this graph's rules pick
        for the document differs from the one that made its current chunks. A
        chunker with new settings re-chunks the document as a content change
        does. Chunks written before chunkers were recorded count as unchanged.
        Otherwise the fresh content ingests under a Cutover Job holding this
        document's lease, and the commit flips the job, closes the document's
        open ``PART_OF`` edges, and clears every pending tag in one
        transaction — so a crash either leaves
        the old version untouched or completes the replacement including
        cleanup. Entities that lose their last evidence are pruned after
        the commit, so replacement mentions count as evidence. A source
        must resolve to exactly one document.

        Args:
            document_key: The stable key of the document to replace.
            text: Replacement text, exactly one of ``text``/``source``.
            source: A single-file source, glob, or path list resolving to
                exactly one document.
            loader: A loader override for a single-file ``source``.
            error_policy: RAISE propagates a stage failure; any other
                policy records it and continues.
            read_options: How loaders read the replacement, including the
                normalization of its text. None uses ``ReadOptions()`` defaults.

        Returns:
            The update summary. A no-op reports ``no_op=True`` with no
            ``add_result``; a change reports ``chunks_closed`` plus the
            fresh ingestion's ``add_result``; an unknown ``document_key``
            ingests fresh with ``previous_content_hash=None`` and
            ``chunks_closed=0``.

        Raises:
            ValueError: Both or neither of ``text`` and ``source`` are given, a loader
                override targets multiple sources, or a source resolves to any number
                of documents other than one.

        Note:
            The fresh-content path shares ``ingest_chunks()`` with
            ``Graph.add()``; both callers observe the same pipeline behavior
            for the same input.
        """
        with self._tracer.start_as_current_span("agrag.ingestion.update"):
            if (text is None) == (source is None):
                raise ValueError("Provide exactly one of 'text' or 'source'.")

            opts = read_options or ReadOptions()
            if text is not None:
                normalized, normalization = normalize_inline_text(text, opts)
                content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
                document = Document(
                    text=normalized,
                    title="inline",
                    uri=document_key,
                    document_key=document_key,
                    source_format=SourceFormat.TXT,
                    family=DocumentFamily.PROSE,
                    content_hash=content_hash,
                    loader_name="inline",
                    encoding="utf-8",
                    char_count=len(normalized),
                    line_count=normalized.count("\n") + 1,
                    normalization=normalization,
                )
            else:
                assert source is not None
                paths, single_file = _resolve_paths(source)
                if loader is not None and not single_file:
                    raise ValueError(
                        "A loader override requires a single-file source, not a "
                        "directory, glob, or list of sources."
                    )
                walk = _CorpusWalk(
                    paths,
                    registry=self._registry,
                    opts=opts,
                    error_policy=error_policy,
                    loader=loader,
                    tracer=self._tracer,
                )
                documents_from_source: list[Document] = []
                async for batch, _cursor, _stats in walk.iter_batches():
                    documents_from_source.extend(batch)
                if len(documents_from_source) != 1:
                    raise ValueError("The source must produce exactly one document.")
                document = documents_from_source[0].model_copy(
                    update={"document_key": document_key}
                )

            found = await find_document(self._graph_store, document_key=document_key)
            _, chunker = self._chunking.select(document)
            if (
                found is not None
                and found.current_content_hash == document.content_hash
                and found.current_chunker_hash in (None, chunker.fingerprint())
            ):
                return UpdateResult(
                    document_key=document_key,
                    no_op=True,
                    previous_content_hash=found.current_content_hash,
                    new_content_hash=document.content_hash,
                )

            candidates: list[UUID] = []
            if found is not None:
                candidates = await self._document_entity_candidates(
                    found.document_node_id
                )
            chunks, chunk_matches = await asyncio.to_thread(
                self._chunk_documents, [document]
            )
            entities, relations, extraction_failures = await extract_chunks(
                chunks,
                start_index=0,
                extractor=self._extractor,
                schema=self._schema,
                error_policy=error_policy,
                tracer=self._tracer,
            )

            components: list[MatchComponent] = []

            async def _pending(job_id: UUID) -> AddResult:
                return await ingest_chunks(
                    chunks,
                    [document],
                    entities,
                    relations,
                    extraction_failures,
                    graph_store=self._graph_store,
                    embedder=self._embedder,
                    vector_store=self._vector_store,
                    graph_schema=self._schema,
                    retrieval_settings=self._retrieval_settings,
                    error_policy=error_policy,
                    ingestion=IngestStats(documents=1),
                    return_chunks=False,
                    job_id=job_id,
                    rebuilt_components=components,
                    tracer=self._tracer,
                    embed_heading_path=self._embed_heading_path,
                    max_llm_pairs=self._max_llm_pairs,
                )

            add_result, cleanup_failures, chunks_closed = await run_cutover_job(
                verb="update",
                document_key=document_key,
                affected_entity_ids=candidates,
                graph_store=self._graph_store,
                vector_store=self._vector_store,
                vector_collections=(
                    self._retrieval_settings.entity_collection,
                    self._retrieval_settings.chunk_collection,
                    self._retrieval_settings.resolved_entity_collection,
                ),
                settings=self._cutover_settings,
                pending_write=_pending,
                cleanup=functools.partial(self._finish_job, error_policy=error_policy),
                components=components,
                close_document_node_id=(
                    found.document_node_id if found is not None else None
                ),
                keep_chunk_ids=[chunk.id for chunk in chunks if chunk.id is not None],
                tracer=self._tracer,
            )
            return UpdateResult(
                document_key=document_key,
                no_op=False,
                previous_content_hash=(found.current_content_hash if found else None),
                new_content_hash=document.content_hash,
                chunks_closed=chunks_closed,
                add_result=_with_cleanup_failures(
                    add_result, cleanup_failures
                ).model_copy(
                    update={"chunking": ChunkingStats.from_matches(chunk_matches)}
                ),
            )

    async def delete_document(self, document_key: str) -> UpdateResult:
        """Soft-delete a document by closing its current PART_OF edges.

        Currency is read transitively through ``PART_OF``: closing the
        open edges removes the document from retrieval while its chunks,
        the ``Document`` node, and contributed entities stay in the graph
        for provenance. An unknown ``document_key`` is a no-op. Entities
        mentioned only by this document's chunks lose their last evidence
        and are pruned with their shrunken clusters. The close and the
        prune run as one job's commit and cleanup, so a crash either
        leaves the document untouched or completes the deletion.

        Args:
            document_key: The stable key of the document to delete.

        Returns:
            The deletion summary: ``no_op=True`` when nothing was stored
            under the key, otherwise ``chunks_closed`` with
            ``new_content_hash=None`` and no ``add_result``.

        Note:
            The close-only degenerate case of ``Graph.update()``; both
            call into the same shared document-lifecycle helpers. See
            ``Graph.add()`` for the shared ingestion behavior.
        """
        with self._tracer.start_as_current_span("agrag.ingestion.delete_document"):
            found = await find_document(self._graph_store, document_key=document_key)
            if found is None:
                return UpdateResult(document_key=document_key, no_op=True)
            candidates = await self._document_entity_candidates(found.document_node_id)

            _, _, chunks_closed = await run_cutover_job(
                verb="delete_document",
                document_key=document_key,
                affected_entity_ids=candidates,
                graph_store=self._graph_store,
                vector_store=self._vector_store,
                vector_collections=(
                    self._retrieval_settings.entity_collection,
                    self._retrieval_settings.chunk_collection,
                    self._retrieval_settings.resolved_entity_collection,
                ),
                settings=self._cutover_settings,
                pending_write=_no_pending_write,
                cleanup=self._finish_job,
                close_document_node_id=found.document_node_id,
                tracer=self._tracer,
            )
            return UpdateResult(
                document_key=document_key,
                no_op=False,
                previous_content_hash=found.current_content_hash,
                chunks_closed=chunks_closed,
            )

    async def _document_entity_candidates(self, document_node_id: UUID) -> list[UUID]:
        """Return live entity ids mentioned by a document's open chunks.

        Args:
            document_node_id: The persisted Document node's id.

        Returns:
            The mentioned entity ids in first-seen order.
        """
        rows = await self._graph_store.execute_read(
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

    async def _finish_job(
        self,
        affected_entity_ids: list[UUID],
        component_seed_ids: list[UUID],
        *,
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
            error_policy: RAISE propagates the first failure; any other
                policy records it and continues. Recovery uses RAISE, so a
                failure leaves the job in ``cleaning`` for a later open.

        Returns:
            The failures recorded while rebuilding components.
        """
        failures = await self._rebuild_resolved_entities(
            component_seed_ids, error_policy=error_policy
        )
        await self._prune_document_entities(affected_entity_ids)
        return failures

    async def _rebuild_resolved_entities(
        self, component_seed_ids: list[UUID], *, error_policy: ErrorPolicy
    ) -> list[StageFailure]:
        """Rebuild committed components' resolved entities and sync vectors.

        The replaced resolved entities' vectors are deleted and the new ones
        written to the graph and the external vector store. Persisted vector
        deletions from earlier passes are retried even when no seed is given.

        Args:
            component_seed_ids: One member id per component to rebuild.
            error_policy: RAISE propagates the first failure; any other
                policy records it and continues.

        Returns:
            The recorded failures.
        """
        with self._tracer.start_as_current_span(
            "agrag.merge.rebuild_components",
            attributes={"agrag.component_count": len(component_seed_ids)},
        ):
            failures: list[StageFailure] = []
            rebuilt: list[ResolvedEntity] = []
            replaced_ids: list[UUID] = []
            for seed_id in component_seed_ids:
                with self._tracer.start_as_current_span(
                    "agrag.merge.rebuild_component"
                ) as span:
                    try:
                        results = await rebuild_resolved_entities(
                            [seed_id],
                            graph_store=self._graph_store,
                            schema=self._schema,
                            tracer=self._tracer,
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
                    embedder=self._embedder,
                    graph_store=self._graph_store,
                    vector_store=self._vector_store,
                    vector_collection=self._retrieval_settings.resolved_entity_collection,
                    error_policy=error_policy,
                )
            )
            return failures

    async def _rebuild_components(
        self, components: list[MatchComponent], *, error_policy: ErrorPolicy
    ) -> tuple[list[ResolvedEntity], list[StageFailure]]:
        """Rebuild committed match components and sync their vectors.

        Runs outside any Cutover Job, so each write replaces the previous
        rebuild of the components it grows or merges, including its
        ``RESOLVED_AS`` edges. The replaced vectors are then deleted and the
        new ones written to the graph and the external vector store.

        Args:
            components: The match decisions and raw members of each
                component to rebuild.
            error_policy: RAISE propagates the first failure; any other
                policy records it and continues.

        Returns:
            The resolved-entities and the recorded failures.
        """
        with self._tracer.start_as_current_span(
            "agrag.merge.rebuild_components",
            attributes={"agrag.component_count": len(components)},
        ):
            failures: list[StageFailure] = []
            rebuilt: list[ResolvedEntity] = []
            replaced_ids: list[UUID] = []
            for decisions, members in components:
                with self._tracer.start_as_current_span(
                    "agrag.merge.rebuild_component",
                    attributes={"agrag.member_count": len(members)},
                ):
                    try:
                        rebuild = await write_matches_and_rebuild(
                            decisions,
                            graph_store=self._graph_store,
                            schema=self._schema,
                            members=members,
                            tracer=self._tracer,
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
                    embedder=self._embedder,
                    graph_store=self._graph_store,
                    vector_store=self._vector_store,
                    vector_collection=self._retrieval_settings.resolved_entity_collection,
                    error_policy=error_policy,
                )
            )
            return rebuilt, failures

    async def _prune_document_entities(self, candidates: list[UUID]) -> None:
        """Prune orphaned candidates and drop their stale vectors.

        Best effort: a vector-store failure never fails the document
        operation that already committed its graph writes.

        Args:
            candidates: Entity ids that may have lost their last evidence.
                Empty skips the pruning pass entirely.
        """
        if not candidates:
            return
        pruning = await prune_orphaned_entities(
            candidates,
            graph_store=self._graph_store,
            schema=self._schema,
            tracer=self._tracer,
        )
        with contextlib.suppress(Exception):
            await _delete_vectors(
                self._vector_store,
                self._retrieval_settings.entity_collection,
                pruning.removed_entity_ids,
            )
        with contextlib.suppress(Exception):
            await _delete_vectors(
                self._vector_store,
                self._retrieval_settings.resolved_entity_collection,
                pruning.removed_resolved_entity_ids,
            )

    def _chunk_documents(
        self, documents: list[Document]
    ) -> tuple[list[Chunk], list[ChunkingMatch]]:
        """Chunk a batch of documents, each with the chunker its rule picks.

        Args:
            documents: The documents to chunk.

        Returns:
            The chunks in document then chunk order, and one match per document
            that records the rule and chunker it got.
        """
        chunks: list[Chunk] = []
        matches: list[ChunkingMatch] = []
        for document in documents:
            rule, chunker = self._chunking.select(document)
            with self._tracer.start_as_current_span(
                "agrag.ingestion.chunk_document",
                attributes={
                    "agrag.document_key": document.resolved_document_key,
                    "agrag.chunker.strategy": chunker.strategy,
                    "agrag.chunker.hash": chunker.fingerprint(),
                    "agrag.chunker.settings": json.dumps(chunker.settings()),
                    "agrag.chunker.rule": "fallback" if rule is None else str(rule),
                },
            ) as span:
                document_chunks = chunker.chunk(document)
                span.set_attribute("agrag.chunks_produced", len(document_chunks))
            chunks.extend(document_chunks)
            by_chunker: dict[str, int] = {}
            for chunk in document_chunks:
                name = chunk.chunker or chunker.strategy
                by_chunker[name] = by_chunker.get(name, 0) + 1
            matches.append(
                ChunkingMatch(
                    document_key=document.resolved_document_key,
                    rule=rule,
                    strategy=chunker.strategy,
                    chunker_hash=chunker.fingerprint(),
                    chunks=len(document_chunks),
                    chunks_by_chunker=by_chunker,
                )
            )
        return chunks, matches

    async def _all_entities_by_label(self, label: str) -> list[Entity]:
        """Return every persisted entity with label, for consolidate().

        Plain pagination through GraphStore.

        Args:
            label: The entity label to fetch.

        Returns:
            All entities with that label.
        """
        entities: list[Entity] = []
        skip = 0
        limit = 256
        while True:
            query = fetch_all_by_label_query(label)
            rows = await self._graph_store.execute_read(
                query, {"skip": skip, "limit": limit}
            )
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

    async def _load_input_entities(self, unique_ids: list[UUID]) -> list[Entity]:
        """Fetch live entities for the given ids, preserving input order.

        Args:
            unique_ids: Deduped entity ids to fetch.

        Returns:
            The live entities in input order.

        Raises:
            ValueError: An id has no live persisted entity.
        """
        entities_by_id = await load_entities(
            self._graph_store, unique_ids, tracer=self._tracer
        )
        missing = [e for e in unique_ids if e not in entities_by_id]
        if missing:
            raise ValueError(
                "Unknown entity ids: " + ", ".join(str(m) for m in missing)
            )
        return [entities_by_id[e] for e in unique_ids]

    async def deactivate_match(self, match_id: UUID) -> list[ResolvedEntity]:
        """Deactivate a semantic match and synchronize replacement retrieval vectors."""
        with self._tracer.start_as_current_span(
            "agrag.ingestion.deactivate_match",
            attributes={"agrag.match_id": str(match_id)},
        ):
            result = await deactivate_match_and_rebuild(
                match_id,
                graph_store=self._graph_store,
                schema=self._schema,
                tracer=self._tracer,
            )
            await _synchronize_resolved_entity_vectors(
                result.resolved_entities,
                result.removed_entity_ids,
                embedder=self._embedder,
                graph_store=self._graph_store,
                vector_store=self._vector_store,
                vector_collection=self._retrieval_settings.resolved_entity_collection,
                error_policy=ErrorPolicy.RAISE,
            )
            return result.resolved_entities

    async def consolidate(self, *, apply: bool = False) -> ConsolidationReport:
        """Run non-destructive resolution against every persisted raw entity.

        Dry-run by default: produces matches before any node is touched. Pass
        apply=True to write MATCHES edges and derived ResolvedEntity nodes.

        For each EntityType label in self._schema, fetches every persisted
        entity with that label, bounds the pairs actually compared with
        GraphCandidateSource's ANN-backed persisted_candidate_indices, and
        runs the same zone-routed resolution add() uses (exact, fuzzy
        fast-path, embedding similarity, capped LLM review) over those
        candidate pairs. Confirmed non-exact matches preserve both raw
        Entity nodes and their relationships.

        LLM verification calls stay bounded: at most
        ceil(L * MAX_LLM_PAIRS / 10) requests for L labels. See Graph.add.

        Args:
            apply: Write the confirmed matches and rebuild resolved entities.
                False produces a report only.

        Returns:
            A report of every confirmed non-exact match, applied or not,
            plus the count of uncertain LLM verdicts.
        """
        with self._tracer.start_as_current_span("agrag.ingestion.consolidate"):
            would_match: list[MatchDecision] = []
            ambiguous_count = 0
            entities_by_id: dict[UUID, Entity] = {}
            # For each label, fetch all entities, then pairwise compare via Resolver
            for entity_type in self._schema.entities:
                label = entity_type.label
                all_entities = await self._all_entities_by_label(label)
                if len(all_entities) < 2:
                    continue
                resolution_result = await resolve_persisted(
                    all_entities,
                    graph_store=self._graph_store,
                    embedder=self._embedder,
                    vector_store=self._vector_store,
                    vector_collection=self._retrieval_settings.entity_collection,
                    entity_labels=[entity.label for entity in self._schema.entities],
                    tracer=self._tracer,
                    max_llm_pairs=self._max_llm_pairs,
                )
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

            consolidation_failures: list[StageFailure] = []
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
                    consolidation_failures,
                ) = await self._rebuild_components(
                    components, error_policy=ErrorPolicy.SKIP
                )

            return ConsolidationReport(
                would_match=would_match,
                applied=apply and bool(rebuilt_entities),
                failures=consolidation_failures,
                ambiguous_count=ambiguous_count,
            )

    async def reevaluate(self, entity_ids: list[UUID]) -> ReevaluationReport:
        """Reevaluate matches among the given entities, adding and removing edges.

        Fetches exactly the supplied entities, compares same-label pairs
        only among this set through one zone-routed Resolver pass, writes
        confirmed matches that lack an active edge, and deactivates active
        edges among the set the resolver did not confirm. Exact-text pairs
        never gain or lose edges. Nothing outside the input set is compared
        or touched, and nothing calls this automatically.

        LLM verification calls stay bounded at ceil(L * MAX_LLM_PAIRS / 10)
        requests for L labels, as in Graph.add.

        Args:
            entity_ids: The persisted entities to reevaluate, deduped with
                input order preserved.

        Returns:
            Which entities were reevaluated, which matches were added,
            which match edges were deactivated, and how many inputs had no
            incident added or removed edge.

        Raises:
            ValueError: An id has no live persisted entity.
        """
        with self._tracer.start_as_current_span(
            "agrag.ingestion.reevaluate",
            attributes={"agrag.entity_count": len(entity_ids)},
        ):
            unique_ids = list(dict.fromkeys(entity_ids))
            if not unique_ids:
                return ReevaluationReport()
            entities_by_id = {
                entity.id: entity
                for entity in await self._load_input_entities(unique_ids)
            }
            entities = [entities_by_id[e] for e in unique_ids]
            resolution = await resolve_among(
                entities,
                embedder=self._embedder,
                tracer=self._tracer,
                max_llm_pairs=self._max_llm_pairs,
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
            edge_rows = await self._graph_store.execute_read(
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
                with self._tracer.start_as_current_span(
                    "agrag.merge.rebuild_component",
                    attributes={"agrag.member_count": len(member_ids)},
                ):
                    rebuild = await write_matches_and_rebuild(
                        component,
                        graph_store=self._graph_store,
                        schema=self._schema,
                        members=[entities_by_id[m] for m in member_ids],
                        tracer=self._tracer,
                    )
                rebuilt.append(rebuild.resolved_entity)
                replaced.extend(rebuild.removed_entity_ids)
                matches_added.extend(component)
            matches_removed: list[UUID] = []
            removed_pairs: set[frozenset[UUID]] = set()
            for pair, match_id in sorted(active.items(), key=lambda item: str(item[1])):
                if pair in confirmed or pair in exact_pairs:
                    continue
                with self._tracer.start_as_current_span(
                    "agrag.merge.deactivate_component",
                    attributes={"agrag.match_id": str(match_id)},
                ):
                    deactivation = await deactivate_match_and_rebuild(
                        match_id,
                        graph_store=self._graph_store,
                        schema=self._schema,
                        tracer=self._tracer,
                    )
                rebuilt.extend(deactivation.resolved_entities)
                replaced.extend(deactivation.removed_entity_ids)
                matches_removed.append(match_id)
                removed_pairs.add(pair)
            await _synchronize_resolved_entity_vectors(
                rebuilt,
                list(dict.fromkeys(replaced)),
                embedder=self._embedder,
                graph_store=self._graph_store,
                vector_store=self._vector_store,
                vector_collection=self._retrieval_settings.resolved_entity_collection,
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

    async def _delete_stale_community_vectors(self) -> None:
        """Remove every community vector from the VectorStore, then return.

        detect_communities is a full recompute: every prior run's Community
        nodes are deleted from the graph, so the matching vectors must go
        too, or the VectorStore keeps serving communities the graph no
        longer has. This clears every record labeled Community in the
        configured collection, matching delete_all_communities deleting
        every Community node in the database: one collection belongs to one
        graph, and a collection shared by several graphs lets this wipe
        remove another graph's community vectors. Best effort: a failure is
        logged and swallowed so it never blocks the recompute itself.

        Raises:
            Exception: Whatever the VectorStore delete raises. Callers wrap
                this; the method itself adds no suppression beyond logging.
        """
        if self._vector_store is None:
            return
        collection = self._retrieval_settings.community_collection
        # Read every id before deleting: a backend may page by position, and
        # deleting a page would shift the records the next page skips.
        community_ids: list[UUID] = []
        page_offset: str | None = None
        while True:
            records, page_offset = await self._vector_store.scroll(
                collection,
                limit=1000,
                page_offset=page_offset,
                filters={"label": COMMUNITY_LABEL},
            )
            community_ids.extend(record.id for record in records)
            if page_offset is None or not records:
                break
        for start in range(0, len(community_ids), 1000):
            await self._vector_store.delete(
                collection, community_ids[start : start + 1000]
            )

    async def detect_communities(  # noqa: PLR0912,PLR0915
        self,
        *,
        apply: bool = False,
        max_cluster_size: int = 10,
        resolution: float = 1.0,
        seed: int | None = 0xDEADBEEF,
    ) -> CommunityDetectionReport:
        """Detect entity communities via hierarchical Leiden.

        Dry-run by default: produces a report of the communities that would be
        written before any node is touched. Pass apply=True to write them.

        Fetches every live domain relation across the whole graph (not scoped
        by entity label the way consolidate() is -- community structure spans
        entity types), builds a weighted edge list, and runs hierarchical
        Leiden off the event loop. Every prior run's Community nodes and
        MEMBER_OF edges are deleted before the new ones are written when
        apply=True: this is a full recompute, not an incremental update,
        so there is no notion of merging this run's output with a
        previous one's.

        Args:
            apply: Write the computed communities. False produces a report only.
            max_cluster_size: Forwarded to compute_communities.
            resolution: Forwarded to compute_communities.
            seed: Forwarded to compute_communities.

        Returns:
            A report of every community this call found, applied or not.

        Raises:
            agrag.ingestion.community.CommunityDetectionMissingExtraError:
                graspologic-native is not installed.
        """
        with self._tracer.start_as_current_span("agrag.ingestion.detect_communities"):
            from agrag.common.data_models.community import (  # noqa: PLC0415
                COMMUNITY_LABEL,
                MEMBER_OF_RELATION,
            )
            from agrag.ingestion.community import (  # noqa: PLC0415
                compute_communities,
                delete_all_communities,
                embed_communities,
                fetch_relation_edges,
                generate_community_reports,
                required_member_ids,
            )

            edges = await fetch_relation_edges(self._graph_store)
            if not edges:
                if apply:
                    async with self._graph_store.transaction() as tx:
                        await delete_all_communities(tx)
                    if self._vector_store is not None:
                        try:
                            await self._delete_stale_community_vectors()
                        except Exception as exc:  # noqa: BLE001
                            trace_id, span_id = record_stage_failure(exc)
                            return CommunityDetectionReport(
                                communities=[],
                                applied=True,
                                failures=[
                                    StageFailure(
                                        item_id="community_vector_store",
                                        error_type=type(exc).__name__,
                                        error_message=str(exc),
                                        trace_id=trace_id,
                                        span_id=span_id,
                                    )
                                ],
                            )
                    return CommunityDetectionReport(
                        communities=[], applied=True, failures=[]
                    )
                return CommunityDetectionReport(
                    communities=[], applied=False, failures=[]
                )

            communities = await asyncio.to_thread(
                compute_communities,
                edges,
                max_cluster_size=max_cluster_size,
                resolution=resolution,
                seed=seed,
            )

            report_failures: list[StageFailure] = []
            if apply:
                if not communities:
                    async with self._graph_store.transaction() as tx:
                        await delete_all_communities(tx)
                    if self._vector_store is not None:
                        try:
                            await self._delete_stale_community_vectors()
                        except Exception as exc:  # noqa: BLE001
                            trace_id, span_id = record_stage_failure(exc)
                            report_failures.append(
                                StageFailure(
                                    item_id="community_vector_store",
                                    error_type=type(exc).__name__,
                                    error_message=str(exc),
                                    trace_id=trace_id,
                                    span_id=span_id,
                                )
                            )
                    return CommunityDetectionReport(
                        communities=[], applied=True, failures=report_failures
                    )
                needed_ids = required_member_ids(communities)
                entities_by_id = await load_entities(
                    self._graph_store, list(needed_ids), tracer=self._tracer
                )
                report_failures = await generate_community_reports(
                    communities,
                    entities_by_id,
                    edges=edges,
                    error_policy=ErrorPolicy.SKIP,
                    tracer=self._tracer,
                )
                report_failures += await embed_communities(
                    communities, embedder=self._embedder, tracer=self._tracer
                )

                async with self._graph_store.transaction() as tx:
                    await delete_all_communities(tx)
                    for i in range(0, len(communities), 5000):
                        batch = communities[i : i + 5000]
                        await tx.upsert_nodes(
                            COMMUNITY_LABEL,
                            [c.to_node_record() for c in batch],
                        )
                    buf: list[Any] = []
                    for community in communities:
                        for member_id in community.member_ids:
                            buf.append(
                                Relation(
                                    id=uuid4(),
                                    type=MEMBER_OF_RELATION,
                                    source_id=member_id,
                                    target_id=community.id,
                                ).to_relation_record()
                            )
                            if len(buf) >= 5000:
                                await tx.upsert_relations(buf)
                                buf = []
                    if buf:
                        await tx.upsert_relations(buf)

                if self._vector_store is not None:
                    try:
                        await self._delete_stale_community_vectors()
                    except Exception as exc:  # noqa: BLE001
                        trace_id, span_id = record_stage_failure(exc)
                        report_failures.append(
                            StageFailure(
                                item_id="community_vector_store",
                                error_type=type(exc).__name__,
                                error_message=str(exc),
                                trace_id=trace_id,
                                span_id=span_id,
                            )
                        )
                    try:
                        await _upsert_vectors(
                            self._vector_store,
                            self._retrieval_settings.community_collection,
                            [
                                _vector_record(
                                    c.id,
                                    c.embedding or [],
                                    label=COMMUNITY_LABEL,
                                    text=c.embedding_text,
                                    properties=c.metadata,
                                )
                                for c in communities
                                if c.embedding is not None
                            ],
                        )
                    except Exception as exc:  # noqa: BLE001
                        trace_id, span_id = record_stage_failure(exc)
                        report_failures.append(
                            StageFailure(
                                item_id="community_vector_store",
                                error_type=type(exc).__name__,
                                error_message=str(exc),
                                trace_id=trace_id,
                                span_id=span_id,
                            )
                        )

            return CommunityDetectionReport(
                communities=communities,
                applied=apply and bool(communities),
                failures=report_failures,
            )
