"""The Extractor interface: reads one Chunk and produces an ExtractionResult."""

import asyncio
import os
from abc import ABC, abstractmethod
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.llm.client_config import LLMClientConfig, RetryConfig
from agrag.loaders.corpus.errors import IngestionError


def _normalize_extraction_result(
    result: ExtractionResult, schema: GraphSchema
) -> ExtractionResult:
    """Drop relations whose label or endpoint-label pair schema does not allow.

    A relation survives only when its label is a declared RelationType and the
    resolved (source label, target label) pair is one of that type's ``patterns``.

    Args:
        result: The extractor's raw result, before schema validation.
        schema: The schema relations are validated against.

    Returns:
        A new ExtractionResult with the same entities and only the relations
        that passed validation.
    """
    allowed_pairs = {
        relation_type.label: set(relation_type.patterns)
        for relation_type in schema.relations
    }
    valid_relations = [
        relation
        for relation in result.relations
        if (
            result.entities[relation.source_index].label,
            result.entities[relation.target_index].label,
        )
        in allowed_pairs.get(relation.label, set())
    ]
    return ExtractionResult(
        entities=result.entities,
        relations=valid_relations,
        extractor_name=result.extractor_name,
    )


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


class Extractor(ABC):
    """Reads one Chunk and produces the entities and relations it contains."""

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


class ExtractionLLMSettings(BaseSettings):
    """Env-backed LLM client config for the extraction role.

    Attributes:
        clients: The LLM client(s) to use. One element for a single provider;
            more than one composed per ``strategy``.
        strategy: How to compose multiple clients. Ignored with one client.
        retry: Retry settings applied to the extraction LLM call.

    Env prefix: ``EXTRACTION_LLM_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="EXTRACTION_LLM_", env_file=".env", extra="ignore"
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
        load_dotenv()
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
    """Extracts locally with a GLiNER2.5 model. No network call."""

    def __init__(
        self,
        *,
        model_name: str = "fastino/gliner2.5-small-v1",
        model: object | None = None,
    ) -> None:
        """Create an extractor with a model name or an already-built model.

        Args:
            model_name: The checkpoint to load if ``model`` is not given.
            model: An already-built GLiNER2.5 model. Tests inject a fake here
                to avoid a real model download.
        """
        self.model_name = model_name
        self._model = model
        self._load_lock = asyncio.Lock()

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Extract with the local GLiNER2.5 model.

        Raises:
            ExtractorMissingExtraError: The ``extract`` package extra is not
                installed.
            ValueError: ``chunk.id`` is ``None``.
        """
        if chunk.id is None:
            raise ValueError("Chunk must have an id for extraction.")
        model = await self._load_model()
        gliner_schema = self._build_schema(model, schema)
        raw = await asyncio.to_thread(
            model.extract,  # ty: ignore[unresolved-attribute]
            chunk.text,
            gliner_schema,
            include_spans=True,
        )
        return _normalize_extraction_result(self._to_result(raw, chunk), schema)

    async def _load_model(self) -> object:
        """Return the cached model, loading it once even under concurrent calls.

        Concurrent first calls block on the same lock instead of each starting
        their own model load. A failed load releases the lock without caching
        anything, so the next call retries it cleanly.
        """
        if self._model is not None:
            return self._model
        async with self._load_lock:
            if self._model is None:
                self._model = await asyncio.to_thread(self._ensure_model)
        return self._model

    def _ensure_model(self) -> object:
        """Return the cached model, building it from ``model_name`` on first call."""
        if self._model is not None:
            return self._model
        try:
            from gliner2 import AutoExtractor  # noqa: PLC0415
        except ImportError as exc:
            raise ExtractorMissingExtraError("GlinerExtractor", "extract") from exc
        self._model = AutoExtractor.from_pretrained(self.model_name)
        return self._model

    def _build_schema(self, model: object, schema: GraphSchema) -> object:
        """Return a GLiNER2.5 schema object built from schema's labels and guidance.

        GLiNER2.5's ``entities()``/``relations()`` accept a label -> description
        dict, so each type's ``description`` reaches the model as extraction
        guidance instead of being dropped.
        """
        builder = model.create_schema()  # ty: ignore[unresolved-attribute]
        builder = builder.entities(
            {entity.label: entity.description for entity in schema.entities}
        )
        return builder.relations(
            {relation.label: relation.description for relation in schema.relations}
        )

    def _to_result(self, raw: object, chunk: Chunk) -> ExtractionResult:
        """Return an ExtractionResult built from gliner2's raw output.

        Called with ``include_spans=True``, GLiNER2.5's extract() returns a dict
        with ``entities`` (label -> list of ``{"text", "start", "end"}`` mention
        dicts) and ``relation_extraction`` (label -> list of ``{"head", "tail"}``
        dicts, each endpoint shaped like a mention dict). Relation endpoints are
        matched back to entities by (text, start, end), not by text alone, so two
        mentions with identical surface text still resolve to their own entity.
        """
        if chunk.id is None:
            raise ValueError("Chunk must have an id for extraction.")
        raw_dict: dict = raw  # ty: ignore[invalid-assignment]
        raw_entities: dict[str, list[dict]] = raw_dict.get("entities", {})
        raw_relations: dict[str, list[dict]] = raw_dict.get("relation_extraction", {})

        entities: list[ExtractedEntity] = []
        span_index: dict[tuple[str, int, int], int] = {}
        chunk_id = chunk.id
        for label, mentions in raw_entities.items():
            for mention in mentions:
                span_index[(mention["text"], mention["start"], mention["end"])] = len(
                    entities
                )
                entities.append(
                    ExtractedEntity(
                        chunk_id=chunk_id,
                        label=label,
                        text=mention["text"],
                        char_start=mention["start"],
                        char_end=mention["end"],
                    )
                )

        relations: list[ExtractedRelation] = []
        for label, pairs in raw_relations.items():
            for pair in pairs:
                head, tail = pair["head"], pair["tail"]
                source_key = (head["text"], head["start"], head["end"])
                target_key = (tail["text"], tail["start"], tail["end"])
                if source_key in span_index and target_key in span_index:
                    relations.append(
                        ExtractedRelation(
                            chunk_id=chunk_id,
                            label=label,
                            source_index=span_index[source_key],
                            target_index=span_index[target_key],
                        )
                    )
        return ExtractionResult(
            entities=entities, relations=relations, extractor_name="gliner"
        )


