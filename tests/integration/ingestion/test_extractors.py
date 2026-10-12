"""Integration tests for the Extractor implementations.

BAMLExtractor tests hit a real OpenAI-compatible endpoint. GlinerExtractor
tests download and run a real GLiNER2.5 model. Both skip gracefully when
their prerequisites are not available.
"""

import os
from pathlib import Path
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion.extract import (
    BAMLExtractor,
    EscalatingExtractor,
    ExtractionLLMSettings,
    GlinerExtractor,
)
from agrag.ingestion.settings import ExtractionSettings


_PARAGRAPH = (
    "Ada Lovelace worked at the Analytical Engine Company in London. "
    "She collaborated with Charles Babbage on the design of the engine."
)
_DOC_ID = uuid4()


def _chunk(text: str = _PARAGRAPH) -> Chunk:
    """Build a minimal Chunk for extraction tests."""
    return Chunk(
        id=uuid4(),
        document_id=_DOC_ID,
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )


def _has_llm_endpoint() -> bool:
    """Return True when the LLM endpoint env vars are set."""
    return bool(os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_MODEL_ID"))


def _has_gliner2() -> bool:
    """Return True when the gliner2 package is importable."""
    try:
        import gliner2  # noqa: F401, PLC0415

        return True
    except ImportError:
        return False


# ── BAMLExtractor ──────────────────────────────────────────────────────


class TestBAMLExtractorIntegration:
    """BAMLExtractor extracts entities and relations via a real LLM endpoint."""

    @pytest.mark.skipif(not _has_llm_endpoint(), reason="LLM endpoint not configured")
    async def test_extracts_entities_from_paragraph(self) -> None:
        """A real LLM call returns recognized entities."""
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        extractor = BAMLExtractor(settings=settings)
        result = await extractor.extract(_chunk(), DEFAULT_SCHEMA)

        assert isinstance(result, ExtractionResult)
        assert result.extractor_name == "baml"
        assert len(result.entities) > 0
        labels = {e.label for e in result.entities}
        # At least one entity should be a known DEFAULT_SCHEMA label
        known = {"Person", "Organization", "Location"}
        assert labels & known, f"Expected known labels, got {labels}"

    @pytest.mark.skipif(not _has_llm_endpoint(), reason="LLM endpoint not configured")
    async def test_extracts_relations_from_paragraph(self) -> None:
        """A real LLM call returns relations between entities."""
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        extractor = BAMLExtractor(settings=settings)
        result = await extractor.extract(_chunk(), DEFAULT_SCHEMA)

        assert isinstance(result, ExtractionResult)
        # The paragraph describes Ada working at a company, so at least one
        # relation should be extracted.
        assert len(result.relations) > 0, "Expected at least one relation"
        rel = result.relations[0]
        assert rel.label in {r.label for r in DEFAULT_SCHEMA.relations}
        assert 0 <= rel.source_index < len(result.entities)
        assert 0 <= rel.target_index < len(result.entities)

    @pytest.mark.skipif(not _has_llm_endpoint(), reason="LLM endpoint not configured")
    async def test_relation_indices_reference_valid_entities(self) -> None:
        """Every relation's source and target index points to a real entity."""
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        extractor = BAMLExtractor(settings=settings)
        result = await extractor.extract(_chunk(), DEFAULT_SCHEMA)

        for rel in result.relations:
            assert 0 <= rel.source_index < len(result.entities)
            assert 0 <= rel.target_index < len(result.entities)


# ── GlinerExtractor ────────────────────────────────────────────────────


class TestGlinerExtractorIntegration:
    """GlinerExtractor extracts entities and relations with a real model."""

    @pytest.mark.skipif(not _has_gliner2(), reason="gliner2 not installed")
    async def test_extracts_entities_from_paragraph(self) -> None:
        """A real GLiNER2.5 model returns recognized entities."""
        extractor = GlinerExtractor()
        result = await extractor.extract(_chunk(), DEFAULT_SCHEMA)

        assert isinstance(result, ExtractionResult)
        assert result.extractor_name == "gliner"
        assert len(result.entities) > 0
        for entity in result.entities:
            assert entity.label in {e.label for e in DEFAULT_SCHEMA.entities}
            assert entity.text
            assert entity.char_start < entity.char_end

    @pytest.mark.skipif(not _has_gliner2(), reason="gliner2 not installed")
    async def test_relation_indices_reference_valid_entities(self) -> None:
        """Every relation's source and target index points to a real entity."""
        extractor = GlinerExtractor()
        result = await extractor.extract(_chunk(), DEFAULT_SCHEMA)

        for rel in result.relations:
            assert 0 <= rel.source_index < len(result.entities)
            assert 0 <= rel.target_index < len(result.entities)

    @pytest.mark.skipif(not _has_gliner2(), reason="gliner2 not installed")
    async def test_extracted_labels_match_schema(self) -> None:
        """No entity or relation label is outside the schema."""
        extractor = GlinerExtractor()
        result = await extractor.extract(_chunk(), DEFAULT_SCHEMA)

        schema_entity_labels = {e.label for e in DEFAULT_SCHEMA.entities}
        schema_relation_labels = {r.label for r in DEFAULT_SCHEMA.relations}
        for entity in result.entities:
            assert entity.label in schema_entity_labels
        for rel in result.relations:
            assert rel.label in schema_relation_labels

    @pytest.mark.skipif(not _has_gliner2(), reason="gliner2 not installed")
    async def test_entities_and_relations_carry_confidence(
        self, tmp_path: Path
    ) -> None:
        """A real model supplies a bounded score for each extracted item."""
        result = await GlinerExtractor().extract(_chunk(), DEFAULT_SCHEMA)

        assert result.entities
        assert result.relations
        for entity in result.entities:
            assert entity.confidence is not None
            assert 0.5 <= entity.confidence <= 1.0
        for relation in result.relations:
            assert relation.confidence is not None
            assert 0.5 <= relation.confidence <= 1.0
        (tmp_path / "extraction.json").write_text(result.model_dump_json(indent=2))

    @pytest.mark.skipif(not _has_gliner2(), reason="gliner2 not installed")
    async def test_bf16_model_still_extracts(self) -> None:
        """Casting the loaded model to bf16 leaves it able to extract."""
        result = await GlinerExtractor(
            settings=ExtractionSettings(dtype="bf16")
        ).extract(_chunk(), DEFAULT_SCHEMA)

        assert result.entities


# ── EscalatingExtractor ────────────────────────────────────────────────


class TestEscalatingExtractorIntegration:
    """EscalatingExtractor runs GLiNER2 first, escalating to the LLM when weak."""

    @pytest.mark.skipif(
        not (_has_llm_endpoint() and _has_gliner2()),
        reason="Both LLM endpoint and gliner2 required",
    )
    async def test_escalating_extractor_produces_valid_results(self) -> None:
        """EscalatingExtractor returns valid extraction from either path.

        Whether GLiNER finds entities (no escalation) or returns empty
        (escalation to LLM), the result must always be valid. Escalation
        logic is covered by unit tests; this integration test verifies the
        two extractors compose correctly end-to-end.
        """
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        extractor = EscalatingExtractor(
            primary=GlinerExtractor(),
            escalate_to=BAMLExtractor(settings=settings),
            min_chunk_words=2,
        )
        result = await extractor.extract(_chunk(), DEFAULT_SCHEMA)

        assert isinstance(result, ExtractionResult)
        assert len(result.entities) > 0
        assert result.extractor_name in ("gliner", "baml")

    @pytest.mark.skipif(
        not (_has_llm_endpoint() and _has_gliner2()),
        reason="Both LLM endpoint and gliner2 required",
    )
    async def test_uses_gliner_when_confident(self) -> None:
        """EscalatingExtractor keeps GLiNER's result when confidence is high."""
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        extractor = EscalatingExtractor(
            primary=GlinerExtractor(),
            escalate_to=BAMLExtractor(settings=settings),
            min_confidence=0.01,  # Very low threshold — GLiNER should pass
        )
        result = await extractor.extract(_chunk(), DEFAULT_SCHEMA)

        assert isinstance(result, ExtractionResult)
        assert result.extractor_name == "gliner"
        assert len(result.entities) > 0
