"""The Extractor interface: reads one Chunk and produces an ExtractionResult."""

import asyncio
import contextvars
import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Sequence
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Literal, TypedDict
from uuid import UUID

from dotenv import load_dotenv
from opentelemetry.trace import Tracer
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.ingestion._gliner_decode import decode_gliner
from agrag.ingestion._mentions import endpoint_key, locate_mentions
from agrag.ingestion.settings import ExtractionSettings
from agrag.llm.client_config import LLMClientConfig, RetryConfig
from agrag.llm.retry import NO_RETRY, call_with_retry
from agrag.llm.tracing import new_collector
from agrag.loaders.errors import IngestionError
from agrag.observability import get_tracer


logger = logging.getLogger(__name__)


class _CandidateSpec(TypedDict):
    """One entity an earlier extractor kept, as the prompt lists it."""

    label: str
    text: str


def _candidate_specs(
    candidates: Sequence[ExtractedEntity] | None,
) -> list[_CandidateSpec] | None:
    """Return the candidate entries for the prompt, or None when there are none."""
    if not candidates:
        return None
    return [{"label": entity.label, "text": entity.text} for entity in candidates]


def _describe_properties(schema: GraphSchema) -> str | None:
    """Return the guidance for the entity ``properties`` field, or None.

    The field exists only when at least one entity type declares properties.
    A BAML class field is static, while declared properties vary by label, so
    the declared names travel in this description, one line per type.

    Args:
        schema: The schema whose entity types declare properties.

    Returns:
        The field description, or ``None`` when no entity type declares a
        property and the model should not be asked for any.
    """
    lines: list[str] = []
    for entity_type in schema.entities:
        if not entity_type.properties:
            continue
        declared = ", ".join(
            f"{name} ({spec.type}; one of {', '.join(spec.enum)})"
            if spec.enum
            else f"{name} ({spec.type})"
            for name, spec in entity_type.properties.items()
        )
        lines.append(f"{entity_type.label}: {declared}")
    if not lines:
        return None
    return (
        "Property values this entity's type declares, keyed by property name, "
        "taken only from what the text states. Leave out any property the text "
        "does not state. Do not invent property names or values. Declared "
        "properties by type: " + "; ".join(lines)
    )


def _raw_properties(entity: object) -> dict[str, object]:
    """Return the ``properties`` the model attached to one raw entity.

    The field is added to the BAML class at call time, so the generated type
    holds it as an extra field (``model_extra``). It is absent when the schema
    declares no properties or the model left it out.
    """
    extra = getattr(entity, "model_extra", None) or {}
    value = extra.get("properties")
    return dict(value) if isinstance(value, dict) else {}


def _resolve_relation_pair(
    relation: object,
    text_index: dict[str, list[int]],
    valid_raw_entities: list[tuple[Any, int, int]],
    schema: GraphSchema,
) -> tuple[int, int] | None:
    """Return the single (source, target) index pair for one raw relation.

    BAML identifies endpoints only by surface text (compared by
    ``endpoint_key``, so case and whitespace differences do not matter), so
    each endpoint text can match several entities. Walk candidate source and
    target indices in order and return the first pair whose endpoint labels
    satisfy the schema, including inherited labels and symmetry. Return None
    when the relation label is undeclared, an endpoint text matches no entity,
    or every pairing self-references. Callers drop such relations rather than
    raise.
    """
    source_candidates = text_index.get(endpoint_key(relation.source_text), [])  # ty: ignore[unresolved-attribute]
    target_candidates = text_index.get(endpoint_key(relation.target_text), [])  # ty: ignore[unresolved-attribute]
    for source_index in source_candidates:
        for target_index in target_candidates:
            if source_index == target_index:
                continue
            source_label = valid_raw_entities[source_index][0].label
            target_label = valid_raw_entities[target_index][0].label
            if schema.allows(relation.label, source_label, target_label):  # ty: ignore[unresolved-attribute]
                return (source_index, target_index)
    return None


