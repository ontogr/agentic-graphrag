"""The public Graph API for ingestion."""

import asyncio
import contextlib
import glob
import hashlib
import unicodedata
from collections import defaultdict
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
from agrag.cypher.entities import (
    fetch_all_by_label_query,
)
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion._document_lifecycle import (
    close_open_part_of_edges,
    find_document,
)
from agrag.ingestion._ingest_pipeline import (
    _parse_entity_node,
    _synthetic_entity_mention,
    _upsert_vectors,
    _vector_record,
    extract_chunks,
    ingest_chunks,
)
from agrag.ingestion.extract import Extractor
from agrag.ingestion.materialize import (
    MatchDecision,
    deactivate_match_and_rematerialize,
    match_decision_components,
    write_matches_and_materialize,
)
from agrag.ingestion.reports import (
    AddResult,
    CommunityDetectionReport,
    ConsolidationReport,
    UpdateResult,
)
from agrag.ingestion.resolve import (
    ExactMatch,
    FuzzyMatch,
    GraphCandidateSource,
    LLMVerify,
    PersistedCandidateSource,
    ResolutionGroup,
    Resolver,
    persisted_candidate_indices,
)
from agrag.ingestion.resolved_embeddings import _synchronize_resolved_entity_vectors
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


def _union_groups_by_existing_entity(
    groups: list[ResolutionGroup], exact_matches: dict[int, Entity]
) -> list[ResolutionGroup]:
    """Union resolver groups that exact-match the same persisted entity.

    Two mentions can land in separate resolver groups -- in-batch fuzzy/LLM
    resolution never compared them directly -- while each independently
    exact-matches the same persisted entity through a different accepted
    alias (see upsert_merge_alias_query). Computing and applying one merge
    plan per resolver group in that case would have the second group's
    apply_merge overwrite the first's contribution: each computes against
    the same snapshot with no knowledge of the other's changes. Unioning
    first means one plan is computed per canonical persisted entity,
    folding in every mention that resolves to it.

    Args:
        groups: The resolver's own groups.
        exact_matches: Mention index to persisted Entity, from
            _global_exact_match.

    Returns:
        Groups covering the same entity_indices, but any two resolver
        groups that shared an exact-matched entity id merged into one.
    """
    parent = list(range(len(groups)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    entity_to_group: dict[UUID, int] = {}
    for group_index, group in enumerate(groups):
        for idx in group.entity_indices:
            entity = exact_matches.get(idx)
            if entity is None:
                continue
            if entity.id in entity_to_group:
                union(group_index, entity_to_group[entity.id])
            else:
                entity_to_group[entity.id] = group_index

    merged: dict[int, list[int]] = defaultdict(list)
    for group_index, group in enumerate(groups):
        merged[find(group_index)].extend(group.entity_indices)

    return [
        ResolutionGroup(entity_indices=sorted(indices)) for indices in merged.values()
    ]


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
    ) -> "Graph":
        """Open a graph, connecting and fully provisioning graph_store.

        Provisioning order: connect, then register every label/relation type
        this graph will ever write (schema's own labels/types plus the fixed
        system names CHUNK_LABEL/SYSTEM_RELATION_TYPES), then
        setup_constraints(), then setup_indexes(), then vector indexes for
        every schema entity label — so a brand-new database is fully ready,
        including the merge_key index the global exact-match tier needs and
        the embedding vector indexes native search needs, before this call
        returns. When vector_store is set, the entity, chunk, and community
        collections are provisioned there too (created when missing) so the
        dual writes never hit an absent collection.

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
            if vector_store is not None:
                settings = retrieval_settings or RetrievalSettings()
                await vector_store.initialize()
                for collection in (
                    settings.entity_collection,
                    settings.resolved_entity_collection,
                    settings.chunk_collection,
                    settings.community_collection,
                ):
                    await vector_store.ensure_collection(
                        collection,
                        dimensions=dimensions,
                        distance=distance,
                        hybrid=True,
                    )
        except Exception:
            await graph_store.close()
            if vector_store is not None:
                with contextlib.suppress(Exception):
                    await vector_store.close()
            raise
        return cls(
            schema=schema,
            graph_store=graph_store,
            embedder=embedder,
            extractor=extractor,
            tracer=tracer,
            vector_store=vector_store,
            retrieval_settings=retrieval_settings,
        )

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
            A summary of what was added per pipeline stage.

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
        # the shared pipeline core over everything the walk collected.
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
        result = await ingest_chunks(
            chunks,
            documents_seen,
            entities,
            relations,
            extraction_failures,
            graph_store=self._graph_store,
            embedder=self._embedder,
            vector_store=self._vector_store,
            graph_schema=self._schema,
            retrieval_settings=self._retrieval_settings,
            error_policy=error_policy,
            ingestion=ingestion,
            return_chunks=return_chunks,
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
    ) -> UpdateResult:
        """Replace one document version, closing its former PART_OF edges.

        Looks up the persisted ``Document`` node by ``document_key``. An
        unchanged content hash is a no-op returning before any chunking,
        extraction, or writes. Otherwise closes the document's open
        ``PART_OF`` edges and ingests the fresh content under the same
        ``Document`` node through the shared pipeline core. A source must
        resolve to exactly one document.

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

        chunks_closed = 0
        if found is not None:
            chunks_closed = await close_open_part_of_edges(
                self._graph_store, document_node_id=found.document_node_id
            )
        chunks = await asyncio.to_thread(self._chunk_documents, [document])
        entities, relations, extraction_failures = await extract_chunks(
            chunks,
            start_index=0,
            extractor=self._extractor,
            schema=self._schema,
            error_policy=error_policy,
        )
        add_result = await ingest_chunks(
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
        )
        return UpdateResult(
            document_key=document_key,
            no_op=False,
            previous_content_hash=(found.current_content_hash if found else None),
            new_content_hash=document.content_hash,
            chunks_closed=chunks_closed,
            add_result=add_result,
        )

    async def delete_document(self, document_key: str) -> UpdateResult:
        """Soft-delete a document by closing its current PART_OF edges.

        Currency is read transitively through ``PART_OF``: closing the
        open edges removes the document from retrieval while its chunks,
        the ``Document`` node, and contributed entities stay in the graph
        for provenance. An unknown ``document_key`` is a no-op.

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
        chunks_closed = await close_open_part_of_edges(
            self._graph_store, document_node_id=found.document_node_id
        )
        return UpdateResult(
            document_key=document_key,
            no_op=False,
            previous_content_hash=found.current_content_hash,
            chunks_closed=chunks_closed,
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
        runs the same comparator sequence add() uses in-batch (ExactMatch,
        FuzzyMatch, LLMVerify) over those candidate pairs. Confirmed non-exact
        matches preserve both raw Entity nodes and their relationships.

        Args:
            apply: Materialize the confirmed matches. False produces a report only.

        Returns:
            A report of every confirmed non-exact match, applied or not.
        """
        would_match: list[MatchDecision] = []
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
            candidate_indices = await persisted_candidate_indices(
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
            )
            resolution_result = await resolver.resolve(synthetic_mentions)
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
        replaced_resolved_entity_ids: list[UUID] = []
        if apply:
            for decisions in match_decision_components(would_match):
                member_ids = {decision.entity_a_id for decision in decisions} | {
                    decision.entity_b_id for decision in decisions
                }
                try:
                    materialization = await write_matches_and_materialize(
                        decisions,
                        graph_store=self._graph_store,
                        schema=self._schema,
                        members=[entities_by_id[member_id] for member_id in member_ids],
                    )
                    materialized_entities.append(materialization.resolved_entity)
                    replaced_resolved_entity_ids.extend(
                        materialization.removed_entity_ids
                    )
                except Exception as exc:  # noqa: BLE001
                    consolidation_failures.append(
                        StageFailure(
                            item_id=",".join(
                                str(member_id) for member_id in member_ids
                            ),
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    )

            consolidation_failures.extend(
                await _synchronize_resolved_entity_vectors(
                    materialized_entities,
                    replaced_resolved_entity_ids,
                    embedder=self._embedder,
                    graph_store=self._graph_store,
                    vector_store=self._vector_store,
                    vector_collection=self._retrieval_settings.resolved_entity_collection,
                    error_policy=ErrorPolicy.SKIP,
                )
            )

        return ConsolidationReport(
            would_match=would_match,
            applied=apply and bool(materialized_entities),
            failures=consolidation_failures,
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
                    {"ids": [str(x) for x in chunk_ids]},
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
