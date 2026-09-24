"""The public Graph API for ingestion."""

import asyncio
import contextlib
import glob
import hashlib
import unicodedata
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Union
from uuid import UUID, uuid4

from opentelemetry.trace import Tracer

import agrag.loaders.docling  # noqa: F401  (registers the docling loaders)
from agrag.chunking import default_chunker
from agrag.chunking.text import chunk_document
from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.community import COMMUNITY_LABEL, MEMBER_OF_RELATION
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
from agrag.common.text import normalize_text
from agrag.cypher.entities import (
    fetch_all_by_label_query,
    hydrate_entities_by_id_query,
)
from agrag.cypher.relations import entities_in_documents_query
from agrag.cypher.resolution_read import fetch_active_matches_among_ids_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion._cutover import run_cutover_job
from agrag.ingestion._document_lifecycle import find_document
from agrag.ingestion._ingest_pipeline import (
    _delete_vectors,
    _parse_entity_node,
    _synthetic_entity_mention,
    _upsert_vectors,
    _vector_record,
    extract_chunks,
    ingest_chunks,
)
from agrag.ingestion._resume import resume_incomplete_jobs
from agrag.ingestion.extract import Extractor
from agrag.ingestion.materialize import (
    MatchComponent,
    MatchDecision,
    deactivate_match_and_rematerialize,
    match_decision_components,
    matches_id,
    prune_orphaned_entities,
    write_matches_and_materialize,
)
from agrag.ingestion.reports import (
    AddResult,
    CommunityDetectionReport,
    ConsolidationReport,
    ReevaluationReport,
    UpdateResult,
)
from agrag.ingestion.resolve import (
    ExactMatch,
    FuzzyMatch,
    GraphCandidateSource,
    LLMVerify,
    PersistedCandidateSource,
    Resolver,
    fetch_persisted_neighbors,
    persisted_candidate_indices,
)
from agrag.ingestion.resolved_embeddings import _synchronize_resolved_entity_vectors
from agrag.ingestion.settings import CutoverJobSettings
from agrag.ingestion.stats import (
    ExtractionStats,
    IngestStats,
    MergeStats,
    ResolutionStats,
    StageFailure,
    StorageStats,
    cap_failures,
)
from agrag.loaders.corpus import registry as _corpus_registry
from agrag.loaders.corpus._walk import _CorpusWalk, _InMemoryWalk
from agrag.loaders.corpus.base import Loader
from agrag.loaders.corpus.types import ErrorPolicy, LoadStats, ReadOptions
from agrag.loaders.docling.chunking import chunk_docling_document
from agrag.observability import get_tracer, traced
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


SourceType = Union[str, Path]
SourcesType = Union[SourceType, Sequence[SourceType]]

# Relationship types Graph.open() always registers
SYSTEM_RELATION_TYPES = [
    "MENTIONED_IN",
    MEMBER_OF_RELATION,
    "PART_OF",
    "NEXT_CHUNK",
    "MATCHES",
    "RESOLVED_AS",
]


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


def _synthesize_consolidation_mentions(
    entities: list[Entity],
) -> tuple[list[ExtractedEntity], dict[UUID, Chunk]]:
    """Build resolver mentions and per-entity dummy chunks for consolidate().

    consolidate() has no real chunk text to compare persisted entities
    against, so each gets a synthetic mention and a dummy chunk carrying its
    own name as LLMVerify context. Each entity's dummy chunk id is its own,
    independent of its real source_chunk_ids: two entities commonly share a
    first source chunk (they were extracted from the same passage), and
    keying the dummy chunk by that shared id would let the first entity
    processed silently stand in as every later entity's own context.

    Args:
        entities: The persisted entities to synthesize mentions for.

    Returns:
        One ExtractedEntity mention per entity and the dummy Chunk each
        mention's chunk_id resolves to, both index-aligned with entities.
    """
    synthetic_mentions: list[ExtractedEntity] = []
    dummy_chunks_by_id: dict[UUID, Chunk] = {}
    for ent in entities:
        mention, chunk = _synthetic_entity_mention(ent)
        synthetic_mentions.append(mention)
        dummy_chunks_by_id[mention.chunk_id] = chunk
    return synthetic_mentions, dummy_chunks_by_id


async def _no_pending_write(job_id: UUID) -> None:
    """Pending-write step for delete_document, which writes nothing new."""