def validate_extraction(
    result: ExtractionResult, schema: GraphSchema
) -> ExtractionResult:
    """Drop entities and relations that the schema does not declare.

    The pipeline applies this to the result of every extractor, so a custom
    extractor cannot send an undeclared label to the graph. An entity
    survives only when its label is a declared EntityType, and keeps only the
    property keys that EntityType declares. A relation survives only when both
    of its entities survive and ``schema.allows`` accepts its label and
    resolved (source label, target label) pair. Relation indices are remapped
    to the surviving entities. A drop is logged with a count.

    Args:
        result: The extractor's result, before schema validation.
        schema: The schema entities and relations are validated against.

    Returns:
        A copy of ``result`` holding only schema-declared entities and
        relations, with relation indices remapped and each entity's properties
        limited to its declared keys. ``candidates`` and ``needs_properties``
        are unchanged.
    """
    entity_types_by_label = {
        entity_type.label: entity_type for entity_type in schema.entities
    }
    valid_entities: list[ExtractedEntity] = []
    index_remap: dict[int, int] = {}
    dropped_properties = 0
    for old_index, entity in enumerate(result.entities):
        entity_type = entity_types_by_label.get(entity.label)
        if entity_type is None:
            continue
        index_remap[old_index] = len(valid_entities)
        valid_entity = entity
        if entity.properties:
            declared = {
                key: value
                for key, value in entity.properties.items()
                if key in entity_type.properties
            }
            if declared != entity.properties:
                dropped_properties += len(entity.properties) - len(declared)
                valid_entity = entity.model_copy(update={"properties": declared})
        valid_entities.append(valid_entity)

    valid_relations: list[ExtractedRelation] = []
    for relation in result.relations:
        if (
            relation.source_index not in index_remap
            or relation.target_index not in index_remap
        ):
            continue
        new_source = index_remap[relation.source_index]
        new_target = index_remap[relation.target_index]
        if not schema.allows(
            relation.label,
            valid_entities[new_source].label,
            valid_entities[new_target].label,
        ):
            continue
        valid_relations.append(
            relation.model_copy(
                update={"source_index": new_source, "target_index": new_target}
            )
        )

    dropped_entities = len(result.entities) - len(valid_entities)
    dropped_relations = len(result.relations) - len(valid_relations)
    if dropped_entities or dropped_relations or dropped_properties:
        logger.warning(
            "Dropped %d entities, %d relations and %d properties from %s "
            "that the schema does not declare",
            dropped_entities,
            dropped_relations,
            dropped_properties,
            result.extractor_name,
        )
    return result.model_copy(
        update={"entities": valid_entities, "relations": valid_relations}
    )


