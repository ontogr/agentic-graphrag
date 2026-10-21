"""Tests for the provenance that combine_results keeps on relations.

Results are built by hand. No extractor runs. A relation that both extractors
found is kept once, with the first result's confidence and both extractor
names. A relation from one extractor keeps its own provenance.
"""

import hashlib
from uuid import uuid4

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion._escalation import combine_results


_TEXT = "alpha beta gamma"


def _chunk() -> Chunk:
    """Build a chunk with a fixed text."""
    return Chunk(
        id=uuid4(),
        document_id=uuid4(),
        text=_TEXT,
        content_hash=hashlib.sha256(_TEXT.encode("utf-8")).hexdigest(),
        provenance=TextProvenance(char_start=0, char_end=len(_TEXT)),
    )


def _entity(
    chunk: Chunk, text: str, start: int, confidence: float | None
) -> ExtractedEntity:
    """Build an entity mention at the given character offset."""
    return ExtractedEntity(
        chunk_id=chunk.id,
        label="Thing",
        text=text,
        char_start=start,
        char_end=start + len(text),
        confidence=confidence,
    )


def _relation(
    chunk: Chunk,
    label: str,
    source_index: int,
    target_index: int,
    *,
    confidence: float | None,
    extractors: list[str],
) -> ExtractedRelation:
    """Build a relation mention between two entity positions."""
    return ExtractedRelation(
        chunk_id=chunk.id,
        label=label,
        source_index=source_index,
        target_index=target_index,
        confidence=confidence,
        extractors=extractors,
    )


def _summary(result: ExtractionResult) -> list[tuple[object, ...]]:
    """Return the label, indices, confidence and extractors of each relation."""
    return [
        (
            relation.label,
            relation.source_index,
            relation.target_index,
            relation.confidence,
            relation.extractors,
        )
        for relation in result.relations
    ]


class TestCombineProvenance:
    """Relation provenance survives the union of two extractors."""

    def test_shared_relation_keeps_one_copy_with_both_extractors(self) -> None:
        """A relation both extractors found gets the first confidence and both names."""
        chunk = _chunk()
        primary = ExtractionResult(
            entities=[
                _entity(chunk, "alpha", 0, 0.9),
                _entity(chunk, "beta", 6, 0.8),
            ],
            relations=[
                _relation(
                    chunk,
                    "KNOWS",
                    0,
                    1,
                    confidence=0.4,
                    extractors=["gliner"],
                )
            ],
            extractor_name="gliner",
        )
        llm = ExtractionResult(
            entities=[
                _entity(chunk, "alpha", 0, None),
                _entity(chunk, "beta", 6, None),
            ],
            relations=[
                _relation(
                    chunk,
                    "KNOWS",
                    0,
                    1,
                    confidence=None,
                    extractors=["llm"],
                )
            ],
            extractor_name="baml",
        )

        combined = combine_results(primary, llm)

        assert _summary(combined) == [("KNOWS", 0, 1, 0.4, ["gliner", "llm"])]

    def test_first_result_only_relation_keeps_its_extractor_and_confidence(
        self,
    ) -> None:
        """A relation the LLM did not return keeps GLiNER's confidence and name."""
        chunk = _chunk()
        primary = ExtractionResult(
            entities=[
                _entity(chunk, "alpha", 0, 0.9),
                _entity(chunk, "beta", 6, 0.8),
                _entity(chunk, "gamma", 11, 0.7),
            ],
            relations=[
                _relation(
                    chunk,
                    "LOCATED_IN",
                    1,
                    2,
                    confidence=0.6,
                    extractors=["gliner"],
                )
            ],
            extractor_name="gliner",
        )
        llm = ExtractionResult(
            entities=[
                _entity(chunk, "alpha", 0, None),
                _entity(chunk, "beta", 6, None),
            ],
            relations=[],
            extractor_name="baml",
        )

        combined = combine_results(primary, llm)

        assert _summary(combined) == [("LOCATED_IN", 1, 2, 0.6, ["gliner"])]

    def test_llm_only_relation_keeps_its_extractor_and_has_no_confidence(
        self,
    ) -> None:
        """A relation only the LLM found is kept with the LLM name and no score."""
        chunk = _chunk()
        primary = ExtractionResult(
            entities=[
                _entity(chunk, "alpha", 0, 0.9),
                _entity(chunk, "beta", 6, 0.8),
            ],
            relations=[],
            extractor_name="gliner",
        )
        llm = ExtractionResult(
            entities=[
                _entity(chunk, "alpha", 0, None),
                _entity(chunk, "beta", 6, None),
            ],
            relations=[
                _relation(
                    chunk,
                    "KNOWS",
                    0,
                    1,
                    confidence=None,
                    extractors=["llm"],
                )
            ],
            extractor_name="baml",
        )

        combined = combine_results(primary, llm)

        assert _summary(combined) == [("KNOWS", 0, 1, None, ["llm"])]
