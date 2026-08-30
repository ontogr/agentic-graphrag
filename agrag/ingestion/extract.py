"""The Extractor interface: reads one Chunk and produces an ExtractionResult."""

import asyncio
import os
from abc import ABC, abstractmethod
from typing import Any, Literal

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
from agrag.llm.retry import NO_RETRY, call_with_retry
from agrag.loaders.corpus.errors import IngestionError


def _resolve_span(
    text: str,
    chunk_text: str,
    hint_start: int,
    hint_end: int,
    occurrences_by_text: dict[str, list[int]] | None = None,
) -> tuple[int, int] | None:
    """Return a verified (start, end) span for text within chunk_text, or None.

    Trusts (hint_start, hint_end) only when it already points at an exact
    occurrence of text. Extractors — GLiNER's own boundary predictions and,
    especially, an LLM counting characters by hand — can report an
    approximately right but off-by-a-few span. Rather than drop a real mention
    over that, this searches chunk_text for every occurrence of text and,
    when text is unique in the chunk, returns the one closest to hint_start
    so a near-miss offset gets corrected instead of discarding real
    provenance. When text repeats in the chunk, an off-by-few hint nearer
    the wrong duplicate would be relocated there and text-only relation
    resolution could bind the relation to that wrong occurrence before the
    genuine schema-compatible one, so repeated text requires an exact span;
    a malformed hint is treated as unrecoverable.

    Args:
        text: The mention text to locate.
        chunk_text: The chunk to search.
        hint_start: The extractor-reported start offset.
        hint_end: The extractor-reported end offset.
        occurrences_by_text: A cache of every occurrence of text already found
            in chunk_text, keyed by text. Callers resolving many spans against
            the same chunk should pass one dict and reuse it across calls, so
            repeated text is scanned once instead of once per mention.

    Returns:
        None when text is empty, does not occur in chunk_text at all, or
        occurs more than once but hint does not exactly match one occurrence
        — the caller should treat that as a fabricated or unrecoverable
        mention.
    """
    if not text:
        return None
    if (
        0 <= hint_start < hint_end <= len(chunk_text)
        and chunk_text[hint_start:hint_end] == text
    ):
        return hint_start, hint_end
    if occurrences_by_text is not None and text in occurrences_by_text:
        occurrences = occurrences_by_text[text]
    else:
        occurrences = []
        search_from = 0
        while (found := chunk_text.find(text, search_from)) != -1:
            occurrences.append(found)
            search_from = found + 1
        if occurrences_by_text is not None:
            occurrences_by_text[text] = occurrences
    if not occurrences:
        return None
    if len(occurrences) > 1:
        # ponytail: repeated surface text is ambiguous — an off-by-few hint
        # nearer the wrong duplicate would be relocated there and text-only
        # relation resolution can then bind the relation to that fabricated
        # occurrence before the genuine one. Require an exact span for
        # repeats; a malformed hint is dropped as unrecoverable.
        return None
    start = min(occurrences, key=lambda candidate: abs(candidate - hint_start))
    return start, start + len(text)


def _relation_patterns(schema: GraphSchema) -> dict[str, set[tuple[str, str]]]:
    """Return each relation label's set of allowed (source, target) label pairs.

    Args:
        schema: The schema whose relations declare endpoint-label ``patterns``.

    Returns:
        A map from relation label to the union of its declared patterns.
    """
    allowed: dict[str, set[tuple[str, str]]] = {}
    for relation_type in schema.relations:
        allowed.setdefault(relation_type.label, set()).update(relation_type.patterns)
    return allowed


def _resolve_relation_pair(
    relation: object,
    text_index: dict[str, list[int]],
    valid_raw_entities: list[tuple[Any, int, int]],
    allowed_pairs: dict[str, set[tuple[str, str]]],
) -> tuple[int, int] | None:
    """Return the single (source, target) index pair for one raw relation.

    BAML identifies endpoints only by surface text, so each endpoint's text
    may match several entities. Walk candidate source/target indices in order
    and return the first pair whose endpoint labels satisfy one of the
    relation's declared ``patterns``. Return None when the relation label is
    undeclared, an endpoint's text matches no entity, or every pairing
    self-references; callers drop such relations rather than raise.
    """
    source_candidates = text_index.get(relation.source_text, [])  # ty: ignore[unresolved-attribute]
    target_candidates = text_index.get(relation.target_text, [])  # ty: ignore[unresolved-attribute]
    patterns = allowed_pairs.get(relation.label)  # ty: ignore[unresolved-attribute]
    if patterns is None:
        return None
    for source_index in source_candidates:
        for target_index in target_candidates:
            if source_index == target_index:
                continue
            source_label = valid_raw_entities[source_index][0].label
            target_label = valid_raw_entities[target_index][0].label
            if (source_label, target_label) in patterns:
                return (source_index, target_index)
    return None


