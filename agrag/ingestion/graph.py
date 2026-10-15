"""The public Graph API for ingestion."""

import contextlib
import functools
import logging
from collections.abc import Callable, Sequence
from importlib.util import find_spec
from pathlib import Path
from typing import Literal
from uuid import UUID

from opentelemetry.trace import Tracer
from pydantic import ValidationError

from agrag.candidates.patch import read_patch
from agrag.chunking import Chunker
from agrag.common.data_models.candidate_review import SchemaPatch
from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.community import COMMUNITY_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL, Document
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.resolved_entity import (
    RESOLVED_ENTITY_LABEL,
    ResolvedEntity,
)
from agrag.common.data_models.structure import (
    DOCUMENT_ACTIVATION_LABEL,
    FIGURE_LABEL,
    SECTION_LABEL,
    SOURCE_LABEL,
    TABLE_LABEL,
)
from agrag.common.schema_fingerprint import (
    LLMOutputSettings,
    RunRecord,
    run_record,
)
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion._candidate_conversion import convert_candidates
from agrag.ingestion._escalation import format_escalation
from agrag.ingestion._ingest import (
    CleanupStep,
    add_documents,
    delete_document,
    purge_document,
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
from agrag.ingestion.extract import (
    BAMLExtractor,
    ExtractionLLMSettings,
    Extractor,
    ExtractorMissingExtraError,
    GlinerExtractor,
    LLMExtractor,
)
from agrag.ingestion.reports import (
    AddResult,
    CommunityDetectionReport,
    ConsolidationReport,
    ConversionReport,
    EscalationReport,
    ReevaluationReport,
    UpdateResult,
)
from agrag.ingestion.resolve import SYSTEM_RELATION_TYPES
from agrag.ingestion.resolve.zone_classifier import MAX_LLM_PAIRS
from agrag.ingestion.settings import (
    EXTRACTION_PROMPT_ID,
    CutoverJobSettings,
    ExtractionSettings,
    effective_mode,
)
from agrag.loaders import registry as _corpus_registry
from agrag.loaders.base import Loader
from agrag.loaders.types import ErrorPolicy, ReadOptions
from agrag.observability import get_tracer
from agrag.schema import load_schema
from agrag.schema.loader import SchemaSource


logger = logging.getLogger(__name__)

_MSG_DEGRADE = (
    'Extraction mode is "hybrid" but no LLM is configured, so this run uses '
    '"gliner". Set EXTRACTION_LLM_CLIENTS, LLM_BASE_URL and LLM_MODEL_ID, or set '
    'mode="gliner" to choose GLiNER only.'
)
_MSG_LLM_MISSING = (
    'Extraction mode "llm" needs an LLM, and none is configured. Set '
    "EXTRACTION_LLM_CLIENTS, LLM_BASE_URL and LLM_MODEL_ID, or pass llm_extractor=."
)
_MSG_EXTRACTOR_IN_LLM_MODE = (
    'extractor= cannot be used with extraction mode "llm", which does not run '
    'GLiNER. Pass llm_extractor= instead, or use mode="hybrid" or mode="gliner".'
)
_MSG_LLM_EXTRACTOR_IN_GLINER_MODE = (
    'llm_extractor= cannot be used with extraction mode "gliner", which does not '
    'run the LLM. Use mode="hybrid" or mode="llm".'
)
_MSG_LLM_EXTRACTOR_IN_LOCAL_SLOT = (
    "Pass an LLMExtractor such as BAMLExtractor as llm_extractor=... with "
    'mode="llm" or mode="hybrid".'
)
_MSG_LOCAL_EXTRACTOR_IN_LLM_SLOT = (
    "Pass a local Extractor such as GlinerExtractor as extractor=..."
)
_MSG_SETTINGS_MISMATCH = (
    "extraction_settings differs from the settings of the GLiNER extractor passed "
    "as extractor=. Pass the same ExtractionSettings object to both, or omit "
    "extraction_settings."
)


def _extraction_settings_of(extractor: Extractor | None) -> ExtractionSettings:
    """Return the GLiNER settings in the local slot, or the defaults."""
    if isinstance(extractor, GlinerExtractor):
        return extractor.settings
    return ExtractionSettings()


def _check_slots(
    settings: ExtractionSettings,
    extractor: Extractor | None,
    llm_extractor: LLMExtractor | None,
    explicit_settings: ExtractionSettings | None,
) -> None:
    """Reject extractor slots that do not fit the selected mode."""
    if isinstance(extractor, LLMExtractor):
        raise ValueError(_MSG_LLM_EXTRACTOR_IN_LOCAL_SLOT)
    if isinstance(llm_extractor, Extractor):
        raise ValueError(_MSG_LOCAL_EXTRACTOR_IN_LLM_SLOT)
    if settings.mode == "llm" and extractor is not None:
        raise ValueError(_MSG_EXTRACTOR_IN_LLM_MODE)
    if settings.mode == "gliner" and llm_extractor is not None:
        raise ValueError(_MSG_LLM_EXTRACTOR_IN_GLINER_MODE)
    if settings.mode == "llm" and llm_extractor is None:
        raise ValueError(_MSG_LLM_MISSING)
    if (
        isinstance(extractor, GlinerExtractor)
        and explicit_settings is not None
        and explicit_settings != extractor.settings
    ):
        raise ValueError(_MSG_SETTINGS_MISMATCH)


def _warn_properties_in_gliner_mode(schema: GraphSchema) -> None:
    """Warn that the local extractor leaves declared entity properties empty."""
    declaring = sorted(item.label for item in schema.entities if item.properties)
    if not declaring:
        return
    logger.warning(
        "Entity types with properties (%s) cannot get property values in gliner "
        "mode. Set EXTRACTION_MODE=hybrid and configure an LLM to extract them.",
        ", ".join(declaring),
    )


def _default_gliner_extractor(
    settings: ExtractionSettings, tracer: Tracer | None
) -> GlinerExtractor:
    """Build the local slot, or explain that the extract extra is required."""
    if find_spec("gliner2") is None:
        raise ExtractorMissingExtraError("GlinerExtractor", "extract")
    try:
        return GlinerExtractor(settings=settings, tracer=tracer)
    except ImportError as error:
        raise ExtractorMissingExtraError("GlinerExtractor", "extract") from error


def _default_llm_extractor(tracer: Tracer | None) -> BAMLExtractor | None:
    """Build the default LLM slot from environment settings when available."""
    try:
        settings = ExtractionLLMSettings()
    except ValidationError as error:
        if any(
            detail["type"] != "missing" or detail["loc"] != ("clients",)
            for detail in error.errors()
        ):
            raise
        try:
            settings = ExtractionLLMSettings.from_openai_compatible_env()
        except RuntimeError:
            return None
    return BAMLExtractor(settings=settings, tracer=tracer)


class Graph:
    """A knowledge graph that a caller can open and add content to."""

    def __init__(
        self,
        *,
        schema: SchemaSource,
        graph_store: GraphStore,
        embedder: Embedder,
        extractor: Extractor | None = None,
        tracer: Tracer | None = None,
        cutover_settings: CutoverJobSettings | None = None,
        extraction_settings: ExtractionSettings | None = None,
        llm_extractor: LLMExtractor | None = None,
        chunker: Chunker | None = None,
        embed_heading_path: bool = True,
        max_llm_pairs: int = MAX_LLM_PAIRS,
    ) -> None:
        """Create a graph bound to a schema, store, embedder, and extractor.

        Args:
            schema: The schema the extractor receives. A ``GraphSchema`` is
                used as given. Any other value goes through ``load_schema``: a
                ``Preset``, a shipped name (``"default"``, ``"operations"`` or
                ``"legal"``), a file path, a dict, a list of strings, a Pydantic
                class, or JSON text. Raises ``SchemaLoadError`` when the
                value is not a valid schema.
            graph_store: Where entities, relations, chunks, and MENTIONED_IN
                edges are written.
            embedder: Populates entity embeddings for native vector search.
            extractor: The local extraction slot, used in ``gliner`` and
                ``hybrid`` modes.
            tracer: A tracer to record spans for every step. Pass None for none.
            cutover_settings: Lease configuration for the Cutover Jobs
                add/update/delete_document run through. None uses
                CutoverJobSettings defaults.
            extraction_settings: The extraction settings this graph uses.
                None uses settings from a GLiNER extractor, or
                the ExtractionSettings defaults. Pass the same object to both.
            llm_extractor: The LLM slot used in ``hybrid`` and ``llm`` modes.
                None builds a BAMLExtractor when LLM settings are configured.
            chunker: The chunker that splits every document. None uses
                ``Chunker()``.
            embed_heading_path: Whether chunk embeddings include the chunk's
                heading path above its text. The stored text does not change.
                Existing embeddings stay until a document is re-chunked with
                ``update()``.
            max_llm_pairs: The most ambiguous entity pairs that resolution sends
                to the LLM for each label. A lower value bounds the number of
                verification calls and leaves more pairs undecided. Zero sends
                no pairs to the LLM.
        """
        self._schema = (
            schema if isinstance(schema, GraphSchema) else load_schema(schema)
        )
        self._graph_store = graph_store
        self._embedder = embedder
        settings = (
            extraction_settings
            if extraction_settings is not None
            else _extraction_settings_of(extractor)
        )
        llm_slot = llm_extractor
        if llm_slot is None and settings.mode != "gliner":
            llm_slot = _default_llm_extractor(tracer)
        _check_slots(settings, extractor, llm_slot, extraction_settings)
        mode = effective_mode(settings, llm_available=llm_slot is not None)
        if settings.mode == "hybrid" and mode == "gliner":
            logger.warning(_MSG_DEGRADE)
        if extractor is None and settings.mode != "llm":
            extractor = _default_gliner_extractor(settings, tracer)
        pipeline_extractor = extractor if extractor is not None else llm_slot
        if pipeline_extractor is None:
            raise RuntimeError("Graph has no extractor for the selected mode")
        if mode == "gliner" and isinstance(pipeline_extractor, GlinerExtractor):
            _warn_properties_in_gliner_mode(self._schema)
        self.extraction_settings = settings
        self._effective_mode = mode
        self._extractor = pipeline_extractor
        self._llm_extractor = llm_slot
        self._tracer = get_tracer(tracer)
        self._registry = _corpus_registry
        self._chunker = chunker or Chunker()
        self._embed_heading_path = embed_heading_path
        self._max_llm_pairs = max_llm_pairs
        self._cutover_settings = cutover_settings or CutoverJobSettings()

    @classmethod
    async def open(
        cls,
        *,
        schema: SchemaSource,
        graph_store: GraphStore,
        embedder: Embedder,
        extractor: Extractor | None = None,
        tracer: Tracer | None = None,
        cutover_settings: CutoverJobSettings | None = None,
        extraction_settings: ExtractionSettings | None = None,
        llm_extractor: LLMExtractor | None = None,
        chunker: Chunker | None = None,
        embed_heading_path: bool = True,
        max_llm_pairs: int = MAX_LLM_PAIRS,
    ) -> "Graph":
        """Open a graph, connecting and fully provisioning graph_store.

        Provisioning order: connect, then register every label/relation type
        this graph will ever write (schema's own labels/types plus the fixed
        system names CHUNK_LABEL/SYSTEM_RELATION_TYPES), then
        setup_constraints(), then setup_indexes(), then vector and full-text
        indexes for every schema entity label, then the full-text index on chunk
        text. A brand-new database is fully ready,
        including the merge_key uniqueness constraints the global exact-match
        tier relies on, the embedding vector indexes native search needs, the
        entity name indexes that entity discovery reads, and the chunk full-text
        index that evidence discovery reads, before this call returns.

        Args:
            schema: The schema the extractor receives. A ``GraphSchema`` is
                used as given. Any other value goes through ``load_schema``: a
                ``Preset``, a shipped name (``"default"``, ``"operations"`` or
                ``"legal"``), a file path, a dict, a list of strings, a Pydantic
                class, or JSON text. Raises ``SchemaLoadError`` when the
                value is not a valid schema.
            graph_store: Where entities, relations, chunks, and MENTIONED_IN
                edges are written.
            embedder: Populates entity embeddings for native vector search.
            extractor: The local extraction slot, used in ``gliner`` and
                ``hybrid`` modes.
            tracer: A tracer to record spans for every step. Pass None for none.
            cutover_settings: Lease configuration for the Cutover Jobs
                add/update/delete_document run through. None uses
                CutoverJobSettings defaults.
            extraction_settings: Extraction settings for this graph; see
                __init__.
            llm_extractor: The LLM slot; see __init__.
            chunker: The chunker that splits every document; see __init__.
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
            Exception: Whatever connect(), registration, constraint/index
                setup, or vector-index provisioning raises. graph_store is
                closed first, so a failed open() never leaks a connection.
        """
        schema = schema if isinstance(schema, GraphSchema) else load_schema(schema)
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
                        DOCUMENT_ACTIVATION_LABEL,
                        DOCUMENT_LABEL,
                        FIGURE_LABEL,
                        RESOLVED_ENTITY_LABEL,
                        SECTION_LABEL,
                        SOURCE_LABEL,
                        TABLE_LABEL,
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
                    await graph_store.ensure_fulltext_index(
                        label=label,
                        properties=["name"],
                    )
                await graph_store.ensure_vector_index(
                    label=CHUNK_LABEL,
                    vector_property="embedding",
                    dimensions=dimensions,
                    distance=distance,
                )
                await graph_store.ensure_fulltext_index(
                    label=CHUNK_LABEL,
                    properties=["text"],
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
                graph = cls(
                    schema=schema,
                    graph_store=graph_store,
                    embedder=embedder,
                    extractor=extractor,
                    tracer=tracer,
                    cutover_settings=cutover_settings,
                    extraction_settings=extraction_settings,
                    llm_extractor=llm_extractor,
                    chunker=chunker,
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
                        roll_forward=graph._cleanup(),
                        lease_ttl_seconds=graph._cutover_settings.lease_ttl_seconds,
                        tracer=resolved_tracer,
                    )
            except Exception:
                await graph_store.close()
                raise
        return graph

    @property
    def chunker(self) -> Chunker:
        """The chunker that splits every document."""
        return self._chunker

    @property
    def effective_mode(self) -> Literal["gliner", "hybrid", "llm"]:
        """The extraction mode this graph uses."""
        return self._effective_mode

    @property
    def llm_extractor(self) -> LLMExtractor | None:
        """The LLM slot, whether injected or built from environment settings."""
        return self._llm_extractor

    @property
    def llm_model_name(self) -> str | None:
        """The model name of the LLM slot, or None when it is unset."""
        slot = self._llm_extractor
        if slot is None:
            return None
        if isinstance(slot, BAMLExtractor) and slot.settings is not None:
            return ",".join(client.model for client in slot.settings.clients)
        return type(slot).__name__

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

        A key that already has a current version is handled as ``update``
        handles it. Content that matches the stored version is skipped and
        counted in ``ingestion.unchanged``, and changed content replaces the
        current version. A key without a current
        version, such as a new key or a deleted document, is added as a new
        document. Calling ``add`` again with the same documents therefore writes
        only what changed.

        If an extraction fails for a chunk, the document and its chunks are
        written without the extraction stamp, so the next ``update`` extracts
        them again instead of returning a no-op.

        Args:
            source: A file path, a directory, a glob, or a list of these.
            text: Raw text to add as one document.
            documents: Already-built documents to add directly.
            loader: A loader to use instead of the registry default. It requires
                a single-file ``source``. A directory, glob, or list of sources
                raises an error.
            error_policy: The action to take on a per-source error.
            on_progress: A callback the call runs after each batch and once more
                at the end with the fully-populated result.
            return_chunks: Whether to include the produced chunks in the
                returned AddResult. False by default to avoid holding full text
                for a large corpus when not needed. Chunks of a document that
                is updated instead of added are not included.
            read_options: How loaders read sources, including the normalization of
                decoded text. None uses ``ReadOptions()`` defaults.

        Returns:
            A summary of what was added per pipeline stage. Resolution runs
                automatically: exact identity plus fuzzy, embedding, and
                capped LLM zones over one combined mention list, with
                confirmed matches persisted as MATCHES edges and derived
                ResolvedEntity nodes. LLM verification calls stay bounded
                at ceil(L * MAX_LLM_PAIRS / 10) requests for L labels;
                within each label, the highest-similarity pairs are verified
                first. Inspect result.resolution.ambiguous_count for uncertain
                model verdicts. ``failed_llm_requests`` counts requests that
                raised, ``cap_truncated_pairs`` counts ambiguous pairs over
                the per-label cap, and ``llm_unavailable_pairs`` counts
                ambiguous pairs skipped because LLM settings or a comparator
                were unavailable.
                These pairs stay undecided. ``in_batch_groups`` counts only
                groups with at least two mentions from this batch.
                ``escalation`` counts the chunks the LLM extractor read in this
                call. The call logs that report at INFO when an LLM extractor
                is set.

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
        result = await add_documents(
            source,
            text=text,
            documents=documents,
            loader=loader,
            error_policy=error_policy,
            on_progress=on_progress,
            return_chunks=return_chunks,
            read_options=read_options,
            schema=self._schema,
            run=self._run_record(),
            graph_store=self._graph_store,
            embedder=self._embedder,
            extractor=self._extractor,
            llm_extractor=self._llm_extractor,
            extraction_settings=self.extraction_settings,
            cutover_settings=self._cutover_settings,
            chunker=self._chunker,
            registry=self._registry,
            embed_heading_path=self._embed_heading_path,
            max_llm_pairs=self._max_llm_pairs,
            write_candidates=self.extraction_settings.candidates_enabled,
            cleanup=self._cleanup(error_policy),
            tracer=self._tracer,
        )
        self._log_escalation(result.escalation)
        return result

    async def update(
        self,
        document_key: str,
        *,
        text: str | None = None,
        source: SourcesType | None = None,
        document: Document | None = None,
        loader: Loader | None = None,
        error_policy: ErrorPolicy = ErrorPolicy.RAISE,
        read_options: ReadOptions | None = None,
        force: bool = False,
    ) -> UpdateResult:
        """Replace one document version, or re-extract it in place.

        Looks up the persisted ``Document`` node by ``document_key``. The update
        is a no-op, returning before any chunking, extraction, or writes, only
        when the document has an open chunk and the content hash, the chunker
        fingerprint, the schema fingerprint, the extraction fingerprint and dates
        all equal the stored ones, and ``force`` is false.
        If only the extraction fingerprint differs (a
        description, a threshold, or the model name), the document is extracted
        again in place. Its chunks stay and are not embedded again. The old
        evidence of the document is removed at the commit, and entities that
        only the old run produced are removed. If the content, the chunker, or
        the schema structure differs, the new version is written. The old
        version closes at the commit, and entities that only the old version
        produced are removed. If an extraction fails for a chunk, the document is
        not stamped current, so the next update extracts it again. An in-place
        update keeps the previous evidence of the failed chunk. Chunks written
        before the fingerprints were recorded are extracted in place when their
        content, chunker, and schema match. A document closed by
        ``delete_document`` has no open chunk, so the same text is added again.
        If only ``published_at`` or ``content_date`` differs, the two dates are
        written and nothing is extracted.

        The new version ingests under a Cutover Job holding this document's
        lease. The commit flips the job, closes the document's open
        ``HAS_PART`` edges, and clears every pending tag in one transaction, so
        a crash either leaves the old version untouched or completes the
        replacement including cleanup. Entities that lose their last evidence
        are pruned after the commit, so replacement mentions count as evidence.
        A source must resolve to exactly one document.

        Args:
            document_key: The stable key of the document to replace.
            text: Replacement text. Give exactly one of ``text``, ``source``, and
                ``document``.
            source: A single-file source, glob, or path list resolving to
                exactly one document.
            document: An already-built replacement Document. It skips loading and
                normalization, so its text and ``content_hash`` are used as given.
                Its ``resolved_document_key`` must equal ``document_key``.
            loader: A loader override for a single-file ``source``.
            error_policy: RAISE propagates a stage failure. Any other
                policy records it and continues. Candidate storage failures
                always abort replacement to preserve committed evidence.
            read_options: How loaders read the replacement, including the
                normalization of its text. None uses ``ReadOptions()`` defaults.
            force: Extract the entities again on the same chunks, even when the
                stored values match. Has no effect when the text, the chunker or
                the schema changed, because those already write a new version.

        Returns:
            The update summary. A no-op reports ``no_op=True`` with no
                ``add_result``. A metadata-only update also has no ``add_result``
                and reports ``parts_closed=0``. The ``decision`` identifies the
                selected update path. An extraction reports ``parts_closed`` plus the
                fresh ingestion's ``add_result``. An unknown ``document_key``
                ingests fresh with ``previous_content_hash=None`` and
                ``parts_closed=0``.

        Raises:
            ValueError: Other than exactly one of ``text``, ``source``, and
                ``document`` is given, a loader override targets multiple sources, a
                source resolves to any number of documents other than one, or the
                ``document`` key differs from ``document_key``.

        Note:
            The fresh-content path shares ``ingest_chunks()`` with
            ``Graph.add()``; both callers observe the same pipeline behavior
            for the same input.
        """
        result = await update_document(
            document_key,
            text=text,
            source=source,
            document=document,
            loader=loader,
            error_policy=error_policy,
            read_options=read_options,
            force=force,
            schema=self._schema,
            run=self._run_record(),
            graph_store=self._graph_store,
            embedder=self._embedder,
            extractor=self._extractor,
            llm_extractor=self._llm_extractor,
            extraction_settings=self.extraction_settings,
            cutover_settings=self._cutover_settings,
            chunker=self._chunker,
            registry=self._registry,
            embed_heading_path=self._embed_heading_path,
            max_llm_pairs=self._max_llm_pairs,
            write_candidates=self.extraction_settings.candidates_enabled,
            cleanup=self._cleanup(error_policy),
            tracer=self._tracer,
        )
        if result.add_result is not None:
            self._log_escalation(result.add_result.escalation)
        return result

    async def delete_document(self, document_key: str) -> UpdateResult:
        """Soft-delete a document by closing its current HAS_PART edges.

        Currency is read transitively through ``HAS_PART``: closing the
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
                under the key, otherwise ``parts_closed`` with
                ``new_content_hash=None`` and no ``add_result``.

        Note:
            The close-only degenerate case of ``Graph.update()``. Both
            call into the same shared document-lifecycle helpers. See
            ``Graph.add()`` for the shared ingestion behavior.
        """
        return await delete_document(
            document_key,
            graph_store=self._graph_store,
            cutover_settings=self._cutover_settings,
            cleanup=self._cleanup(),
            tracer=self._tracer,
        )

    async def purge_document(self, document_key: str) -> UpdateResult:
        """Hard-delete every stored version of a document and its evidence.

        The commit removes the chunk, section, table and figure nodes of every
        version. Each relation that cites those chunks in ``source_chunk_ids``
        drops them, and a relation left with no evidence is deleted, whether or
        not a chunk still mentions its endpoints. Pending candidates that cite
        the chunks are deleted too. Entities that lose their last evidence, the
        ones mentioned by the chunks and the endpoints of the relations they
        cited, are pruned after the commit, as for a delete. The Document node
        and its activation records stay, and each dependent decision is flagged
        ``source_removed``. Purging a key that has no stored content is a no-op.

        This lives on ``Graph`` rather than ``RetentionMemory``: a purge needs
        the graph schema, embedder and cutover settings to clean up, and
        ``RetentionMemory`` covers only project-scoped memory records.

        Args:
            document_key: The stable key of the document to purge.

        Returns:
            The purge summary: ``no_op=True`` when no content was stored under the
                key, otherwise ``parts_closed`` with ``new_content_hash=None``
                and no ``add_result``.
        """
        return await purge_document(
            document_key,
            graph_store=self._graph_store,
            cutover_settings=self._cutover_settings,
            cleanup=self._cleanup(),
            tracer=self._tracer,
        )

    def _run_record(self) -> RunRecord:
        """Describe the current extraction setup for stamping a document."""
        llm_output: LLMOutputSettings | None = None
        if isinstance(self._llm_extractor, BAMLExtractor):
            llm_output = {
                "include_heading_path": self._llm_extractor.include_heading_path
            }
        return run_record(
            self._schema,
            self.extraction_settings,
            effective_mode=self.effective_mode,
            llm_model=self.llm_model_name,
            prompt_id=EXTRACTION_PROMPT_ID,
            llm_output=llm_output,
        )

    def _cleanup(self, error_policy: ErrorPolicy = ErrorPolicy.RAISE) -> CleanupStep:
        """Bind the post-commit cleanup of a Cutover Job to this graph.

        Args:
            error_policy: RAISE propagates the first failure. Any other
                policy records it and continues.

        Returns:
            The cleanup step the live calls and crash recovery both run.
        """
        return functools.partial(
            finish_job,
            graph_store=self._graph_store,
            schema=self._schema,
            embedder=self._embedder,
            tracer=self._tracer,
            max_llm_pairs=self._max_llm_pairs,
            error_policy=error_policy,
        )

    def _log_escalation(self, report: EscalationReport) -> None:
        """Log an escalation report when the graph has an LLM extractor.

        Args:
            report: The report of one add or update call.
        """
        if self._llm_extractor is None:
            return
        for line in format_escalation(report, self.extraction_settings):
            logger.info("%s", line)

    async def deactivate_match(self, match_id: UUID) -> list[ResolvedEntity]:
        """Deactivate a semantic match and embed the replacement resolved entities.

        Raises:
            ValueError: The match does not exist or an in-flight job has not
                committed it.
        """
        return await deactivate_match(
            match_id,
            schema=self._schema,
            graph_store=self._graph_store,
            embedder=self._embedder,
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
        ceil(L * MAX_LLM_PAIRS / 10) requests for L labels, as in Graph.add.
        Within a label, the highest-similarity pairs are verified first.

        Args:
            apply: Write the confirmed matches and rebuild resolved entities.
                False produces a report only.

        A failed read of an entity's candidates does not stop the pass. That
        entity is not compared in this call and the report lists the failure.

        Returns:
            A report of every confirmed non-exact match, applied or not,
                plus the count of uncertain LLM verdicts, failed LLM requests,
                pairs over the per-label cap, pairs skipped because LLM
                settings were missing, and every other failure.
        """
        return await consolidate(
            apply=apply,
            schema=self._schema,
            graph_store=self._graph_store,
            embedder=self._embedder,
            tracer=self._tracer,
            max_llm_pairs=self._max_llm_pairs,
        )

    async def convert_candidates(
        self,
        patch: SchemaPatch | Path,
        *,
        error_policy: ErrorPolicy = ErrorPolicy.RAISE,
    ) -> ConversionReport:
        """Turn approved candidates into graph data after applying their patch.

        The graph must use the updated schema. Entity candidates become entity
        nodes in place or fold into an exact-name owner. Relation and property
        candidates become graph data. Graph writes are atomic; repeated calls
        skip candidates already converted.

        Args:
            patch: The schema patch, or its JSON file path.
            error_policy: How to report description embedding failures that
                occur after the graph transaction commits.

        Returns:
            Counts of converted data and reasons for skipped candidates.

        Raises:
            PatchNotAppliedError: The active schema does not include the patch.
        """
        resolved = read_patch(patch) if isinstance(patch, Path) else patch
        return await convert_candidates(
            resolved,
            graph_store=self._graph_store,
            schema=self._schema,
            embedder=self._embedder,
            error_policy=error_policy,
            tracer=self._tracer,
        )

    async def reevaluate(self, entity_ids: list[UUID]) -> ReevaluationReport:
        """Reevaluate matches among the given entities.

        Fetches exactly the supplied entities, compares same-label pairs
        only among this set through one zone-routed Resolver pass, writes
        confirmed matches that lack an active edge, and deactivates active
        edges only when the resolver rejects their pair. Exact-text pairs
        never gain or lose edges. An active edge is deactivated only when the
        resolver rejects its pair: an embedding score under the discard
        threshold, or an explicit LLM "no match". When the resolver cannot
        decide the pair (the LLM request failed, the pair was over the
        per-label cap, no LLM settings were found, or the model answered
        uncertain), the edge stays active and its id appears in
        ``matches_unverified``. Nothing outside the input set is compared or
        touched, and nothing calls this automatically.

        LLM verification calls stay bounded at ceil(L * MAX_LLM_PAIRS / 10)
        requests for L labels, as in Graph.add. Within a label, the
        highest-similarity pairs are verified first.

        Args:
            entity_ids: The persisted entities to reevaluate, deduped with
                input order preserved.

        Returns:
            Which entities were reevaluated, which matches were added,
                which match edges were deactivated, which were left
                unverified, how many inputs had no incident added or removed
                edge, and the counts of failed LLM requests, pairs over the
                per-label cap, and pairs skipped because LLM settings were
                missing.

        Raises:
            ValueError: An id has no live persisted entity.
        """
        return await reevaluate(
            entity_ids,
            schema=self._schema,
            graph_store=self._graph_store,
            embedder=self._embedder,
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

        Dry-run by default. It produces a report of the communities that the
        call will write before any node is touched. Pass apply=True to write
        them.

        Fetches every live domain relation across the whole graph (not scoped
        by entity label the way consolidate() is; community structure spans
        entity types), builds a weighted edge list, and runs hierarchical
        Leiden off the event loop. Every prior run's Community nodes and
        MEMBER_OF edges are deleted before the new ones are written when
        apply=True. This is a full recompute, not an incremental update,
        so there is no notion of merging this run's output with a
        previous one.

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
            embedder=self._embedder,
            tracer=self._tracer,
            apply=apply,
            max_cluster_size=max_cluster_size,
            resolution=resolution,
            seed=seed,
        )
