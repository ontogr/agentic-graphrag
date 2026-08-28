"""Tests for the Extractor implementations and ExtractorMissingExtraError."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import GENERIC
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion.extract import (
    BAMLExtractor,
    EscalatingExtractor,
    ExtractorMissingExtraError,
    GlinerExtractor,
)
from agrag.loaders.corpus.errors import IngestionError


_DOC_ID = uuid4()


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
        # Simulate BAML raw output
        entities_raw = [
            SimpleNamespace(label="Person", text="Ada", char_start=0, char_end=3),
            SimpleNamespace(
                label="Organization",
                text="the Analytical Engine Company",
                char_start=14,
                char_end=43,
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