def _normalize_extraction_result(
    result: ExtractionResult, schema: GraphSchema
) -> ExtractionResult:
    """Drop entities and relations schema does not declare.

    An entity survives only when its label is a declared EntityType. A
    relation survives only when its label is a declared RelationType and the
    resolved (source label, target label) pair — checked against the
    surviving entities — is one of that type's ``patterns``; a relation
    pointing at a dropped entity is dropped too. Surviving relation indices
    are remapped to the filtered entity list.

    Args:
        result: The extractor's raw result, before schema validation.
        schema: The schema entities and relations are validated against.

    Returns:
        A new ExtractionResult holding only schema-declared entities and
        relations, with relation indices remapped to the filtered entities.
    """
    entity_labels = {entity_type.label for entity_type in schema.entities}
    valid_entities: list[ExtractedEntity] = []
    index_remap: dict[int, int] = {}
    for old_index, entity in enumerate(result.entities):
        if entity.label not in entity_labels:
            continue
        index_remap[old_index] = len(valid_entities)
        valid_entities.append(entity)

    allowed_pairs = _relation_patterns(schema)
    valid_relations: list[ExtractedRelation] = []
    for relation in result.relations:
        if (
            relation.source_index not in index_remap
            or relation.target_index not in index_remap
        ):
            continue
        new_source = index_remap[relation.source_index]
        new_target = index_remap[relation.target_index]
        pair = (valid_entities[new_source].label, valid_entities[new_target].label)
        if pair not in allowed_pairs.get(relation.label, set()):
            continue
        valid_relations.append(
            relation.model_copy(
                update={"source_index": new_source, "target_index": new_target}
            )
        )

    return ExtractionResult(
        entities=valid_entities,
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
        self._load_task: asyncio.Task[object] | None = None

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
        return _normalize_extraction_result(self._to_result(raw, chunk, schema), schema)

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

    def _to_result(
        self, raw: object, chunk: Chunk, schema: GraphSchema
    ) -> ExtractionResult:
        """Return an ExtractionResult built from gliner2's raw output.

        Called with ``include_spans=True``, GLiNER2.5's extract() returns a dict
        with ``entities`` (label -> list of ``{"text", "start", "end"}`` mention
        dicts) and ``relation_extraction`` (label -> list of ``{"head", "tail"}``
        dicts, each endpoint shaped like a mention dict). Every reported span is
        verified against chunk.text via ``_resolve_span``: a mention whose text
        does not occur in chunk.text at all is dropped, an off-by-a-few span is
        corrected. Relation endpoints are matched back to entities by their
        resolved (text, start, end), not by text alone, so two mentions with
        identical surface text still resolve to their own entity. When the same
        span appears under multiple labels, all candidate indices are preserved
        and each relation is resolved to a distinct candidate pair compatible
        with its declared endpoint patterns. A relation whose endpoints both
        resolve to the same entity is dropped, not raised, so one malformed
        relation does not abort the whole chunk.
        """
        if chunk.id is None:
            raise ValueError("Chunk must have an id for extraction.")
        raw_dict: dict = raw  # ty: ignore[invalid-assignment]
        raw_entities: dict[str, list[dict]] = raw_dict.get("entities", {})
        raw_relations: dict[str, list[dict]] = raw_dict.get("relation_extraction", {})

        entities: list[ExtractedEntity] = []
        span_index: dict[tuple[str, int, int], list[int]] = {}
        chunk_id = chunk.id
        occurrences_by_text: dict[str, list[int]] = {}
        for label, mentions in raw_entities.items():
            for mention in mentions:
                span = _resolve_span(
                    mention["text"],
                    chunk.text,
                    mention["start"],
                    mention["end"],
                    occurrences_by_text,
                )
                if span is None:
                    continue
                start, end = span
                key = (mention["text"], start, end)
                span_index.setdefault(key, []).append(len(entities))
                entities.append(
                    ExtractedEntity(
                        chunk_id=chunk_id,
                        label=label,
                        text=mention["text"],
                        char_start=start,
                        char_end=end,
                    )
                )

        allowed_pairs = _relation_patterns(schema)
        relations: list[ExtractedRelation] = []
        for label, pairs in raw_relations.items():
            patterns = allowed_pairs.get(label)
            if patterns is None:
                continue
            for pair in pairs:
                head, tail = pair["head"], pair["tail"]
                source_span = _resolve_span(
                    head["text"],
                    chunk.text,
                    head["start"],
                    head["end"],
                    occurrences_by_text,
                )
                target_span = _resolve_span(
                    tail["text"],
                    chunk.text,
                    tail["start"],
                    tail["end"],
                    occurrences_by_text,
                )
                if source_span is None or target_span is None:
                    continue
                source_key = (head["text"], *source_span)
                target_key = (tail["text"], *target_span)
                source_candidates = span_index.get(source_key, [])
                target_candidates = span_index.get(target_key, [])
                match = next(
                    (
                        (si, ti)
                        for si in source_candidates
                        for ti in target_candidates
                        if si != ti
                        and (entities[si].label, entities[ti].label) in patterns
                    ),
                    None,
                )
                if match is not None:
                    si, ti = match
                    relations.append(
                        ExtractedRelation(
                            chunk_id=chunk_id,
                            label=label,
                            source_index=si,
                            target_index=ti,
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
                loaded from the environment/``.env``. Ignored when ``client``
                is given: an injected client also disables ``settings.retry``,
                since a caller building its own client is assumed to own its
                own retry behavior too.
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
            retry = NO_RETRY
        else:
            from agrag.llm.client_registry import build_client_registry  # noqa: PLC0415

            client = self._default_client()
            settings = self.settings or ExtractionLLMSettings()
            registry = build_client_registry(
                settings.clients, strategy=settings.strategy
            )
            baml_options = {"client_registry": registry}
            retry = settings.retry
        type_builder = self._type_builder_for(schema)
        call_options: dict = {**baml_options}
        if type_builder is not None:
            call_options["tb"] = type_builder
        # ponytail: retries every exception except the BAML error types
        # call_with_retry recognizes as permanently unretryable (an invalid
        # argument or a non-429 4xx); narrow further if that proves noisy.
        raw = await call_with_retry(
            lambda: client.ExtractEntitiesAndRelations(  # ty: ignore[unresolved-attribute]
                chunk.text, call_options
            ),
            retry,
        )
        return _normalize_extraction_result(self._to_result(raw, chunk, schema), schema)

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

    def _to_result(
        self, raw: object, chunk: Chunk, schema: GraphSchema
    ) -> ExtractionResult:
        """Return an ExtractionResult, matching relation text back to entities.

        BAML returns each relation's endpoints as text, not an index into
        ``raw.entities``, so duplicate surface text is inherently ambiguous:
        every entity sharing an endpoint's text is a candidate for that
        endpoint. Each raw relation yields at most one (source, target)
        pair: the first candidate pairing whose endpoint labels satisfy one
        of the relation's declared ``patterns``. Candidate pairings are
        walked in index order, so a pairing whose labels the schema forbids
        is skipped in favor of a later matching one — but once a
        schema-valid pairing is found, the search for that relation stops
        instead of emitting every compatible combination. An undeclared
        relation label, an endpoint whose text matches no entity, or a
        relation that collapses to a single entity (self-reference) yields
        no pair and is dropped, not raised, so one bad relation does not
        fail the whole chunk.

        Every entity's span is verified against chunk.text via
        ``_resolve_span``: an LLM-invented span (its text doesn't occur in
        chunk.text at all) is dropped, along with any relation referencing it
        by text; a merely miscounted span is corrected instead of dropped.
        A second entity with the same label, text, and resolved span is
        dropped as a true duplicate. Two entities with different labels on
        the same span (e.g. "Apple" as both Product and Organization) are
        both kept, so relations that need the second label survive.
        """
        if chunk.id is None:
            raise ValueError("Chunk must have an id for extraction.")
        chunk_id = chunk.id
        occurrences_by_text: dict[str, list[int]] = {}
        seen_spans: set[tuple[str, str, int, int]] = set()
        valid_raw_entities: list[tuple[Any, int, int]] = []
        for entity in raw.entities:  # ty: ignore[unresolved-attribute]
            span = _resolve_span(
                entity.text,
                chunk.text,
                entity.char_start,
                entity.char_end,
                occurrences_by_text,
            )
            if span is None:
                continue
            dedup_key = (entity.label, entity.text, span[0], span[1])
            if dedup_key not in seen_spans:
                seen_spans.add(dedup_key)
                valid_raw_entities.append((entity, *span))
        entities = [
            ExtractedEntity(
                chunk_id=chunk_id,
                label=entity.label,
                text=entity.text,
                char_start=start,
                char_end=end,
            )
            for entity, start, end in valid_raw_entities
        ]
        text_index: dict[str, list[int]] = {}
        for index, (entity, _, _) in enumerate(valid_raw_entities):
            text_index.setdefault(entity.text, []).append(index)

        allowed_pairs = _relation_patterns(schema)
        relations: list[ExtractedRelation] = []
        seen_pairs: set[tuple[int, int, str]] = set()
        for relation in raw.relations:  # ty: ignore[unresolved-attribute]
            chosen = _resolve_relation_pair(
                relation, text_index, valid_raw_entities, allowed_pairs
            )
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