def _with_cleanup_failures(
    result: AddResult, failures: list[StageFailure]
) -> AddResult:
    """Record post-commit materialization failures in the storage stats.

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
    results: list[AddResult], *, ingestion: IngestStats
) -> AddResult:
    """Combine per-document job results into one call-level summary.

    Each document in an add() call commits as its own Cutover Job; the
    caller still gets a single AddResult shaped exactly like a one-job
    call's. Counters sum, failure lists concatenate re-capped against the
    per-stage cap with true totals preserved, and chunks concatenate in
    job order. The call-level ingestion summary passed in replaces the
    per-slice placeholders.

    Args:
        results: One AddResult per document job, in job order.
        ingestion: The call-level ingestion summary from the walk.

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
            extraction=ExtractionStats(),
            resolution=ResolutionStats(),
            merge=MergeStats(),
            storage=StorageStats(),
            chunks=[],
        )
    if len(results) == 1:
        return results[0].model_copy(update={"ingestion": ingestion})
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
            nodes_merged=sum(result.merge.nodes_merged for result in results),
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
                tombstoned entities deleted after merges and old community
                vectors removed on each detect_communities(apply=True)
                cycle.
            retrieval_settings: Collection names for the VectorStore writes.
                None uses RetrievalSettings defaults. Ignored when
                vector_store is None.
            cutover_settings: Lease configuration for the Cutover Jobs
                add/update/delete_document run through. None uses
                CutoverJobSettings defaults.
        """
        self._schema = schema
        self._graph_store = graph_store
        self._embedder = embedder
        self._extractor = extractor
        self._tracer = get_tracer(tracer)
        self._registry = _corpus_registry
        self._chunker = default_chunker()
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

        Returns:
            A graph connected to graph_store and ready to accept add() calls.

        Raises:
            Exception: Whatever connect(), registration, constraint/index
                setup, or vector-index provisioning raises. graph_store is
                closed first, so a failed open() never leaks a connection.
        """
        try:
            await graph_store.connect()
            entity_labels = [entity_type.label for entity_type in schema.entities]
            relation_types = [relation_type.label for relation_type in schema.relations]
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
            )
            # Crash recovery, last: every index and collection the
            # recovery paths rely on now exists. A pending job (its worker
            # died pre-commit) rolls back; a committed or cleaning job
            # rolls forward, rerunning the cleanup phase this graph's own
            # pruning implements. A recovery failure is swallowed: opening
            # the graph must not break because a leftover job could not be
            # finished, and the pending filters keep any tagged writes
            # invisible to retrieval until a later open succeeds.
            with contextlib.suppress(Exception):
                await resume_incomplete_jobs(
                    graph_store,
                    vector_store=vector_store,
                    vector_collections=recovery_collections,
                    roll_forward=graph._prune_document_entities,
                    lease_ttl_seconds=graph._cutover_settings.lease_ttl_seconds,
                )
        except Exception:
            await graph_store.close()
            if vector_store is not None:
                with contextlib.suppress(Exception):
                    await vector_store.close()
            raise
        return graph

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
        given = sum(x is not None for x in (source, text, documents))
        if given != 1:
            raise ValueError(
                f"Provide exactly one of 'source', 'text', or 'documents'; got {given}."
            )
        if loader is not None and source is None:
            raise ValueError(
                "A loader override requires 'source'; it has no effect on 'text' or "
                "'documents'."
            )

        chunks: list[Chunk] = []
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
                quarantined_items=[
                    StageFailure(
                        item_id=str(uri),
                        error_type="Quarantined",
                        error_message=reason,
                    )
                    for uri, reason in final_stats.quarantined_items
                ],
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
            chunk_batch = await asyncio.to_thread(self._chunk_documents, docs_list)
            chunks.extend(chunk_batch)
            documents_seen.extend(docs_list)
            batch_entities, batch_relations, batch_failures = await extract_chunks(
                chunk_batch,
                start_index=len(entities),
                extractor=self._extractor,
                schema=self._schema,
                error_policy=error_policy,
            )
            entities.extend(batch_entities)
            relations.extend(batch_relations)
            extraction_failures.extend(batch_failures)
            # Fire on_progress once for the synthetic batch (partial)
            if on_progress is not None:
                with contextlib.suppress(Exception):
                    on_progress(_build_partial_add_result())
        elif text is not None:
            walk = _InMemoryWalk(text, opts=ReadOptions())
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
                chunk_batch = await asyncio.to_thread(self._chunk_documents, batch)
                chunks.extend(chunk_batch)
                documents_seen.extend(batch)
                batch_entities, batch_relations, batch_failures = await extract_chunks(
                    chunk_batch,
                    start_index=len(entities),
                    extractor=self._extractor,
                    schema=self._schema,
                    error_policy=error_policy,
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
                    "A loader override requires a single-file source, not a directory, "
                    "glob, or list of sources."
                )
            walk = _CorpusWalk(
                paths,
                registry=self._registry,
                opts=ReadOptions(),
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
                chunk_batch = await asyncio.to_thread(self._chunk_documents, batch)
                chunks.extend(chunk_batch)
                documents_seen.extend(batch)
                batch_entities, batch_relations, batch_failures = await extract_chunks(
                    chunk_batch,
                    start_index=len(entities),
                    extractor=self._extractor,
                    schema=self._schema,
                    error_policy=error_policy,
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
            quarantined_items=[
                StageFailure(
                    item_id=str(uri),
                    error_type="Quarantined",
                    error_message=reason,
                )
                for uri, reason in final_stats.quarantined_items
            ],
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
                    materialized_components=_components,
                )

            async def _cleanup(
                _components: list[MatchComponent] = components,
            ) -> list[StageFailure]:
                _, cleanup_failures = await self._materialize_components(
                    _components, error_policy=error_policy
                )
                return cleanup_failures

            partial, cleanup_failures, _ = await run_cutover_job(
                verb="add",
                document_key=document_key,
                affected_entity_ids=[],
                graph_store=self._graph_store,
                vector_store=self._vector_store,
                vector_collections=vector_collections,
                settings=self._cutover_settings,
                pending_write=_pending,
                cleanup=_cleanup,
            )
            partials.append(_with_cleanup_failures(partial, cleanup_failures))
        result = _merge_add_results(partials, ingestion=ingestion)

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
    ) -> UpdateResult:
        """Replace one document version, closing its former PART_OF edges.

        Looks up the persisted ``Document`` node by ``document_key``. An
        unchanged content hash is a no-op returning before any chunking,
        extraction, or writes. Otherwise the fresh content ingests under a
        Cutover Job holding this document's lease, and the commit flips
        the job, closes the document's open ``PART_OF`` edges, and clears
        every pending tag in one transaction — so a crash either leaves
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
        if (text is None) == (source is None):
            raise ValueError("Provide exactly one of 'text' or 'source'.")

        if text is not None:
            normalized = unicodedata.normalize("NFKC", text)
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
            )
        else:
            assert source is not None
            paths, single_file = _resolve_paths(source)
            if loader is not None and not single_file:
                raise ValueError(
                    "A loader override requires a single-file source, not a directory, "
                    "glob, or list of sources."
                )
            walk = _CorpusWalk(
                paths,
                registry=self._registry,
                opts=ReadOptions(),
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
        if found is not None and found.current_content_hash == document.content_hash:
            return UpdateResult(
                document_key=document_key,
                no_op=True,
                previous_content_hash=found.current_content_hash,
                new_content_hash=document.content_hash,
            )

        candidates: list[UUID] = []
        if found is not None:
            candidates = await self._document_entity_candidates(found.document_node_id)
        chunks = await asyncio.to_thread(self._chunk_documents, [document])
        entities, relations, extraction_failures = await extract_chunks(
            chunks,
            start_index=0,
            extractor=self._extractor,
            schema=self._schema,
            error_policy=error_policy,
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
                materialized_components=components,
            )

        async def _cleanup() -> list[StageFailure]:
            _, cleanup_failures = await self._materialize_components(
                components, error_policy=error_policy
            )
            await self._prune_document_entities(candidates)
            return cleanup_failures

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
            cleanup=_cleanup,
            close_document_node_id=(
                found.document_node_id if found is not None else None
            ),
        )
        return UpdateResult(
            document_key=document_key,
            no_op=False,
            previous_content_hash=(found.current_content_hash if found else None),
            new_content_hash=document.content_hash,
            chunks_closed=chunks_closed,
            add_result=_with_cleanup_failures(add_result, cleanup_failures),
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
        found = await find_document(self._graph_store, document_key=document_key)
        if found is None:
            return UpdateResult(document_key=document_key, no_op=True)
        candidates = await self._document_entity_candidates(found.document_node_id)

        async def _cleanup() -> None:
            await self._prune_document_entities(candidates)

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
            cleanup=_cleanup,
            close_document_node_id=found.document_node_id,
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

    async def _materialize_components(
        self, components: list[MatchComponent], *, error_policy: ErrorPolicy
    ) -> tuple[list[ResolvedEntity], list[StageFailure]]:
        """Materialize committed match components and sync their vectors.

        Runs outside any Cutover Job, so each write replaces the previous
        materialization of the components it grows or merges, including its
        ``RESOLVED_AS`` edges. The replaced vectors are then deleted and the
        new ones written to the graph and the external vector store.

        Args:
            components: The match decisions and raw members of each
                component to materialize.
            error_policy: RAISE propagates the first failure; any other
                policy records it and continues.

        Returns:
            The materialized resolved entities and the recorded failures.
        """
        failures: list[StageFailure] = []
        materialized: list[ResolvedEntity] = []
        replaced_ids: list[UUID] = []
        for decisions, members in components:
            try:
                materialization = await write_matches_and_materialize(
                    decisions,
                    graph_store=self._graph_store,
                    schema=self._schema,
                    members=members,
                )
            except Exception as exc:  # noqa: BLE001
                if error_policy is ErrorPolicy.RAISE:
                    raise
                failures.append(
                    StageFailure(
                        item_id=",".join(str(member.id) for member in members),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
                continue
            materialized.append(materialization.resolved_entity)
            replaced_ids.extend(materialization.removed_entity_ids)
        failures.extend(
            await _synchronize_resolved_entity_vectors(
                materialized,
                replaced_ids,
                embedder=self._embedder,
                graph_store=self._graph_store,
                vector_store=self._vector_store,
                vector_collection=self._retrieval_settings.resolved_entity_collection,
                error_policy=error_policy,
            )
        )
        return materialized, failures

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
            candidates, graph_store=self._graph_store, schema=self._schema
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

    def _chunk_documents(self, documents: list[Document]) -> list[Chunk]:
        """Chunk a batch of documents with the right chunker each.

        Args:
            documents: The documents to chunk.

        Returns:
            The chunks, in document then chunk order.
        """
        chunks: list[Chunk] = []
        for document in documents:
            if document.loader_name == "docling":
                docling_doc = document.metadata.get("_docling_document")
                if docling_doc is not None:
                    chunks.extend(
                        traced(self._tracer)(chunk_docling_document)(
                            docling_doc,
                            Document.node_id_for(
                                document_key=document.resolved_document_key
                            ),
                            version_id=Document.id_for(
                                content_hash=document.content_hash
                            ),
                        )
                    )
                    continue
            chunks.extend(traced(self._tracer)(chunk_document)(document, self._chunker))
        return chunks

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
                node = row.get("n") if isinstance(row, dict) and "n" in row else row
                ent = _parse_entity_node(node)
                if ent is not None:
                    # Skip tombstoned nodes with merged_into.
                    # Check node for merged_into property.
                    try:
                        raw_props = (
                            dict(node)  # ty: ignore[no-matching-overload]
                            if not isinstance(node, dict)
                            else node.get("properties", node)
                        )  # type: ignore[union-attr]
                        if isinstance(raw_props, dict) and raw_props.get("merged_into"):
                            continue
                        # Also check node dict directly
                        if isinstance(node, dict) and node.get("merged_into"):
                            continue
                        # Check row for merged_into
                        if isinstance(row, dict) and row.get("merged_into"):
                            continue
                    except Exception:
                        pass
                    entities.append(ent)
                else:
                    # Try parsing row directly if node was wrapped differently
                    ent2 = _parse_entity_node(row)
                    if ent2 is not None:
                        entities.append(ent2)
            if len(rows) < limit:
                break
            skip += limit
        return entities

    async def _hydrate_input_entities(self, unique_ids: list[UUID]) -> list[Entity]:
        """Fetch live entities for the given ids, preserving input order.

        Args:
            unique_ids: Deduped entity ids to fetch.

        Returns:
            The live entities in input order.

        Raises:
            ValueError: An id has no live persisted entity.
        """
        rows = await self._graph_store.execute_read(
            hydrate_entities_by_id_query(),
            {"ids": [str(e) for e in unique_ids], "job_id": None},
        )
        entities_by_id: dict[UUID, Entity] = {}
        for row in rows:
            node = row.get("n", row) if isinstance(row, dict) else row
            entity = _parse_entity_node(node)
            if entity is not None:
                entities_by_id[entity.id] = entity
        missing = [e for e in unique_ids if e not in entities_by_id]
        if missing:
            raise ValueError(
                "Unknown entity ids: " + ", ".join(str(m) for m in missing)
            )
        return [entities_by_id[e] for e in unique_ids]

    async def deactivate_match(self, match_id: UUID) -> list[ResolvedEntity]:
        """Deactivate a semantic match and synchronize replacement retrieval vectors."""
        result = await deactivate_match_and_rematerialize(
            match_id, graph_store=self._graph_store, schema=self._schema
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
            apply: Materialize the confirmed matches. False produces a report only.

        Returns:
            A report of every confirmed non-exact match, applied or not,
            plus the count of uncertain LLM verdicts.
        """
        would_match: list[MatchDecision] = []
        ambiguous_count = 0
        entities_by_id: dict[UUID, Entity] = {}
        # For each label, fetch all entities, then pairwise compare via Resolver
        for entity_type in self._schema.entities:
            label = entity_type.label
            all_entities = await self._all_entities_by_label(label)
            if len(all_entities) < 2:
                continue
            synthetic_mentions, dummy_chunks_by_id = _synthesize_consolidation_mentions(
                all_entities
            )

            candidate_source = GraphCandidateSource(
                graph_store=self._graph_store,
                embedder=self._embedder,
                vector_store=self._vector_store,
                vector_collection=self._retrieval_settings.entity_collection,
                entity_labels=[entity.label for entity in self._schema.entities],
            )
            persisted_neighbors = await fetch_persisted_neighbors(
                [entity.id for entity in all_entities],
                graph_store=self._graph_store,
                exclude_relation_types=SYSTEM_RELATION_TYPES,
            )
            neighbors_by_index = {
                index: persisted_neighbors.get(entity.id, [])
                for index, entity in enumerate(all_entities)
            }
            candidate_indices, similarity_by_pair = await persisted_candidate_indices(
                synthetic_mentions,
                all_entities,
                source=candidate_source,
            )
            resolver = Resolver(
                comparators=[
                    ExactMatch(),
                    FuzzyMatch(),
                    LLMVerify(chunks_by_id=dummy_chunks_by_id),
                ],
                candidate_source=PersistedCandidateSource(candidate_indices),
                embedder=self._embedder,
            )
            resolution_result = await resolver.resolve(
                synthetic_mentions,
                neighbors_by_index=neighbors_by_index,
                similarity_by_pair=similarity_by_pair,
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
        materialized_entities: list[ResolvedEntity] = []
        if apply:
            components: list[MatchComponent] = []
            for decisions in match_decision_components(would_match):
                member_ids = {decision.entity_a_id for decision in decisions} | {
                    decision.entity_b_id for decision in decisions
                }
                components.append(
                    (decisions, [entities_by_id[member_id] for member_id in member_ids])
                )
            (
                materialized_entities,
                consolidation_failures,
            ) = await self._materialize_components(
                components, error_policy=ErrorPolicy.SKIP
            )

        return ConsolidationReport(
            would_match=would_match,
            applied=apply and bool(materialized_entities),
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
        unique_ids = list(dict.fromkeys(entity_ids))
        if not unique_ids:
            return ReevaluationReport()
        entities_by_id = {
            entity.id: entity
            for entity in await self._hydrate_input_entities(unique_ids)
        }
        entities = [entities_by_id[e] for e in unique_ids]
        mentions, dummy_chunks = _synthesize_consolidation_mentions(entities)
        candidates_by_index = {
            index: [
                other
                for other, peer in enumerate(mentions)
                if other != index and peer.label == mention.label
            ]
            for index, mention in enumerate(mentions)
        }
        resolver = Resolver(
            comparators=[
                ExactMatch(),
                FuzzyMatch(),
                LLMVerify(chunks_by_id=dummy_chunks),
            ],
            candidate_source=PersistedCandidateSource(
                {index: peers for index, peers in candidates_by_index.items() if peers}
            ),
            embedder=self._embedder,
        )
        resolution = await resolver.resolve(mentions)
        confirmed = {
            frozenset((unique_ids[m.left_index], unique_ids[m.right_index])): m
            for m in resolution.matches
        }
        exact_pairs = {
            frozenset((unique_ids[left], unique_ids[right]))
            for left in range(len(mentions))
            for right in range(left + 1, len(mentions))
            if normalize_text(mentions[left].text)
            == normalize_text(mentions[right].text)
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
        materialized: list[ResolvedEntity] = []
        replaced: list[UUID] = []
        matches_added: list[MatchDecision] = []
        for component in match_decision_components(decisions):
            member_ids = {d.entity_a_id for d in component} | {
                d.entity_b_id for d in component
            }
            materialization = await write_matches_and_materialize(
                component,
                graph_store=self._graph_store,
                schema=self._schema,
                members=[entities_by_id[m] for m in member_ids],
            )
            materialized.append(materialization.resolved_entity)
            replaced.extend(materialization.removed_entity_ids)
            matches_added.extend(component)
        matches_removed: list[UUID] = []
        removed_pairs: set[frozenset[UUID]] = set()
        for pair, match_id in sorted(active.items(), key=lambda item: str(item[1])):
            if pair in confirmed or pair in exact_pairs:
                continue
            deactivation = await deactivate_match_and_rematerialize(
                match_id, graph_store=self._graph_store, schema=self._schema
            )
            materialized.extend(deactivation.resolved_entities)
            replaced.extend(deactivation.removed_entity_ids)
            matches_removed.append(match_id)
            removed_pairs.add(pair)
        await _synchronize_resolved_entity_vectors(
            materialized,
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
        page_offset: str | None = None
        while True:
            records, page_offset = await self._vector_store.scroll(
                collection,
                limit=1000,
                page_offset=page_offset,
                filters={"label": COMMUNITY_LABEL},
            )
            if records:
                await self._vector_store.delete(
                    collection, [record.id for record in records]
                )
            if page_offset is None:
                break

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
        from agrag.common.data_models.community import (  # noqa: PLC0415
            COMMUNITY_LABEL,
            MEMBER_OF_RELATION,
        )
        from agrag.cypher.entities import hydrate_entities_by_id_query  # noqa: PLC0415
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
                        return CommunityDetectionReport(
                            communities=[],
                            applied=True,
                            failures=[
                                StageFailure(
                                    item_id="community_vector_store",
                                    error_type=type(exc).__name__,
                                    error_message=str(exc),
                                )
                            ],
                        )
                return CommunityDetectionReport(
                    communities=[], applied=True, failures=[]
                )
            return CommunityDetectionReport(communities=[], applied=False, failures=[])

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
                        report_failures.append(
                            StageFailure(
                                item_id="community_vector_store",
                                error_type=type(exc).__name__,
                                error_message=str(exc),
                            )
                        )
                return CommunityDetectionReport(
                    communities=[], applied=True, failures=report_failures
                )
            needed_ids = required_member_ids(communities)
            entities_by_id: dict[UUID, Entity] = {}
            ids = list(needed_ids)
            HYDRATE_BATCH = 1000  # noqa: N806
            for i in range(0, len(ids), HYDRATE_BATCH):
                chunk_ids = ids[i : i + HYDRATE_BATCH]
                rows = await self._graph_store.execute_read(
                    hydrate_entities_by_id_query(),
                    {"ids": [str(x) for x in chunk_ids], "job_id": None},
                )
                entities_by_id.update(
                    {
                        ent.id: ent
                        for row in rows
                        if (
                            ent := _parse_entity_node(row.get("n", row))  # type: ignore[arg-type]
                        )
                        is not None
                    }
                )
            report_failures = await generate_community_reports(
                communities,
                entities_by_id,
                edges=edges,
                error_policy=ErrorPolicy.SKIP,
            )
            report_failures += await embed_communities(
                communities, embedder=self._embedder
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
                    report_failures.append(
                        StageFailure(
                            item_id="community_vector_store",
                            error_type=type(exc).__name__,
                            error_message=str(exc),
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
                    report_failures.append(
                        StageFailure(
                            item_id="community_vector_store",
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    )

        return CommunityDetectionReport(
            communities=communities,
            applied=apply and bool(communities),
            failures=report_failures,
        )
