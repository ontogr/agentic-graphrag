"""Tests for the Extractor implementations and ExtractorMissingExtraError."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import (
    GENERIC,
    EntityType,
    GraphSchema,
    RelationType,
)
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion.extract import (
    BAMLExtractor,
    EscalatingExtractor,
    ExtractionLLMSettings,
    ExtractorMissingExtraError,
    GlinerExtractor,
)
from agrag.llm.client_config import LLMClientConfig, RetryConfig
from agrag.loaders.corpus.errors import IngestionError


_DOC_ID = uuid4()

# A schema that permits only a Person -> Organization WORKS_AT relation, used to
# test that normalization drops relations with the wrong label or endpoint pair.
_ONE_PAIR_SCHEMA = GraphSchema(
    name="one-pair",
    version="1",
    entities=[
        EntityType(label="Person", description="A named individual."),
        EntityType(label="Organization", description="A company or institution."),
    ],
    relations=[
        RelationType(
            label="WORKS_AT",
            description="A person works at an organization.",
            patterns=[("Person", "Organization")],
        )
    ],
)

# Schema where the same text can have two valid labels (e.g. "Apple" as both
# Product and Organization), with a relation valid only for the second label.
_MULTI_LABEL_SCHEMA = GraphSchema(
    name="multi-label",
    version="1",
    entities=[
        EntityType(label="Product", description="A product."),
        EntityType(label="Organization", description="A company."),
    ],
    relations=[
        RelationType(
            label="SELLS",
            description="An org sells a product.",
            patterns=[("Organization", "Product")],
        ),
    ],
)


def _chunk(
    text: str = "Ada Lovelace worked at the Analytical Engine Company.",
) -> Chunk:
    """Build a minimal Chunk for extraction tests."""
    return Chunk(
        document_id=_DOC_ID,
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )


class TestExtractorMissingExtraError:
    """ExtractorMissingExtraError carries component and extra name."""

    def test_message_includes_install_command(self) -> None:
        """The error message tells the user which extra to install."""
        err = ExtractorMissingExtraError("GlinerExtractor", "extract")
        assert "GlinerExtractor" in str(err)
        assert "extract" in str(err)
        assert "pip install" in str(err)

    def test_attributes_are_set(self) -> None:
        """Component and extra are stored as attributes."""
        err = ExtractorMissingExtraError("BAMLExtractor", "llm")
        assert err.component == "BAMLExtractor"
        assert err.extra == "llm"

    def test_inherits_ingestion_error(self) -> None:
        """ExtractorMissingExtraError is a subclass of IngestionError."""
        assert issubclass(ExtractorMissingExtraError, IngestionError)


class TestGlinerExtractor:
    """GlinerExtractor raises when gliner2 is not installed."""

    async def test_extract_maps_model_output_and_schema(self) -> None:
        """Injected model output becomes indexed entities and relations."""

        class FakeSchemaBuilder:
            def __init__(self) -> None:
                self.entity_descriptions: dict[str, str] = {}
                self.relation_descriptions: dict[str, str] = {}

            def entities(self, descriptions: dict[str, str]) -> "FakeSchemaBuilder":
                self.entity_descriptions = descriptions
                return self

            def relations(self, descriptions: dict[str, str]) -> "FakeSchemaBuilder":
                self.relation_descriptions = descriptions
                return self

        class FakeModel:
            def __init__(self) -> None:
                self.schema = FakeSchemaBuilder()

            def create_schema(self) -> FakeSchemaBuilder:
                return self.schema

            def extract(
                self, text: str, schema: FakeSchemaBuilder, include_spans: bool = False
            ) -> dict:
                assert text.startswith("Ada Lovelace")
                assert schema is self.schema
                assert include_spans is True
                return {
                    "entities": {
                        "Person": [{"text": "Ada Lovelace", "start": 0, "end": 12}],
                        "Organization": [
                            {
                                "text": "Analytical Engine Company",
                                "start": 27,
                                "end": 53,
                            }
                        ],
                    },
                    "relation_extraction": {
                        "RELATED_TO": [
                            {
                                "head": {
                                    "text": "Ada Lovelace",
                                    "start": 0,
                                    "end": 12,
                                },
                                "tail": {
                                    "text": "Analytical Engine Company",
                                    "start": 27,
                                    "end": 53,
                                },
                            }
                        ]
                    },
                }

        model = FakeModel()
        result = await GlinerExtractor(model=model).extract(_chunk(), GENERIC)

        assert model.schema.entity_descriptions == {
            item.label: item.description for item in GENERIC.entities
        }
        assert model.schema.relation_descriptions == {
            item.label: item.description for item in GENERIC.relations
        }
        assert [(entity.text, entity.char_start) for entity in result.entities] == [
            ("Ada Lovelace", 0),
            ("Analytical Engine Company", 27),
        ]
        assert result.relations[0].source_index == 0
        assert result.relations[0].target_index == 1
        assert result.extractor_name == "gliner"

    async def test_extract_disambiguates_duplicate_mention_text(self) -> None:
        """Two mentions with identical text resolve to their own entity index."""

        class FakeModel:
            def create_schema(self) -> "FakeModel":
                return self

            def entities(self, labels: list[str]) -> "FakeModel":
                return self

            def relations(self, labels: list[str]) -> "FakeModel":
                return self

            def extract(self, text: str, schema: object, include_spans=False) -> dict:
                return {
                    "entities": {
                        "Person": [
                            {"text": "Ada", "start": 0, "end": 3},
                            {"text": "Ada", "start": 27, "end": 30},
                        ],
                        "Organization": [{"text": "Acme", "start": 15, "end": 19}],
                    },
                    "relation_extraction": {
                        "WORKS_AT": [
                            {
                                "head": {"text": "Ada", "start": 27, "end": 30},
                                "tail": {"text": "Acme", "start": 15, "end": 19},
                            }
                        ]
                    },
                }

        chunk = _chunk("Ada met Bob at Acme; later Ada left.")
        assert chunk.text.index("Ada", 1) == 27
        assert chunk.text.index("Acme") == 15
        result = await GlinerExtractor(model=FakeModel()).extract(
            chunk, _ONE_PAIR_SCHEMA
        )

        assert len(result.entities) == 3
        assert len(result.relations) == 1
        # The relation must target the second "Ada" mention (index 1), not the first.
        assert result.relations[0].source_index == 1
        assert result.relations[0].target_index == 2

    async def test_extract_drops_relations_the_schema_does_not_permit(self) -> None:
        """A relation whose endpoint labels the schema forbids is dropped."""

        class FakeModel:
            def create_schema(self) -> "FakeModel":
                return self

            def entities(self, labels: list[str]) -> "FakeModel":
                return self

            def relations(self, labels: list[str]) -> "FakeModel":
                return self

            def extract(self, text: str, schema: object, include_spans=False) -> dict:
                return {
                    "entities": {
                        "Person": [{"text": "Ada", "start": 0, "end": 3}],
                        "Organization": [{"text": "Acme", "start": 13, "end": 17}],
                    },
                    "relation_extraction": {
                        # Reversed: Organization -> Person is not a declared pattern.
                        "WORKS_AT": [
                            {
                                "head": {"text": "Acme", "start": 13, "end": 17},
                                "tail": {"text": "Ada", "start": 0, "end": 3},
                            }
                        ]
                    },
                }

        result = await GlinerExtractor(model=FakeModel()).extract(
            _chunk("Ada works at Acme."), _ONE_PAIR_SCHEMA
        )
        assert len(result.entities) == 2
        assert result.relations == []

    async def test_extract_drops_self_referencing_relation(self) -> None:
        """A relation whose head and tail resolve to the same entity is dropped.

        A malformed relation naming the same mention as both endpoints must
        not abort the whole chunk: ExtractedRelation rejects a self-reference
        outright, so _to_result has to catch it first.
        """

        class FakeModel:
            def create_schema(self) -> "FakeModel":
                return self

            def entities(self, labels: list[str]) -> "FakeModel":
                return self

            def relations(self, labels: list[str]) -> "FakeModel":
                return self

            def extract(self, text: str, schema: object, include_spans=False) -> dict:
                return {
                    "entities": {
                        "Person": [{"text": "Ada", "start": 0, "end": 3}],
                    },
                    "relation_extraction": {
                        "RELATED_TO": [
                            {
                                "head": {"text": "Ada", "start": 0, "end": 3},
                                "tail": {"text": "Ada", "start": 0, "end": 3},
                            }
                        ]
                    },
                }

        result = await GlinerExtractor(model=FakeModel()).extract(_chunk(), GENERIC)

        assert len(result.entities) == 1
        assert result.relations == []

    async def test_extract_drops_relation_with_undeclared_label(self) -> None:
        """A relation label the schema never declares is dropped."""

        class FakeModel:
            def create_schema(self) -> "FakeModel":
                return self

            def entities(self, labels: list[str]) -> "FakeModel":
                return self

            def relations(self, labels: list[str]) -> "FakeModel":
                return self

            def extract(self, text: str, schema: object, include_spans=False) -> dict:
                return {
                    "entities": {
                        "Person": [{"text": "Ada", "start": 0, "end": 3}],
                        "Organization": [{"text": "Acme", "start": 13, "end": 17}],
                    },
                    "relation_extraction": {
                        # Correct Person -> Organization pair, but the schema
                        # never declares a FOUNDED relation type at all.
                        "FOUNDED": [
                            {
                                "head": {"text": "Ada", "start": 0, "end": 3},
                                "tail": {"text": "Acme", "start": 13, "end": 17},
                            }
                        ]
                    },
                }

        result = await GlinerExtractor(model=FakeModel()).extract(
            _chunk("Ada works at Acme."), _ONE_PAIR_SCHEMA
        )
        assert len(result.entities) == 2
        assert result.relations == []

    async def test_extract_unions_patterns_for_a_relation_label_declared_twice(
        self,
    ) -> None:
        """A relation label declared twice keeps patterns from every declaration.

        Nothing stops a GraphSchema from repeating a relation label with a
        different pattern each time. Normalization must union the patterns
        across every declaration, not keep only the last one.
        """
        schema = GraphSchema(
            name="repeated-label",
            version="1",
            entities=[
                EntityType(label="Person", description="A named individual."),
                EntityType(
                    label="Organization", description="A company or institution."
                ),
                EntityType(label="Product", description="A thing an org makes."),
            ],
            relations=[
                RelationType(
                    label="WORKS_AT",
                    description="A person works at an organization.",
                    patterns=[("Person", "Organization")],
                ),
                RelationType(
                    label="WORKS_AT",
                    description="A person works on a product.",
                    patterns=[("Person", "Product")],
                ),
            ],
        )

        class FakeModel:
            def create_schema(self) -> "FakeModel":
                return self

            def entities(self, labels: list[str]) -> "FakeModel":
                return self

            def relations(self, labels: list[str]) -> "FakeModel":
                return self

            def extract(self, text: str, schema: object, include_spans=False) -> dict:
                return {
                    "entities": {
                        "Person": [{"text": "Ada", "start": 0, "end": 3}],
                        "Organization": [{"text": "Acme", "start": 13, "end": 17}],
                    },
                    "relation_extraction": {
                        "WORKS_AT": [
                            {
                                "head": {"text": "Ada", "start": 0, "end": 3},
                                "tail": {"text": "Acme", "start": 13, "end": 17},
                            }
                        ]
                    },
                }

        result = await GlinerExtractor(model=FakeModel()).extract(
            _chunk("Ada works at Acme."), schema
        )
        assert len(result.relations) == 1

    async def test_extract_drops_undeclared_entity_and_remaps_relation_indices(
        self,
    ) -> None:
        """An entity with an undeclared label is dropped; relation indices remap."""

        class FakeModel:
            def create_schema(self) -> "FakeModel":
                return self

            def entities(self, labels: list[str]) -> "FakeModel":
                return self

            def relations(self, labels: list[str]) -> "FakeModel":
                return self

            def extract(self, text: str, schema: object, include_spans=False) -> dict:
                return {
                    "entities": {
                        "Person": [{"text": "Ada", "start": 0, "end": 3}],
                        # Animal is not declared in _ONE_PAIR_SCHEMA at all.
                        "Animal": [{"text": "Rex", "start": 4, "end": 7}],
                        "Organization": [{"text": "Acme", "start": 17, "end": 21}],
                    },
                    "relation_extraction": {
                        "WORKS_AT": [
                            {
                                "head": {"text": "Ada", "start": 0, "end": 3},
                                "tail": {"text": "Acme", "start": 17, "end": 21},
                            }
                        ]
                    },
                }

        chunk = _chunk("Ada Rex works at Acme.")
        result = await GlinerExtractor(model=FakeModel()).extract(
            chunk, _ONE_PAIR_SCHEMA
        )

        assert [entity.text for entity in result.entities] == ["Ada", "Acme"]
        assert len(result.relations) == 1
        # Acme was originally index 2; after Rex (index 1) is dropped, it must
        # be remapped to index 1, not left pointing at the old index.
        assert result.relations[0].source_index == 0
        assert result.relations[0].target_index == 1

    def test_raises_when_gliner2_not_importable(self) -> None:
        """ExtractorMissingExtraError is raised if gliner2 can't be imported."""
        extractor = GlinerExtractor()
        with patch.dict("sys.modules", {"gliner2": None}):
            with pytest.raises(ExtractorMissingExtraError) as exc_info:
                extractor._ensure_model()
            assert exc_info.value.extra == "extract"

    def test_uses_injected_model_when_provided(self) -> None:
        """An injected model skips the import and loading entirely."""
        fake_model = SimpleNamespace()
        extractor = GlinerExtractor(model=fake_model)
        assert extractor._ensure_model() is fake_model

    async def test_concurrent_extract_loads_model_once(self) -> None:
        """Concurrent first calls to extract() load the model exactly once."""

        class FakeSchemaBuilder:
            def entities(self, labels: list[str]) -> "FakeSchemaBuilder":
                return self

            def relations(self, labels: list[str]) -> "FakeSchemaBuilder":
                return self

        class FakeModel:
            def create_schema(self) -> FakeSchemaBuilder:
                return FakeSchemaBuilder()

            def extract(self, text: str, schema: object, include_spans=False) -> dict:
                return {"entities": {}, "relation_extraction": {}}

        extractor = GlinerExtractor(model_name="fake")
        load_started = threading.Event()
        release_load = threading.Event()
        load_calls: list[int] = []

        def blocking_ensure_model() -> object:
            load_calls.append(1)
            load_started.set()
            assert release_load.wait(timeout=5), "test deadlocked"
            extractor._model = FakeModel()
            return extractor._model

        extractor._ensure_model = blocking_ensure_model

        task_one = asyncio.create_task(extractor.extract(_chunk(), GENERIC))
        await asyncio.to_thread(load_started.wait, 5)
        task_two = asyncio.create_task(extractor.extract(_chunk(), GENERIC))
        await asyncio.sleep(0.05)
        release_load.set()
        result_one, result_two = await asyncio.gather(task_one, task_two)

        assert load_calls == [1]
        assert result_one.extractor_name == "gliner"
        assert result_two.extractor_name == "gliner"

    async def test_cancelled_waiter_does_not_duplicate_the_model_load(self) -> None:
        """A cancelled first waiter does not stop the load or start a second one."""

        class FakeSchemaBuilder:
            def entities(self, labels: list[str]) -> "FakeSchemaBuilder":
                return self

            def relations(self, labels: list[str]) -> "FakeSchemaBuilder":
                return self

        class FakeModel:
            def create_schema(self) -> FakeSchemaBuilder:
                return FakeSchemaBuilder()

            def extract(self, text: str, schema: object, include_spans=False) -> dict:
                return {"entities": {}, "relation_extraction": {}}

        extractor = GlinerExtractor(model_name="fake")
        load_started = threading.Event()
        release_load = threading.Event()
        load_calls: list[int] = []

        def blocking_ensure_model() -> object:
            load_calls.append(1)
            load_started.set()
            assert release_load.wait(timeout=5), "test deadlocked"
            extractor._model = FakeModel()
            return extractor._model

        extractor._ensure_model = blocking_ensure_model

        task_one = asyncio.create_task(extractor.extract(_chunk(), GENERIC))
        await asyncio.to_thread(load_started.wait, 5)

        task_one.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task_one

        # A second extraction, arriving while the cancelled waiter's load is
        # still blocked, must reuse that same in-flight load instead of
        # starting a new one.
        task_two = asyncio.create_task(extractor.extract(_chunk(), GENERIC))
        await asyncio.sleep(0.05)
        release_load.set()
        result_two = await task_two

        assert load_calls == [1]
        assert result_two.extractor_name == "gliner"