class BAMLExtractor(Extractor):
    """Extracts with an LLM, via a BAML function and a runtime ClientRegistry."""

    def __init__(
        self,
        *,
        settings: "ExtractionLLMSettings | None" = None,
        client: object | None = None,
    ) -> None:
        """Create an extractor from settings or an already-built BAML client.

        Args:
            settings: LLM client config. Defaults to ``ExtractionLLMSettings()``,
                loaded from the environment/``.env``.
            client: An already-built BAML client object exposing
                ``ExtractEntitiesAndRelations``. Tests inject a fake here.
        """
        self.settings = settings
        self._client = client

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Extract with an LLM call through the configured ClientRegistry.

        Raises:
            ExtractorMissingExtraError: The ``llm`` package extra is not
                installed.
            ValueError: ``chunk.id`` is ``None``.
        """
        if chunk.id is None:
            raise ValueError("Chunk must have an id for extraction.")
        if self._client is not None:
            client = self._client
            baml_options: dict = {}
        else:
            from agrag.llm.client_registry import build_client_registry  # noqa: PLC0415

            client = self._default_client()
            settings = self.settings or ExtractionLLMSettings()
            registry = build_client_registry(
                settings.clients, strategy=settings.strategy, retry=settings.retry
            )
            baml_options = {"client_registry": registry}
        type_builder = self._type_builder_for(schema)
        call_options: dict = {**baml_options}
        if type_builder is not None:
            call_options["tb"] = type_builder
        raw = await client.ExtractEntitiesAndRelations(  # ty: ignore[unresolved-attribute]
            chunk.text, call_options
        )
        return _normalize_extraction_result(self._to_result(raw, chunk), schema)

    def _default_client(self) -> object:
        """Return the default generated BAML client."""
        try:
            from agrag.llm.baml_client import b  # noqa: PLC0415
        except ImportError as exc:
            raise ExtractorMissingExtraError("BAMLExtractor", "llm") from exc
        return b

    def _type_builder_for(self, schema: GraphSchema) -> object | None:
        """Return a TypeBuilder populated with schema's labels and guidance.

        Each value's ``description`` is attached to its enum value, so it
        reaches the model as extraction guidance instead of being dropped.

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
        for relation_type in schema.relations:
            builder.ExtractedRelationLabel.add_value(relation_type.label).description(
                relation_type.description
            )
        return builder

    def _to_result(self, raw: object, chunk: Chunk) -> ExtractionResult:
        """Return an ExtractionResult, matching relation text back to entities.

        BAML returns each relation's endpoints as text, not an index into
        ``raw.entities`` — this matches each one back by exact normalized text,
        first match wins. A chunk with the same surface text for two different
        entities is a known, minor ambiguity this introduces.

        Entities whose span the LLM got wrong — out of range, zero-length, or not
        matching ``chunk.text`` at that span — are dropped, along with any
        relation that references one by text. One malformed field is not reason
        to fail the whole chunk's extraction.
        """
        if chunk.id is None:
            raise ValueError("Chunk must have an id for extraction.")
        chunk_id = chunk.id
        valid_raw_entities = [
            entity
            for entity in raw.entities  # ty: ignore[unresolved-attribute]
            if self._has_valid_span(entity, chunk.text)
        ]
        entities = [
            ExtractedEntity(
                chunk_id=chunk_id,
                label=entity.label,
                text=entity.text,
                char_start=entity.char_start,
                char_end=entity.char_end,
            )
            for entity in valid_raw_entities
        ]
        text_index = {
            entity.text: index for index, entity in enumerate(valid_raw_entities)
        }
        relations = [
            ExtractedRelation(
                chunk_id=chunk_id,
                label=relation.label,
                source_index=text_index[relation.source_text],
                target_index=text_index[relation.target_text],
            )
            for relation in raw.relations  # ty: ignore[unresolved-attribute]
            if relation.source_text in text_index and relation.target_text in text_index
        ]
        return ExtractionResult(
            entities=entities, relations=relations, extractor_name="baml"
        )

    def _has_valid_span(self, entity: object, chunk_text: str) -> bool:
        """Return whether entity's span is in range and matches its own text."""
        start, end = entity.char_start, entity.char_end  # ty: ignore[unresolved-attribute]
        return (
            0 <= start < end <= len(chunk_text) and chunk_text[start:end] == entity.text  # ty: ignore[unresolved-attribute]
        )


