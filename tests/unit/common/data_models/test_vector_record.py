"""Tests for the shared vector storage record shapes."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from agrag.common.data_models.vector_record import Distance, VectorHit, VectorRecord


class TestDistance:
    """The Distance enum resolves from its string value."""

    def test_construct_from_value(self) -> None:
        """A stored string value builds the enum."""
        assert Distance("Cosine") is Distance.COSINE
        assert Distance("Euclid") is Distance.EUCLID
        assert Distance("Dot") is Distance.DOT

    @pytest.mark.parametrize("member", [Distance.COSINE, Distance.EUCLID, Distance.DOT])
    def test_str_round_trip(self, member: Distance) -> None:
        """The string form parses back to the same member."""
        assert Distance(str(member)) is member


class TestVectorRecord:
    """A VectorRecord models one vector and its payload."""

    def test_construct_minimal(self) -> None:
        """A record needs an id, a vector, and a payload."""
        record_id = uuid4()
        record = VectorRecord(id=record_id, vector=[0.1, 0.2], payload={"text": "x"})
        assert record.id == record_id
        assert record.vector == [0.1, 0.2]
        assert record.payload == {"text": "x"}

    def test_json_round_trip(self) -> None:
        """A record dumps to JSON and validates back unchanged."""
        record_id = uuid4()
        record = VectorRecord(id=record_id, vector=[1.0, 2.0], payload={"k": "v"})
        dumped = record.model_dump(mode="json")
        restored = VectorRecord.model_validate(dumped)
        assert restored == record

    def test_id_required(self) -> None:
        """A record without an id fails validation."""
        with pytest.raises(ValidationError):
            VectorRecord(vector=[1.0], payload={})  # ty: ignore[missing-argument]


class TestVectorHit:
    """A VectorHit models one search result."""

    def test_construct_minimal(self) -> None:
        """A hit needs an id, a score, and a payload."""
        hit = VectorHit(id=uuid4(), score=0.9, payload={"text": "x"})
        assert hit.score == 0.9

    def test_json_round_trip(self) -> None:
        """A hit dumps to JSON and validates back unchanged."""
        hit_id = uuid4()
        hit = VectorHit(id=hit_id, score=0.5, payload={"k": 1})
        restored = VectorHit.model_validate(hit.model_dump(mode="json"))
        assert restored == hit
