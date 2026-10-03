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
from agrag.common.data_models.document import (
    DOCUMENT_LABEL,
    Document,
)
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.resolved_entity import (
    RESOLVED_ENTITY_LABEL,
    ResolvedEntity,
)
from agrag.common.data_models.stage_failure import StageFailure
from agrag.common.text import normalize_text
from agrag.cypher.entities import (
    fetch_all_by_label_query,
)
from agrag.cypher.resolution_read import fetch_active_matches_among_ids_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.graphdb.entities import load_entities
from agrag.graphdb.serialize import parse_entity_node
from agrag.ingestion._ingest import (
    CleanupStep,
    add_documents,
    delete_document,
    update_document,
)
from agrag.ingestion._job_cleanup import finish_job
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
    write_matches_and_rebuild,
)
from agrag.ingestion.settings import CutoverJobSettings
from agrag.loaders.corpus import registry as _corpus_registry
from agrag.loaders.corpus.base import Loader
from agrag.loaders.corpus.types import ErrorPolicy, ReadOptions
from agrag.observability import get_tracer, record_stage_failure
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
