"""The public Graph API for ingestion."""

import asyncio
import contextlib
import functools
from collections.abc import Callable, Sequence
from uuid import UUID

from opentelemetry.trace import Tracer

import agrag.loaders.docling  # noqa: F401  (registers the docling loaders)
from agrag.chunking import DEFAULT_CHUNKING, Chunking
from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.community import COMMUNITY_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL, Document
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.resolved_entity import (
    RESOLVED_ENTITY_LABEL,
    ResolvedEntity,
)
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion._ingest import (
    CleanupStep,
    add_documents,
    delete_document,
    update_document,
)
from agrag.ingestion._job_cleanup import finish_job
from agrag.ingestion._resolution_maintenance import (
    consolidate,
    deactivate_match,
    reevaluate,
)
from agrag.ingestion._resume import resume_incomplete_jobs
from agrag.ingestion._walk import SourcesType
from agrag.ingestion.community import detect_communities
from agrag.ingestion.extract import Extractor
from agrag.ingestion.reports import (
    AddResult,
    CommunityDetectionReport,
    ConsolidationReport,
    ReevaluationReport,
    UpdateResult,
)
from agrag.ingestion.resolve import SYSTEM_RELATION_TYPES
from agrag.ingestion.resolve.zone_classifier import MAX_LLM_PAIRS
from agrag.ingestion.settings import CutoverJobSettings
from agrag.loaders.corpus import registry as _corpus_registry
from agrag.loaders.corpus.base import Loader
from agrag.loaders.corpus.types import ErrorPolicy, ReadOptions
from agrag.observability import get_tracer
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


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
                        roll_forward=graph._cleanup(),
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
        return await add_documents(
            source,
            text=text,
            documents=documents,
            loader=loader,
            error_policy=error_policy,
            on_progress=on_progress,
            return_chunks=return_chunks,
            read_options=read_options,
            schema=self._schema,
            graph_store=self._graph_store,
            embedder=self._embedder,
            extractor=self._extractor,
            vector_store=self._vector_store,
            retrieval_settings=self._retrieval_settings,
            cutover_settings=self._cutover_settings,
            chunking=self._chunking,
            registry=self._registry,
            embed_heading_path=self._embed_heading_path,
            max_llm_pairs=self._max_llm_pairs,
            cleanup=self._cleanup(error_policy),
            tracer=self._tracer,
        )

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
        return await update_document(
            document_key,
            text=text,
            source=source,
            loader=loader,
            error_policy=error_policy,
            read_options=read_options,
            schema=self._schema,
            graph_store=self._graph_store,
            embedder=self._embedder,
            extractor=self._extractor,
            vector_store=self._vector_store,
            retrieval_settings=self._retrieval_settings,
            cutover_settings=self._cutover_settings,
            chunking=self._chunking,
            registry=self._registry,
            embed_heading_path=self._embed_heading_path,
            max_llm_pairs=self._max_llm_pairs,
            cleanup=self._cleanup(error_policy),
            tracer=self._tracer,
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
        return await delete_document(
            document_key,
            graph_store=self._graph_store,
            vector_store=self._vector_store,
            retrieval_settings=self._retrieval_settings,
            cutover_settings=self._cutover_settings,
            cleanup=self._cleanup(),
            tracer=self._tracer,
        )

    def _cleanup(self, error_policy: ErrorPolicy = ErrorPolicy.RAISE) -> CleanupStep:
        """Bind the post-commit cleanup of a Cutover Job to this graph.

        Args:
            error_policy: RAISE propagates the first failure; any other
                policy records it and continues.

        Returns:
            The cleanup step the live calls and crash recovery both run.
        """
        return functools.partial(
            finish_job,
            graph_store=self._graph_store,
            schema=self._schema,
            embedder=self._embedder,
            vector_store=self._vector_store,
            retrieval_settings=self._retrieval_settings,
            tracer=self._tracer,
            error_policy=error_policy,
        )

    async def deactivate_match(self, match_id: UUID) -> list[ResolvedEntity]:
        """Deactivate a semantic match and synchronize replacement retrieval vectors."""
        return await deactivate_match(
            match_id,
            schema=self._schema,
            graph_store=self._graph_store,
            embedder=self._embedder,
            vector_store=self._vector_store,
            retrieval_settings=self._retrieval_settings,
            tracer=self._tracer,
        )

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

        A failed read of an entity's candidates does not stop the pass. That
        entity is not compared in this call and the report lists the failure.

        Returns:
            A report of every confirmed non-exact match, applied or not,
            plus the count of uncertain LLM verdicts and every failure.
        """
        return await consolidate(
            apply=apply,
            schema=self._schema,
            graph_store=self._graph_store,
            embedder=self._embedder,
            vector_store=self._vector_store,
            retrieval_settings=self._retrieval_settings,
            tracer=self._tracer,
            max_llm_pairs=self._max_llm_pairs,
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
        return await reevaluate(
            entity_ids,
            schema=self._schema,
            graph_store=self._graph_store,
            embedder=self._embedder,
            vector_store=self._vector_store,
            retrieval_settings=self._retrieval_settings,
            tracer=self._tracer,
            max_llm_pairs=self._max_llm_pairs,
        )

    async def detect_communities(
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
        return await detect_communities(
            self._graph_store,
            vector_store=self._vector_store,
            embedder=self._embedder,
            settings=self._retrieval_settings,
            tracer=self._tracer,
            apply=apply,
            max_cluster_size=max_cluster_size,
            resolution=resolution,
            seed=seed,
        )
