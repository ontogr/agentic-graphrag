"""Candidate records bound long text, key unresolved endpoints and check shape.

Pure model checks with no database. Long text is cut to 200 characters with
a 16 character SHA-256 suffix, an unresolved relation endpoint keys by its
text, and each kind rejects a record that lacks the field it needs.
"""

from uuid import UUID

import pytest
from pydantic import ValidationError

from agrag.common.data_models.candidate import CandidateRecord


CHUNK_ID = UUID("11111111-1111-1111-1111-111111111111")
TARGET_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_long_text_key_is_truncated_with_a_digest() -> None:
    """Text longer than 200 normalized characters keys by prefix and digest."""
    record = CandidateRecord(
        kind="entity",
        label="Contract",
        text="a" * 250,
        confidence=0.4,
        reason="entity_band",
        chunk_id=CHUNK_ID,
    )

    assert record.key == "entity|contract|" + "a" * 200 + "~3f3e35e0a775d9b1"


def test_unresolved_relation_endpoint_keys_by_normalized_text() -> None:
    """A relation endpoint without an id keys by its normalized text."""
    record = CandidateRecord(
        kind="relation",
        label="Works For",
        source_text="The Acme Corp.",
        target_entity_id=TARGET_ID,
        confidence=0.7,
        reason="unresolved_endpoint",
        chunk_id=CHUNK_ID,
    )

    assert record.key == (
        "relation|works for|~acme corp|22222222-2222-2222-2222-222222222222"
    )
    assert record.source_edge_id is None


def test_entity_without_word_characters_is_rejected() -> None:
    """An entity whose text normalizes to nothing is refused."""
    with pytest.raises(ValidationError, match="a entity candidate needs text"):
        CandidateRecord(
            kind="entity",
            label="Contract",
            text="!!!",
            confidence=0.4,
            reason="entity_band",
            chunk_id=CHUNK_ID,
        )


def test_property_without_a_holder_is_rejected() -> None:
    """A property needs a resolved holder or the text of an unresolved one."""
    with pytest.raises(
        ValidationError,
        match="a property candidate needs source_entity_id or source_text",
    ):
        CandidateRecord(
            kind="property",
            label="salary",
            text="1000",
            confidence=0.5,
            reason="property",
            chunk_id=CHUNK_ID,
        )


def test_relation_side_without_an_id_or_text_is_rejected() -> None:
    """A relation whose target has neither an id nor text is refused."""
    with pytest.raises(
        ValidationError, match="a relation candidate needs target id or text"
    ):
        CandidateRecord(
            kind="relation",
            label="Works For",
            source_text="Acme",
            target_text="  ",
            confidence=0.7,
            reason="unresolved_endpoint",
            chunk_id=CHUNK_ID,
        )
