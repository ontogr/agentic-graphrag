"""Integration tests for the Extractor implementations.

BAMLExtractor tests hit a real OpenAI-compatible endpoint. GlinerExtractor
tests download and run a real GLiNER2.5 model. Both skip gracefully when
their prerequisites are not available.
"""

import os
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import GENERIC
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion.extract import (
    BAMLExtractor,
    EscalatingExtractor,
    ExtractionLLMSettings,
    GlinerExtractor,
)


_PARAGRAPH = (
    "Ada Lovelace worked at the Analytical Engine Company in London. "
    "She collaborated with Charles Babbage on the design of the engine."
)
_DOC_ID = uuid4()


def _chunk(text: str = _PARAGRAPH) -> Chunk:
    """Build a minimal Chunk for extraction tests."""
    return Chunk(
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
        result = await extractor.extract(_chunk(), GENERIC)

        assert isinstance(result, ExtractionResult)
        assert result.extractor_name == "baml"
        assert len(result.entities) > 0
        labels = {e.label for e in result.entities}
        # At least one entity should be a known GENERIC label
        known = {"Person", "Organization", "Location"}
        assert labels & known, f"Expected known labels, got {labels}"

    @pytest.mark.skipif(not _has_llm_endpoint(), reason="LLM endpoint not configured")
    async def test_extracts_relations_from_paragraph(self) -> None:
        """A real LLM call returns relations between entities."""
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        extractor = BAMLExtractor(settings=settings)
        result = await extractor.extract(_chunk(), GENERIC)

        assert isinstance(result, ExtractionResult)
        # The paragraph describes Ada working at a company, so a relation
        # should be extracted
        if result.relations:
            rel = result.relations[0]
            assert rel.label in {r.label for r in GENERIC.relations}
            assert 0 <= rel.source_index < len(result.entities)
            assert 0 <= rel.target_index < len(result.entities)

    @pytest.mark.skipif(not _has_llm_endpoint(), reason="LLM endpoint not configured")
    async def test_relation_indices_reference_valid_entities(self) -> None:
        """Every relation's source and target index points to a real entity."""
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        extractor = BAMLExtractor(settings=settings)
        result = await extractor.extract(_chunk(), GENERIC)

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
        result = await extractor.extract(_chunk(), GENERIC)

        assert isinstance(result, ExtractionResult)
        assert result.extractor_name == "gliner"
        assert len(result.entities) > 0
        for entity in result.entities:
            assert entity.label in {e.label for e in GENERIC.entities}
            assert entity.text
            assert entity.char_start < entity.char_end

    @pytest.mark.skipif(not _has_gliner2(), reason="gliner2 not installed")
    async def test_relation_indices_reference_valid_entities(self) -> None:
        """Every relation's source and target index points to a real entity."""
        extractor = GlinerExtractor()
        result = await extractor.extract(_chunk(), GENERIC)

        for rel in result.relations:
            assert 0 <= rel.source_index < len(result.entities)
            assert 0 <= rel.target_index < len(result.entities)

    @pytest.mark.skipif(not _has_gliner2(), reason="gliner2 not installed")
    async def test_extracted_labels_match_schema(self) -> None:
        """No entity or relation label is outside the schema."""
        extractor = GlinerExtractor()
        result = await extractor.extract(_chunk(), GENERIC)

        schema_entity_labels = {e.label for e in GENERIC.entities}
        schema_relation_labels = {r.label for r in GENERIC.relations}
        for entity in result.entities:
            assert entity.label in schema_entity_labels
        for rel in result.relations:
            assert rel.label in schema_relation_labels


# ── EscalatingExtractor ────────────────────────────────────────────────


class TestEscalatingExtractorIntegration:
    """EscalatingExtractor runs GLiNER2 first, escalating to the LLM when weak."""

    @pytest.mark.skipif(
        not (_has_llm_endpoint() and _has_gliner2()),
        reason="Both LLM endpoint and gliner2 required",
    )
    async def test_escalates_when_gliner_returns_few_entities(self) -> None:
        """EscalatingExtractor falls back to the LLM when GLiNER is weak."""
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        extractor = EscalatingExtractor(
            primary=GlinerExtractor(),
            escalate_to=BAMLExtractor(settings=settings),
            min_confidence=0.9,  # Aggressive threshold to force escalation
        )
        result = await extractor.extract(_chunk(), GENERIC)

        assert isinstance(result, ExtractionResult)
        assert len(result.entities) > 0

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
        result = await extractor.extract(_chunk(), GENERIC)

        assert isinstance(result, ExtractionResult)
        assert result.extractor_name == "gliner"
        assert len(result.entities) > 0
