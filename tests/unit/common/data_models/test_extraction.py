"""Tests for the pre-resolution extraction data models."""

from uuid import uuid4

from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)


class TestExtractedEntity:
    """ExtractedEntity defaults and field types."""

    def test_confidence_defaults_to_none(self) -> None:
        """Confidence is optional and absent by default."""
        entity = ExtractedEntity(
            chunk_id=uuid4(),
            label="Person",
            text="Ada",
            char_start=0,
            char_end=3,
        )
        assert entity.confidence is None

    def test_text_and_label_are_plain_strings(self) -> None:
        """Surface text and label are simple strings, not structured types."""
        entity = ExtractedEntity(
            chunk_id=uuid4(),
            label="Person",
            text="Ada",
            char_start=0,
            char_end=3,
        )
        assert isinstance(entity.text, str)
        assert isinstance(entity.label, str)


class TestExtractedRelation:
    """ExtractedRelation references entities by plain int indices."""

    def test_indices_are_plain_ints(self) -> None:
        """Relation endpoints are int indices, not entity references."""
        relation = ExtractedRelation(
            chunk_id=uuid4(),
            label="RELATED_TO",
            source_index=0,
            target_index=1,
        )
        assert isinstance(relation.source_index, int)
        assert isinstance(relation.target_index, int)
        assert relation.confidence is None


class TestExtractionResult:
    """ExtractionResult carries entities, relations, and a provenance name."""

    def test_empty_result_round_trips(self) -> None:
        """An empty result stores no entities or relations."""
        result = ExtractionResult(entities=[], relations=[], extractor_name="baml")
        assert result.entities == []
        assert result.relations == []
        assert result.extractor_name == "baml"