def _infer(
    model: object,
    text: str,
    main_schema: object,
    band_schema: object | None,
    settings: ExtractionSettings,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Run the gliner2 calls for one chunk on the calling thread.

    The main call reads entities at ``entity_threshold``. The schema carries a
    threshold for every relation, so the same call returns relations from
    ``relation_floor``. The band call reads entities at ``band_floor``, which
    lets the caller see the spans between the two thresholds. The two calls
    stay apart because gliner2 resolves overlap after it applies the
    threshold: a lower threshold can drop a span that the higher one keeps.

    Args:
        model: The GLiNER2.5 model.
        text: The chunk text.
        main_schema: The schema with entities and relations.
        band_schema: The entity-only schema for the band call, or None to skip
            that call.
        settings: Supplies both thresholds.

    Returns:
        The raw result of the main call, and of the band call. The band result
        is None when no band call ran or when the band call raised.
    """
    raw = model.extract(  # ty: ignore[unresolved-attribute]
        text,
        main_schema,
        threshold=settings.entity_threshold,
        include_confidence=True,
        include_spans=True,
    )
    if band_schema is None:
        return raw, None
    try:
        band_raw = model.extract(  # ty: ignore[unresolved-attribute]
            text,
            band_schema,
            threshold=settings.band_floor,
            include_confidence=True,
            include_spans=True,
        )
    except Exception:
        logger.warning(
            "Band inference failed; keeping the main result without band candidates.",
            exc_info=True,
        )
        return raw, None
    return raw, band_raw


class ExtractorMissingExtraError(IngestionError):
    """An Extractor needs a package extra that is not installed.

    Attributes:
        component: The class name that needs the extra.
        extra: The package extra to install.
    """

    def __init__(self, component: str, extra: str) -> None:
        """Bind the offending component and the missing extra to the error."""
        super().__init__(
            f"{component!r} needs the {extra!r} extra: "
            f"pip install 'agentic-graphrag[{extra}]'"
        )
        self.component = component
        self.extra = extra


class UnparsableExtractionError(IngestionError):
    """The LLM replied, but the reply holds no JSON answer.

    BAML turns a reply it cannot read into an empty result instead of raising.
    This error tells that case apart from a model that answered "nothing found".

    Attributes:
        chunk_id: The chunk whose extraction failed.
    """

    def __init__(self, chunk_id: UUID) -> None:
        """Bind the chunk id to the error."""
        super().__init__(f"The LLM reply for chunk {chunk_id} holds no JSON answer.")
        self.chunk_id = chunk_id


_JSON_DECODER = json.JSONDecoder()


def _reply_holds_answer(reply: str) -> bool:
    """Return whether reply holds a JSON answer, even an empty one.

    A JSON object with an ``entities`` key or an empty JSON list counts.
    Anything else, such as prose or a cut-off object, does not.
    """
    # Prose can surround the JSON, so every opening brace and bracket is tried.
    for start, char in enumerate(reply):
        if char not in "{[":
            continue
        try:
            value, _ = _JSON_DECODER.raw_decode(reply, start)
        except ValueError:
            continue
        if isinstance(value, dict) and "entities" in value:
            return True
        if value == []:
            return True
    return False


def _last_reply(collector: object | None) -> str | None:
    """Return the raw text of the last reply a BAML collector recorded."""
    log = getattr(collector, "last", None)
    return getattr(log, "raw_llm_response", None)


def _has_relations(raw: object, schema: GraphSchema) -> bool:
    """Return whether the parsed reply holds any raw relation."""
    return bool(schema.relations and raw.relations)  # ty: ignore[unresolved-attribute]


class Extractor(ABC):
    """Reads one chunk and returns the entities and relations it contains.

    Note:
        Subclass this class to provide custom extraction. ``Graph`` awaits
        ``extract`` once for each chunk. ``GlinerExtractor`` is a local
        extractor. ``LLMExtractor`` marks the LLM role: ``Graph`` gives it only
        the weakest chunks, as ``llm_extractor``. ``Graph`` drops any entity or
        relation whose label the schema does not declare, and logs the count.

        ``Graph`` runs up to ``max_concurrency`` ``extract`` calls at the same
        time. An extractor that is not safe to call from several tasks at once
        sets ``max_concurrency`` to 1 or makes its calls take turns itself, for
        example with an ``asyncio.Lock``.

    Attributes:
        max_concurrency: The most ``extract`` calls that run at once for one
            batch of chunks. Must be positive.
    """

    max_concurrency: int = 8

    @abstractmethod
    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Extract entities and relations from one chunk.

        Args:
            chunk: The chunk to read. Only ``chunk.text`` and ``chunk.id`` are used.
            schema: The entity/relation types to extract. Every returned entity's
                ``label`` and relation's ``label`` must be declared in this schema.

        Returns:
            The entities and relations this call found, in extraction order.
        """


class LLMExtractor(ABC):
    """LLM role that may receive entities found by an earlier extractor."""

    max_concurrency: int | None = None

    @abstractmethod
    async def extract(
        self,
        chunk: Chunk,
        schema: GraphSchema,
        candidates: Sequence[ExtractedEntity] | None = None,
    ) -> ExtractionResult:
        """Extract entities and relations from one chunk.

        Args:
            chunk: The chunk to read.
            schema: The entity and relation types to extract.
            candidates: Entities found by an earlier extractor. Escalation may
                pass them for review; an implementation may ignore them.

        Returns:
            The entities and relations found in the chunk.
        """


class ExtractionLLMSettings(BaseSettings):
    """Env-backed LLM client configuration for the extraction role.

    Attributes:
        clients: The LLM clients to use. One element for a single provider.
            More than one is composed per ``strategy``.
        strategy: How to compose multiple clients. Ignored with one client.
        retry: Retry configuration applied to the extraction LLM call.

    Env prefix: ``EXTRACTION_LLM_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="EXTRACTION_LLM_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    clients: list[LLMClientConfig]
    strategy: Literal["single", "fallback", "round_robin"] = "single"
    retry: RetryConfig = Field(default_factory=RetryConfig)

    @classmethod
    def from_openai_compatible_env(cls) -> "ExtractionLLMSettings":
        """Build settings from a generic OpenAI-compatible endpoint.

        Reads ``LLM_BASE_URL``, ``LLM_API_KEY``, and ``LLM_MODEL_ID`` from the
        environment or ``.env``, so the model name is never hardcoded. Raises
        ``RuntimeError`` when the required variables are not all set.

        Returns:
            Settings pointing at one ``openai-generic`` client.
        """
        load_dotenv(dotenv_path=".env")
        base_url = os.environ.get("LLM_BASE_URL")
        api_key = os.environ.get("LLM_API_KEY")
        model = os.environ.get("LLM_MODEL_ID")
        if not base_url or not model:
            raise RuntimeError(
                "from_openai_compatible_env needs LLM_BASE_URL and LLM_MODEL_ID set."
            )
        client = LLMClientConfig(
            name="openai-generic",
            provider="openai-generic",
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
        return cls(clients=[client])


class GlinerExtractor(Extractor):
    """Extracts entities and relations with a local GLiNER2.5 model.

    The model runs in this process, so extraction needs no LLM key. It loads on
    first use and one load serves concurrent calls. Inference calls run one at a
    time on one worker thread. A call cancelled while it waits for its turn never
    starts, and one cancelled mid-inference leaves the next call waiting until the
    inference ends. The first load downloads the weights from Hugging Face unless
    ``model`` is passed. Needs the ``extract`` extra.

    One model call reads the whole schema: every entity type and every relation,
    each with its description. Entities need ``settings.entity_threshold``.
    Relations need ``settings.relation_threshold`` and must match a pattern of
    the schema, where a pattern also accepts the child types of its labels. When
    the model returns the same words under a parent type and a child type, the
    label with the higher score is kept. Every kept entity and relation carries
    its confidence.

    The extractor reports what it dropped as candidates in the result: relations
    below the threshold, that match no pattern, or whose endpoint is not a kept
    entity. With ``settings.candidates_enabled`` it also makes a second model
    call at ``settings.band_floor`` and reports entity spans that score between
    that floor and the entity threshold and do not overlap a kept entity.

    The model reports spans and types only, so extracted entities carry no
    property values. The result sets ``needs_properties`` when a kept entity has
    a type that declares properties. Chunks of the default size fit the model in
    one pass.

    Args:
        settings: Model name, data type and thresholds. Defaults to
            ``ExtractionSettings()``, loaded from the environment or ``.env``.
        model: An already-built GLiNER2.5 model.
        tracer: Opens ``agrag.extraction.gliner`` and
            ``agrag.extraction.model_load`` spans. ``None`` opens no recorded
            span.

    Attributes:
        settings: The checkpoint, precision and thresholds used by extraction.
    """

    # Inference runs on one worker thread, so extra concurrent calls only queue.
    max_concurrency = 1

    def __init__(
        self,
        *,
        settings: ExtractionSettings | None = None,
        model: object | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        """Create an extractor from settings or an already-built model."""
        self.settings = settings if settings is not None else ExtractionSettings()
        self._model = model
        self._tracer = tracer
        self._load_task: asyncio.Task[object] | None = None
        self._inference_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="gliner"
        )

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Extract with the local GLiNER2.5 model.

        Args:
            chunk: The chunk to read. Only ``chunk.text`` and ``chunk.id`` are used.
            schema: The entity and relation types to extract.

        Returns:
            The normalized entities and relations found in the chunk.

        Raises:
            ExtractorMissingExtraError: The ``extract`` package extra is not
                installed.
            ValueError: ``chunk.id`` is ``None``.
        """
        if chunk.id is None:
            raise ValueError("Chunk must have an id for extraction.")
        with get_tracer(self._tracer).start_as_current_span(
            "agrag.extraction.gliner",
            attributes={"agrag.chunk_id": str(chunk.id)},
        ) as span:
            model = await self._load_model()
            settings = self.settings
            main_schema = self._build_schema(model, schema, band=False)
            band_schema = (
                self._build_schema(model, schema, band=True)
                if settings.candidates_enabled
                else None
            )
            # Unlike asyncio.to_thread, run_in_executor does not copy the context,
            # so copy it here to keep the active trace span in the inference thread.
            raw, band_raw = await asyncio.get_running_loop().run_in_executor(
                self._inference_executor,
                partial(
                    contextvars.copy_context().run,
                    _infer,
                    model,
                    chunk.text,
                    main_schema,
                    band_schema,
                    settings,
                ),
            )
            result = decode_gliner(raw, band_raw, chunk, schema, settings)
            span.set_attribute("agrag.entities_extracted", len(result.entities))
            span.set_attribute("agrag.relations_extracted", len(result.relations))
            return result

    async def _load_model(self) -> object:
        """Return the cached model, loading it once even under concurrent calls.

        All callers await the same shared task via asyncio.shield, so a
        cancelled waiter does not stop or hide the load: the worker thread
        asyncio.to_thread starts keeps running regardless of the cancellation
        (Python cannot interrupt a running thread), and shield keeps the task
        itself alive for a later caller to discover through self._load_task
        and await afresh. A lock alone doesn't give this — cancelling a waiter
        parked on `async with lock` releases the lock while the abandoned
        thread keeps running unobserved, so a second caller starts a second
        load. A load that raises clears self._load_task so the next call
        retries instead of reusing a broken one.
        """
        if self._model is not None:
            return self._model
        if self._load_task is None:
            self._load_task = asyncio.ensure_future(
                asyncio.to_thread(self._ensure_model)
            )
        task = self._load_task
        try:
            model = await asyncio.shield(task)
        except Exception:
            # CancelledError is a BaseException, not caught here, so a
            # cancelled waiter leaves self._load_task in place for others.
            if self._load_task is task:
                self._load_task = None
            raise
        if self._load_task is task:
            self._load_task = None
        self._model = model
        return model

    def _ensure_model(self) -> object:
        """Return the cached model, building it from settings on first call."""
        if self._model is not None:
            return self._model
        try:
            from gliner2 import AutoExtractor  # noqa: PLC0415
        except ImportError as exc:
            raise ExtractorMissingExtraError("GlinerExtractor", "extract") from exc
        with get_tracer(self._tracer).start_as_current_span(
            "agrag.extraction.model_load",
            attributes={"agrag.model": self.settings.model_name},
        ):
            model = AutoExtractor.from_pretrained(self.settings.model_name)
            if self.settings.dtype != "fp32":
                model.quantize(self.settings.dtype)
            self._model = model
            logger.info(
                "Loaded GLiNER model %s (dtype=%s, entity_threshold=%s, "
                "label_thresholds=%s).",
                self.settings.model_name,
                self.settings.dtype,
                self.settings.entity_threshold,
                self.settings.label_thresholds,
            )
        return self._model

    def _build_schema(
        self, model: object, schema: GraphSchema, *, band: bool
    ) -> object:
        """Return a GLiNER2.5 schema object built from the types of schema.

        GLiNER2.5 takes a label -> description mapping, so each description
        reaches the model as guidance. A label with an entry in
        ``settings.label_thresholds`` gets its own entity threshold. Every
        relation gets a threshold of ``relation_floor``, or less when its label
        threshold is lower, so the model returns relations that score below the
        relation cut and the caller can report them. Every declared entity type
        is listed, parents and children alike, so the model sees both labels.

        Args:
            model: The GLiNER2.5 model.
            schema: The schema to read.
            band: Whether to build the entity-only schema for the band call. It
                has no label thresholds, so all labels read at the call
                threshold.
        """
        settings = self.settings
        builder = model.create_schema()  # ty: ignore[unresolved-attribute]
        entities: dict[str, str | dict[str, object]] = {}
        for entity in schema.entities:
            override = None if band else settings.label_thresholds.get(entity.label)
            entities[entity.label] = (
                entity.description
                if override is None
                else {"description": entity.description, "threshold": override}
            )
        builder = builder.entities(entities)
        if band:
            return builder
        relations = {
            relation.label: {
                "description": relation.description,
                "threshold": min(
                    settings.relation_floor,
                    settings.label_thresholds.get(
                        relation.label, settings.relation_floor
                    ),
                ),
            }
            for relation in schema.relations
        }
        return builder.relations(relations)


class BAMLExtractor(LLMExtractor):
    """Extract entities and relations with an LLM through a typed BAML function.

    The extractor calls ``ExtractEntitiesAndRelations`` on the clients in
    ``ExtractionLLMSettings`` and retries failed calls with the backoff from
    its configuration. The model sees each label with its description through
    the enum values. The model answers with labels and names only. The
    extractor finds each name in the chunk text and drops a name that is not
    there. The response type comes from the graph schema, so the model can
    return only declared labels. When an entity type declares properties, the
    model also fills a ``properties`` value for each entity. A reply that holds
    no JSON answer raises ``UnparsableExtractionError``. Needs the ``llm``
    extra and a reachable LLM endpoint.

    Args:
        settings: LLM client configuration. Defaults to ``ExtractionLLMSettings()``,
            loaded from the environment or ``.env``. Ignored when ``client`` is
            given. An injected client also disables ``settings.retry`` because
            its caller owns retry behavior.
        client: An already-built BAML client exposing
            ``ExtractEntitiesAndRelations``.
        tracer: Opens ``agrag.extraction.baml`` and ``agrag.llm.call`` spans.
            ``None`` opens no recorded span.
        include_heading_path: Whether to pass the chunk's heading path as a
            separate ``section`` line. The heading is never searched for
            mentions, so an entity found only in the heading is dropped; only
            this extractor uses heading context.
    """

    def __init__(
        self,
        *,
        settings: "ExtractionLLMSettings | None" = None,
        client: object | None = None,
        tracer: Tracer | None = None,
        include_heading_path: bool = True,
    ) -> None:
        """Create an extractor from settings or an already-built BAML client."""
        self.settings = settings
        self._client = client
        self._tracer = tracer
        self._include_heading_path = include_heading_path

    @property
    def include_heading_path(self) -> bool:
        """Whether the chunk's heading path is sent to the model as context."""
        return self._include_heading_path

    async def extract(
        self,
        chunk: Chunk,
        schema: GraphSchema,
        candidates: Sequence[ExtractedEntity] | None = None,
    ) -> ExtractionResult:
        """Extract with an LLM call through the configured ClientRegistry.

        Args:
            chunk: The chunk to read. Only ``chunk.text`` and ``chunk.id`` are used.
            schema: The entity and relation types to extract.
            candidates: Entities an earlier extractor found. They are listed in
                the prompt for the model to check. None or empty gives the
                prompt without that list.

        Returns:
            The entities and relations found in the chunk. An empty result means
            the model answered with no entities or relations.

        Raises:
            ExtractorMissingExtraError: The ``llm`` package extra is not
                installed.
            UnparsableExtractionError: The reply holds no JSON answer, such as
                prose or a cut-off object.
            ValueError: ``chunk.id`` is ``None``.
        """
        if chunk.id is None:
            raise ValueError("Chunk must have an id for extraction.")
        chunk_id = chunk.id
        with get_tracer(self._tracer).start_as_current_span(
            "agrag.extraction.baml",
            attributes={"agrag.chunk_id": str(chunk.id)},
        ) as span:
            if self._client is not None:
                client = self._client
                baml_options: dict = {}
                retry = NO_RETRY
            else:
                from agrag.llm.client_registry import (  # noqa: PLC0415
                    build_client_registry,
                )

                client = self._default_client()
                settings = self.settings or ExtractionLLMSettings()
                registry = build_client_registry(
                    settings.clients, strategy=settings.strategy
                )
                baml_options = {"client_registry": registry}
                retry = settings.retry
            section = chunk.section_label() if self._include_heading_path else None
            span.set_attribute("agrag.extraction.heading_context", section is not None)
            type_builder = self._type_builder_for(schema)
            call_options: dict = {**baml_options}
            if type_builder is not None:
                call_options["tb"] = type_builder
            candidate_specs = _candidate_specs(candidates)
            # The collector keeps the raw reply, which BAML does not return
            # when it parses the reply to an empty result. It is added even when
            # tracing is off, because the unparsable check depends on it.
            reply_log = new_collector()

            def attempt(options: dict) -> Awaitable[object]:
                """Run one call, adding a collector that keeps the raw reply."""
                if reply_log is not None:
                    existing = options.get("collector")
                    collectors = [] if existing is None else [existing]
                    options = {**options, "collector": [*collectors, reply_log]}
                return client.ExtractEntitiesAndRelations(  # ty: ignore[unresolved-attribute]
                    chunk.text, section, candidate_specs, options
                )

            # ponytail: retries every exception except the BAML error types
            # call_with_retry recognizes as permanently unretryable (an invalid
            # argument or a non-429 4xx); narrow further if that proves noisy.
            raw = await call_with_retry(
                attempt,
                retry,
                options=call_options,
                tracer=self._tracer,
                function="ExtractEntitiesAndRelations",
            )
            reply = _last_reply(reply_log)
            # The parsed object decides, not the located entities: a reply whose
            # names the chunk does not hold is still an answer.
            nothing_parsed = not raw.entities and not _has_relations(raw, schema)  # ty: ignore[unresolved-attribute]
            if nothing_parsed and reply is not None and not _reply_holds_answer(reply):
                span.set_attribute("agrag.extraction.unparsable", True)
                raise UnparsableExtractionError(chunk_id)
            result = validate_extraction(self._to_result(raw, chunk, schema), schema)
            span.set_attribute("agrag.entities_extracted", len(result.entities))
            span.set_attribute("agrag.relations_extracted", len(result.relations))
            return result

    def _default_client(self) -> object:
        """Return the default generated BAML client."""
        try:
            from agrag.llm.baml_client import b  # noqa: PLC0415
        except ImportError as exc:
            raise ExtractorMissingExtraError("BAMLExtractor", "llm") from exc
        return b

    def _type_builder_for(self, schema: GraphSchema) -> object | None:
        """Return a TypeBuilder populated with the schema's labels.

        The enums make the BAML parser drop any entity or relation whose label
        is not in the schema, before agrag sees it. Each enum value carries its
        label and its type's description, and BAML prints them once in the
        output format. No type pairs are sent; the pattern check runs after
        extraction. The ``relations`` field is added only when the schema
        declares relation types, and the ``properties`` field only when an
        entity type declares properties.

        Returns ``None`` when the ``llm`` extra is not installed and an
        injected client is being used, so callers can skip the ``tb`` option.
        """
        try:
            from agrag.llm.baml_client.type_builder import TypeBuilder  # noqa: PLC0415
        except ImportError:
            if self._client is not None:
                return None
            raise

        builder = TypeBuilder()
        for entity_type in schema.entities:
            builder.ExtractedEntityLabel.add_value(entity_type.label).description(
                entity_type.description
            )
        if schema.relations:
            for relation_type in schema.relations:
                builder.ExtractedRelationLabel.add_value(
                    relation_type.label
                ).description(relation_type.description)
            builder.BAMLExtractionResult.add_property(
                "relations", builder.list(builder.BAMLExtractedRelation.type())
            )
        properties = _describe_properties(schema)
        if properties is not None:
            builder.BAMLExtractedEntity.add_property(
                "properties", builder.map(builder.string(), builder.string()).optional()
            ).description(properties)
        return builder

    def _to_result(
        self, raw: object, chunk: Chunk, schema: GraphSchema
    ) -> ExtractionResult:
        """Return an ExtractionResult, finding each mention in the chunk text.

        The model reports labels and names, not offsets. ``locate_mentions``
        finds the span of each name in ``chunk.text``. A name the chunk does
        not hold, including one that only the heading holds, is dropped
        together with any relation that names it. The n-th listing of the same
        label and name maps to the n-th occurrence. One name under two labels
        keeps both labels on one span, so a relation that needs the second
        label still resolves.

        BAML returns each relation's endpoints as text, not an index into
        ``raw.entities``, so duplicate surface text is inherently ambiguous:
        every mention sharing an endpoint's text is a candidate for that
        endpoint. Each raw relation yields at most one (source, target) pair:
        the first candidate pairing the schema allows. An undeclared relation
        label, an endpoint whose text matches no mention, or a relation that
        collapses to a single mention (self-reference) is dropped, not raised,
        so one bad relation does not fail the whole chunk.

        Each entity's ``properties`` pass through as reported; schema
        validation of the property keys happens later, in
        ``validate_extraction``. Entities carry no confidence.
        """
        if chunk.id is None:
            raise ValueError("Chunk must have an id for extraction.")
        chunk_id = chunk.id
        raw_entities = list(raw.entities)  # ty: ignore[unresolved-attribute]
        spans = locate_mentions(
            [(entity.label, entity.text) for entity in raw_entities], chunk.text
        )
        located: list[tuple[Any, int, int]] = [
            (entity, span[0], span[1])
            for entity, span in zip(raw_entities, spans, strict=True)
            if span is not None
        ]
        entities = [
            ExtractedEntity(
                chunk_id=chunk_id,
                label=entity.label,
                text=chunk.text[start:end],
                char_start=start,
                char_end=end,
                confidence=None,
                properties=_raw_properties(entity),
            )
            for entity, start, end in located
        ]
        text_index: dict[str, list[int]] = {}
        for index, (entity, _, _) in enumerate(located):
            text_index.setdefault(endpoint_key(entity.text), []).append(index)

        raw_relations = (
            raw.relations if schema.relations else []  # ty: ignore[unresolved-attribute]
        )
        relations: list[ExtractedRelation] = []
        seen_pairs: set[tuple[int, int, str]] = set()
        for relation in raw_relations:
            chosen = _resolve_relation_pair(relation, text_index, located, schema)
            if chosen is None or (chosen[0], chosen[1], relation.label) in seen_pairs:
                continue
            seen_pairs.add((chosen[0], chosen[1], relation.label))
            relations.append(
                ExtractedRelation(
                    chunk_id=chunk_id,
                    label=relation.label,
                    source_index=chosen[0],
                    target_index=chosen[1],
                )
            )
        return ExtractionResult(
            entities=entities, relations=relations, extractor_name="baml"
        )
