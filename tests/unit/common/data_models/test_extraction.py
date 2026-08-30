"""Tests for the pre-resolution extraction data models."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

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

    @pytest.mark.parametrize(
        ("char_start", "char_end", "message"),
        [(-1, 3, "char_start"), (4, 3, "char_end"), (3, 3, "char_end")],
    )
    def test_rejects_invalid_spans(
        self, char_start: int, char_end: int, message: str
    ) -> None:
        """Negative starts, reversed spans, and empty spans are rejected."""
        with pytest.raises(ValidationError, match=message):
            ExtractedEntity(
                chunk_id=uuid4(),
                label="Person",
                text="Ada",
                char_start=char_start,
                char_end=char_end,
            )


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

    @pytest.mark.parametrize(
        ("source_index", "target_index", "message"),
        [(-1, 1, "source_index"), (0, -1, "target_index"), (1, 1, "must differ")],
    )
    def test_rejects_invalid_indices(
        self, source_index: int, target_index: int, message: str
    ) -> None:
        """Negative and self-referential relation indices are rejected."""
        with pytest.raises(ValidationError, match=message):
            ExtractedRelation(
                chunk_id=uuid4(),
                label="RELATED_TO",
                source_index=source_index,
                target_index=target_index,
            )


class TestExtractionResult:
    """ExtractionResult carries entities, relations, and a provenance name."""

    def test_empty_result_round_trips(self) -> None:
        """An empty result stores no entities or relations."""
        result = ExtractionResult(entities=[], relations=[], extractor_name="baml")
        assert result.entities == []
        assert result.relations == []
        assert result.extractor_name == "baml"

    @pytest.mark.parametrize(
        ("source_index", "target_index", "message"),
        [(2, 0, "source_index"), (0, 2, "target_index")],
    )
    def test_rejects_relation_indices_outside_entities(
        self, source_index: int, target_index: int, message: str
    ) -> None:
        """Relation endpoints must refer to entities in the same result."""
        chunk_id = uuid4()
        entities = [
            ExtractedEntity(
                chunk_id=chunk_id,
                label="Person",
                text=text,
                char_start=index,
                char_end=index + 1,
            )
            for index, text in enumerate(("A", "B"))
        ]
        relation = ExtractedRelation(
            chunk_id=chunk_id,
            label="RELATED_TO",
            source_index=source_index,
            target_index=target_index,
        )

        with pytest.raises(ValidationError, match=message):
            ExtractionResult(
                entities=entities,
                relations=[relation],
                extractor_name="test",
            )