class TestBAMLExtractor:
    """BAMLExtractor raises when the llm extra is not installed."""

    def test_raises_when_baml_client_not_importable(self) -> None:
        """ExtractorMissingExtraError is raised if baml_client can't be imported."""
        extractor = BAMLExtractor.__new__(BAMLExtractor)
        extractor._client = None
        extractor.settings = None
        with patch.dict("sys.modules", {"agrag.llm.baml_client": None}):
            with pytest.raises(ExtractorMissingExtraError) as exc_info:
                extractor._default_client()
            assert exc_info.value.extra == "llm"

    async def test_to_result_maps_source_text_to_indices(self) -> None:
        """BAML output relations are mapped to entity indices by text."""
        chunk = _chunk()
        org_text = "the Analytical Engine Company"
        org_start = chunk.text.index(org_text)
        # Simulate BAML raw output
        entities_raw = [
            SimpleNamespace(label="Person", text="Ada", char_start=0, char_end=3),
            SimpleNamespace(
                label="Organization",
                text=org_text,
                char_start=org_start,
                char_end=org_start + len(org_text),
            ),
        ]
        relations_raw = [
            SimpleNamespace(
                label="WORKS_AT",
                source_text="Ada",
                target_text="the Analytical Engine Company",
            )
        ]
        raw = SimpleNamespace(entities=entities_raw, relations=relations_raw)

        extractor = BAMLExtractor.__new__(BAMLExtractor)
        result = extractor._to_result(raw, chunk)

        assert len(result.entities) == 2
        assert result.entities[0].text == "Ada"
        assert result.entities[1].text == "the Analytical Engine Company"
        assert len(result.relations) == 1
        assert result.relations[0].source_index == 0
        assert result.relations[0].target_index == 1
        assert result.relations[0].label == "WORKS_AT"
        assert result.extractor_name == "baml"

    async def test_to_result_skips_relations_with_unknown_text(self) -> None:
        """Relations whose text doesn't match any entity are dropped."""
        chunk = _chunk()
        entities_raw = [
            SimpleNamespace(label="Person", text="Ada", char_start=0, char_end=3),
        ]
        relations_raw = [
            SimpleNamespace(
                label="WORKS_AT",
                source_text="Ada",
                target_text="Nonexistent Corp",
            )
        ]
        raw = SimpleNamespace(entities=entities_raw, relations=relations_raw)

        extractor = BAMLExtractor.__new__(BAMLExtractor)
        result = extractor._to_result(raw, chunk)

        assert len(result.entities) == 1
        assert len(result.relations) == 0

    async def test_to_result_resolves_self_referencing_relation_between_duplicates(
        self,
    ) -> None:
        """A relation whose source and target text match resolves to two entities.

        BAML relations carry no entity identity beyond surface text, so a
        relation between two distinct people who share a name (or the model
        double-counting one) reports the same text for both endpoints. The
        old text-only-keyed lookup mapped both endpoints to one index, and
        ExtractedRelation raised on the self-reference, aborting the whole
        chunk. This must instead resolve the two distinct mentions.
        """
        chunk = _chunk("Ada met Bob; later Ada left.")
        second_ada_start = chunk.text.index("Ada", 1)
        entities_raw = [
            SimpleNamespace(label="Person", text="Ada", char_start=0, char_end=3),
            SimpleNamespace(
                label="Person",
                text="Ada",
                char_start=second_ada_start,
                char_end=second_ada_start + 3,
            ),
        ]
        relations_raw = [
            SimpleNamespace(label="KNOWS", source_text="Ada", target_text="Ada"),
        ]
        raw = SimpleNamespace(entities=entities_raw, relations=relations_raw)

        extractor = BAMLExtractor.__new__(BAMLExtractor)
        result = extractor._to_result(raw, chunk)

        # Both directions survive: (0->1) and (1->0). Normalization filters
        # only by schema pattern, so symmetric KNOWS keeps both.
        assert len(result.relations) == 2
        for relation in result.relations:
            assert relation.source_index != relation.target_index
            assert {relation.source_index, relation.target_index} == {0, 1}

    async def test_to_result_drops_self_referencing_relation_with_one_candidate(
        self,
    ) -> None:
        """A self-referencing relation with only one matching entity is dropped.

        With a single "Ada" entity, a relation naming "Ada" on both sides has
        no distinct pairing available. Dropping it, not raising, keeps the
        rest of the chunk's entities and relations intact.
        """
        chunk = _chunk()
        entities_raw = [
            SimpleNamespace(label="Person", text="Ada", char_start=0, char_end=3),
        ]
        relations_raw = [
            SimpleNamespace(label="KNOWS", source_text="Ada", target_text="Ada"),
        ]
        raw = SimpleNamespace(entities=entities_raw, relations=relations_raw)

        extractor = BAMLExtractor.__new__(BAMLExtractor)
        result = extractor._to_result(raw, chunk)

        assert len(result.entities) == 1
        assert result.relations == []

    async def test_to_result_drops_duplicate_entity_resolving_to_a_claimed_span(
        self,
    ) -> None:
        """A malformed duplicate that resolves onto an already-claimed span is dropped.

        Two raw entities can share text with only one real occurrence in the
        chunk: a correct one, and a malformed one whose hint offsets are
        wrong but whose text still exists exactly once. Without deduping,
        both would resolve to the same (text, span) and survive as separate
        entities, and a same-text relation could then be fabricated between
        what is really one entity.
        """
        chunk = _chunk()
        entities_raw = [
            SimpleNamespace(label="Person", text="Ada", char_start=0, char_end=3),
            SimpleNamespace(label="Person", text="Ada", char_start=500, char_end=503),
        ]
        relations_raw = [
            SimpleNamespace(label="KNOWS", source_text="Ada", target_text="Ada"),
        ]
        raw = SimpleNamespace(entities=entities_raw, relations=relations_raw)

        extractor = BAMLExtractor.__new__(BAMLExtractor)
        result = extractor._to_result(raw, chunk)

        assert len(result.entities) == 1
        assert result.relations == []

    async def test_extract_keeps_entity_with_corrected_span(self) -> None:
        """A wrong-but-recoverable span is corrected, not dropped.

        LLMs are unreliable at counting characters; a span this far off (but
        whose text genuinely occurs in the chunk) is a miscount, not a
        fabrication, so the mention is kept with its real span.
        """
        chunk = _chunk()

        class FakeClient:
            async def ExtractEntitiesAndRelations(self, *args):  # noqa: N802
                return SimpleNamespace(
                    entities=[
                        SimpleNamespace(
                            label="Person", text="Ada", char_start=0, char_end=1000
                        ),
                    ],
                    relations=[],
                )

        extractor = BAMLExtractor(client=FakeClient())
        result = await extractor.extract(chunk, GENERIC)

        assert len(result.entities) == 1
        assert result.entities[0].text == "Ada"
        assert result.entities[0].char_start == 0
        assert result.entities[0].char_end == 3

    async def test_extract_drops_entity_with_hallucinated_text(self) -> None:
        """An entity whose text never occurs in chunk.text is dropped."""
        chunk = _chunk()

        class FakeClient:
            async def ExtractEntitiesAndRelations(self, *args):  # noqa: N802
                return SimpleNamespace(
                    entities=[
                        SimpleNamespace(
                            label="Person", text="Ada", char_start=0, char_end=3
                        ),
                        SimpleNamespace(
                            label="Person", text="Ghost", char_start=0, char_end=5
                        ),
                    ],
                    relations=[],
                )

        extractor = BAMLExtractor(client=FakeClient())
        result = await extractor.extract(chunk, GENERIC)

        assert [entity.text for entity in result.entities] == ["Ada"]

    async def test_extract_drops_entity_with_zero_length_span(self) -> None:
        """A zero-length span is dropped before it reaches ExtractedEntity."""

        class FakeClient:
            async def ExtractEntitiesAndRelations(self, *args):  # noqa: N802
                return SimpleNamespace(
                    entities=[
                        SimpleNamespace(
                            label="Person", text="Ada", char_start=0, char_end=3
                        ),
                        SimpleNamespace(
                            label="Person", text="", char_start=5, char_end=5
                        ),
                    ],
                    relations=[],
                )

        extractor = BAMLExtractor(client=FakeClient())
        result = await extractor.extract(_chunk(), GENERIC)

        assert [entity.text for entity in result.entities] == ["Ada"]

    async def test_to_result_keeps_distinct_labels_on_same_span(self) -> None:
        """Two valid labels on one span are kept, preserving the second's relations.

        When the LLM extracts "Apple" as both Product and Organization at the
        same character span, the old dedup (keyed only on span) would drop the
        second entity. A SELLS relation (Organization -> Product) that needs
        the Organization entity then had no target and disappeared.
        """
        chunk = _chunk("Apple released the iPhone.")
        apple_start = chunk.text.index("Apple")
        entities_raw = [
            SimpleNamespace(
                label="Product",
                text="Apple",
                char_start=apple_start,
                char_end=apple_start + 5,
            ),
            SimpleNamespace(
                label="Organization",
                text="Apple",
                char_start=apple_start,
                char_end=apple_start + 5,
            ),
        ]
        relations_raw = [
            SimpleNamespace(
                label="SELLS",
                source_text="Apple",
                target_text="iPhone",
            ),
        ]
        raw = SimpleNamespace(entities=entities_raw, relations=relations_raw)

        extractor = BAMLExtractor.__new__(BAMLExtractor)
        result = extractor._to_result(raw, chunk)

        # Both labels survive despite sharing a span.
        assert len(result.entities) == 2
        labels = {entity.label for entity in result.entities}
        assert labels == {"Product", "Organization"}

    async def test_extract_preserves_relation_needing_second_label(self) -> None:
        """A relation valid only for the second label survives extraction.

        Regression test for the dedup bug: seen_spans was keyed on
        (start, end) only, so "Apple" as Organization was dropped when
        "Apple" as Product appeared first. With both labels surviving and
        all pairings emitted, normalization selects the (Organization,
        Product) pairing that matches the SELLS pattern.
        """
        chunk = _chunk("Apple released the iPhone.")
        apple_start = chunk.text.index("Apple")
        iphone_start = chunk.text.index("iPhone")

        class FakeClient:
            async def ExtractEntitiesAndRelations(self, *args):  # noqa: N802
                return SimpleNamespace(
                    entities=[
                        SimpleNamespace(
                            label="Product",
                            text="Apple",
                            char_start=apple_start,
                            char_end=apple_start + 5,
                        ),
                        SimpleNamespace(
                            label="Organization",
                            text="Apple",
                            char_start=apple_start,
                            char_end=apple_start + 5,
                        ),
                        SimpleNamespace(
                            label="Product",
                            text="iPhone",
                            char_start=iphone_start,
                            char_end=iphone_start + 6,
                        ),
                    ],
                    relations=[
                        SimpleNamespace(
                            label="SELLS",
                            source_text="Apple",
                            target_text="iPhone",
                        ),
                    ],
                )

        extractor = BAMLExtractor(client=FakeClient())
        result = await extractor.extract(chunk, _MULTI_LABEL_SCHEMA)

        assert len(result.entities) == 3
        labels = {entity.label for entity in result.entities}
        assert labels == {"Product", "Organization"}
        assert len(result.relations) == 1
        assert result.relations[0].label == "SELLS"

    async def test_extract_drops_relation_referencing_a_hallucinated_entity(
        self,
    ) -> None:
        """A relation to a hallucinated entity is dropped along with it."""

        class FakeClient:
            async def ExtractEntitiesAndRelations(self, *args):  # noqa: N802
                return SimpleNamespace(
                    entities=[
                        SimpleNamespace(
                            label="Person", text="Ada", char_start=0, char_end=3
                        ),
                        SimpleNamespace(
                            label="Organization",
                            text="Ghost Corp",
                            char_start=0,
                            char_end=10,
                        ),
                    ],
                    relations=[
                        SimpleNamespace(
                            label="WORKS_AT",
                            source_text="Ada",
                            target_text="Ghost Corp",
                        )
                    ],
                )

        extractor = BAMLExtractor(client=FakeClient())
        result = await extractor.extract(_chunk(), _ONE_PAIR_SCHEMA)

        assert [entity.text for entity in result.entities] == ["Ada"]
        assert result.relations == []

    async def test_extract_with_injected_client_skips_settings(self) -> None:
        """An injected client works without EXTRACTION_LLM_CLIENTS env vars."""

        class FakeClient:
            async def ExtractEntitiesAndRelations(self, *args):  # noqa: N802
                return SimpleNamespace(
                    entities=[
                        SimpleNamespace(
                            label="Person", text="Ada", char_start=0, char_end=3
                        )
                    ],
                    relations=[],
                )

        chunk = _chunk()
        extractor = BAMLExtractor(client=FakeClient())
        # No settings set — should not raise
        assert extractor.settings is None
        result = await extractor.extract(chunk, GENERIC)
        assert len(result.entities) == 1
        assert result.entities[0].text == "Ada"

    async def test_type_builder_output_format_permits_only_declared_labels(
        self,
    ) -> None:
        """The rendered prompt offers only a schema's labels, never PLACEHOLDER.

        Captures the TypeBuilder that extract() passes to the client, then
        renders the real BAML HTTP request with it (no network call) — proving
        the compiled runtime's behavior, not just BAMLExtractor's Python logic.
        """
        from agrag.llm.baml_client import b  # noqa: PLC0415

        captured: dict = {}

        class FakeClient:
            async def ExtractEntitiesAndRelations(self, text, call_options):  # noqa: N802
                captured["tb"] = call_options["tb"]
                return SimpleNamespace(entities=[], relations=[])

        extractor = BAMLExtractor(client=FakeClient())
        await extractor.extract(_chunk("Ada works at Acme."), _ONE_PAIR_SCHEMA)

        request = await b.request.ExtractEntitiesAndRelations(
            "Ada works at Acme.", {"tb": captured["tb"]}
        )
        prompt = "".join(
            block["text"]
            for message in request.body.json()["messages"]
            for block in message["content"]
        )

        assert "PLACEHOLDER" not in prompt
        assert "Person" in prompt
        assert "Organization" in prompt
        assert "WORKS_AT" in prompt
        assert _ONE_PAIR_SCHEMA.relations[0].description in prompt

    async def test_extract_drops_relations_the_schema_does_not_permit(self) -> None:
        """A relation whose endpoint labels the schema forbids is dropped."""

        class FakeClient:
            async def ExtractEntitiesAndRelations(self, *args):  # noqa: N802
                return SimpleNamespace(
                    entities=[
                        SimpleNamespace(
                            label="Person", text="Ada", char_start=0, char_end=3
                        ),
                        SimpleNamespace(
                            label="Organization",
                            text="Acme",
                            char_start=13,
                            char_end=17,
                        ),
                    ],
                    relations=[
                        # Reversed: Organization -> Person is not a declared pattern.
                        SimpleNamespace(
                            label="WORKS_AT", source_text="Acme", target_text="Ada"
                        )
                    ],
                )

        extractor = BAMLExtractor(client=FakeClient())
        result = await extractor.extract(_chunk("Ada works at Acme."), _ONE_PAIR_SCHEMA)
        assert len(result.entities) == 2
        assert result.relations == []

    async def test_extract_retries_a_transient_failure_per_settings_retry(
        self, monkeypatch
    ) -> None:
        """settings.retry drives real retry-with-backoff around the LLM call."""
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr("agrag.llm.retry.sleep", fake_sleep)
        monkeypatch.setattr(
            "agrag.llm.client_registry.build_client_registry",
            lambda clients, *, strategy: object(),
        )

        call_count = 0

        class FlakyClient:
            async def ExtractEntitiesAndRelations(self, *args):  # noqa: N802
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise RuntimeError("transient provider error")
                return SimpleNamespace(entities=[], relations=[])

        settings = ExtractionLLMSettings(
            clients=[LLMClientConfig(name="c", provider="openai", model="gpt-4o-mini")],
            retry=RetryConfig(max_retries=3, delay_ms=50, multiplier=2),
        )
        extractor = BAMLExtractor(settings=settings)
        monkeypatch.setattr(extractor, "_default_client", FlakyClient)

        result = await extractor.extract(_chunk(), GENERIC)

        assert call_count == 3
        assert sleeps == [0.05, 0.1]
        assert result.entities == []

    async def test_extract_with_non_default_env_retry_does_not_abort(
        self, monkeypatch
    ) -> None:
        """A non-default, env-backed RetryConfig no longer aborts extraction.

        Exercises the real (unmocked) build_client_registry — this used to
        raise for any non-default RetryConfig before BAML's static
        retry_policy syntax was replaced with Python-level retry.
        """
        monkeypatch.setenv(
            "EXTRACTION_LLM_CLIENTS",
            '[{"name": "c", "provider": "openai", "model": "gpt-4o-mini"}]',
        )
        monkeypatch.setenv("EXTRACTION_LLM_RETRY", '{"max_retries": 7}')
        settings = ExtractionLLMSettings()
        assert settings.retry.max_retries == 7

        class FakeClient:
            async def ExtractEntitiesAndRelations(self, *args):  # noqa: N802
                return SimpleNamespace(entities=[], relations=[])

        extractor = BAMLExtractor(settings=settings)
        monkeypatch.setattr(extractor, "_default_client", FakeClient)

        result = await extractor.extract(_chunk(), GENERIC)

        assert result.entities == []