class EscalatingExtractor(Extractor):
    """Runs a cheap primary extractor first, escalating per chunk when it's weak."""

    def __init__(
        self,
        primary: Extractor,
        escalate_to: Extractor,
        *,
        min_confidence: float = 0.5,
        min_chunk_words: int = 8,
    ) -> None:
        """Create an extractor that escalates from a primary to a stronger one.

        Args:
            primary: Runs first, for every chunk.
            escalate_to: Runs instead of, never in addition to, the primary's
                result, when escalation triggers. Merging both extractors'
                output would mean reconciling overlapping spans between them,
                which is what entity resolution is for, not extraction.
            min_confidence: Escalate when the primary's mean entity confidence
                falls below this, among entities that report a confidence.
            min_chunk_words: Below this word count, a zero-entity result from
                the primary is treated as plausibly correct, not a miss.
        """
        self.primary = primary
        self.escalate_to = escalate_to
        self.min_confidence = min_confidence
        self.min_chunk_words = min_chunk_words

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Extract with the primary extractor, escalating when it's weak.

        Returns escalate_to's result outright when escalation triggers, never
        a combination of both extractors' results.
        """
        result = await self.primary.extract(chunk, schema)
        if self._should_escalate(result, chunk):
            return await self.escalate_to.extract(chunk, schema)
        return result

    def _should_escalate(self, result: ExtractionResult, chunk: Chunk) -> bool:
        """Return whether result is weak enough to escalate.

        Args:
            result: The primary extractor's result for chunk.
            chunk: The chunk result came from, used for its word count.
        """
        if not result.entities and len(chunk.text.split()) >= self.min_chunk_words:
            return True
        confidences = [
            entity.confidence
            for entity in result.entities
            if entity.confidence is not None
        ]
        mean_confidence = sum(confidences) / len(confidences) if confidences else None
        return mean_confidence is not None and mean_confidence < self.min_confidence