class TestEscalatingExtractor:
    """EscalatingExtractor escalates on weak results, not on strong ones."""

    def _make_extractor(
        self,
        *,
        primary_entities: list | None = None,
        primary_confidences: list[float | None] | None = None,
        escalate_entities: list | None = None,
    ) -> tuple[EscalatingExtractor, list[str]]:
        """Build an EscalatingExtractor with a fake primary and escalate_to.

        Returns the extractor and a list that records which extractors ran.
        """
        ran: list[str] = []

        primary_result = ExtractionResult(
            entities=[
                ExtractedEntity(
                    chunk_id=uuid4(),
                    label="Person",
                    text="X",
                    char_start=0,
                    char_end=1,
                    confidence=conf,
                )
                for conf in (primary_confidences or primary_entities or [])
            ]
            if primary_entities is not None
            else [],
            relations=[],
            extractor_name="primary",
        )

        escalate_result = ExtractionResult(
            entities=[
                ExtractedEntity(
                    chunk_id=uuid4(),
                    label="Person",
                    text="Y",
                    char_start=0,
                    char_end=1,
                    confidence=0.9,
                )
            ]
            if escalate_entities is not None
            else [],
            relations=[],
            extractor_name="escalate",
        )

        class FakeExtractor:
            def __init__(self, result: ExtractionResult, name: str) -> None:
                self._result = result
                self._name = name

            async def extract(self, chunk, schema):  # noqa: ANN001
                ran.append(self._name)
                return self._result

        primary = FakeExtractor(primary_result, "primary")
        escalate = FakeExtractor(escalate_result, "escalate")
        return EscalatingExtractor(primary=primary, escalate_to=escalate), ran

    async def test_escalates_on_zero_yield_above_word_floor(self) -> None:
        """Zero entities from primary escalates when chunk has enough words."""
        chunk = _chunk("This is a chunk with more than eight words in it.")
        extractor, ran = self._make_extractor(primary_entities=None)
        result = await extractor.extract(chunk, GENERIC)
        assert ran == ["primary", "escalate"]
        assert result.extractor_name == "escalate"

    async def test_does_not_escalate_on_zero_yield_below_word_floor(self) -> None:
        """Zero entities from primary is accepted when chunk is short."""
        chunk = _chunk("short")
        extractor, ran = self._make_extractor(primary_entities=None)
        result = await extractor.extract(chunk, GENERIC)
        assert ran == ["primary"]
        assert result.extractor_name == "primary"

    async def test_escalates_on_low_mean_confidence(self) -> None:
        """Mean confidence below threshold triggers escalation."""
        chunk = _chunk("This is a chunk with enough words to pass the floor.")
        extractor, ran = self._make_extractor(
            primary_entities=[1, 2],
            primary_confidences=[0.3, 0.4],
        )
        result = await extractor.extract(chunk, GENERIC)
        assert ran == ["primary", "escalate"]
        assert result.extractor_name == "escalate"

    async def test_does_not_escalate_on_high_confidence(self) -> None:
        """Confident primary result is kept as-is."""
        chunk = _chunk("This is a chunk with enough words to pass the floor.")
        extractor, ran = self._make_extractor(
            primary_entities=[1, 2],
            primary_confidences=[0.9, 0.95],
        )
        result = await extractor.extract(chunk, GENERIC)
        assert ran == ["primary"]
        assert result.extractor_name == "primary"

    async def test_does_not_escalate_when_no_confidence_reported(self) -> None:
        """Primary result with no confidence values is not escalated."""
        chunk = _chunk("This is a chunk with enough words to pass the floor.")
        extractor, ran = self._make_extractor(
            primary_entities=[1, 2],
            primary_confidences=[None, None],
        )
        result = await extractor.extract(chunk, GENERIC)
        assert ran == ["primary"]
        assert result.extractor_name == "primary"

    async def test_never_merges_entities_from_both_extractors(self) -> None:
        """Escalation returns escalate_to's result, never a merge."""
        chunk = _chunk("This is a chunk with enough words to pass the floor.")
        extractor, _ = self._make_extractor(primary_entities=None)
        result = await extractor.extract(chunk, GENERIC)
        # Only escalate's entities should be present
        assert all(e.text == "Y" for e in result.entities)
