"""Unit tests for the evidence id codec.

An evidence id is a string that callers keep and send back, so the codec must
round-trip every valid reference exactly and reject every malformed variant.
The tests use no database.
"""

from uuid import uuid4

import pytest

from agrag.common.data_models.evidence import EvidenceKind, EvidenceReference
from agrag.evidence.ids import (
    MalformedEvidenceIdError,
    decode_evidence_id,
    encode_evidence_id,
)


_HASH_PREFIX = "0123456789abcdef"


class TestEvidenceIdCodec:
    """Span and chunk ids round-trip and malformed ids are rejected."""

    def test_span_id_round_trips(self) -> None:
        """A span reference decodes to the same fields it was encoded from."""
        reference = EvidenceReference(
            kind=EvidenceKind.SPAN,
            document_node_id=uuid4(),
            content_hash_prefix=_HASH_PREFIX,
            char_start=1221,
            char_end=1361,
        )

        evidence_id = encode_evidence_id(reference)

        assert evidence_id.startswith("ev1:s:")
        assert decode_evidence_id(evidence_id) == reference

    def test_chunk_id_round_trips(self) -> None:
        """A chunk reference decodes to the same fields it was encoded from."""
        reference = EvidenceReference(
            kind=EvidenceKind.CHUNK,
            document_node_id=uuid4(),
            content_hash_prefix=_HASH_PREFIX,
            chunk_id=uuid4(),
        )

        evidence_id = encode_evidence_id(reference)

        assert evidence_id.startswith("ev1:c:")
        assert decode_evidence_id(evidence_id) == reference

    @pytest.mark.parametrize(
        "evidence_id",
        [
            "",
            "ev2:s:{doc}:{hash}:1-5",
            "ev1:x:{doc}:{hash}:1-5",
            "ev1:s:{doc}:{hash}:5-5",
            "ev1:s:{doc}:{hash}:9-5",
            "ev1:s:{doc}:{hash}:+1-5",
            "ev1:s:{doc}:{hash}:01-5",
            "ev1:s:{doc}:{hash}:-1-5",
            "ev1:s:{doc}:{hash}:1-5 ",
            "ev1:s:{doc}:0123456789ABCDEF:1-5",
            "ev1:s:{doc}:0123456789abcde:1-5",
            "ev1:s:{doc_upper}:{hash}:1-5",
            "ev1:s:not-a-uuid:{hash}:1-5",
            "ev1:c:{doc}:{hash}:not-a-uuid",
            "ev1:c:{doc}:{hash}:{chunk_upper}",
            "ev1:c:{doc}:{hash}:{chunk}:extra",
            "ev1:s:{doc}:{hash}:" + "9" * 5000 + "-" + "9" * 5000,
            "ev1:s:{doc}:{hash}:1234567890123-1234567890124",
        ],
    )
    def test_rejects_malformed_ids(self, evidence_id: str) -> None:
        """Every malformed id raises the codec error instead of decoding."""
        doc = str(uuid4())
        chunk = str(uuid4())
        candidate = evidence_id.format(
            doc=doc,
            doc_upper=doc.upper(),
            hash=_HASH_PREFIX,
            chunk=chunk,
            chunk_upper=chunk.upper(),
        )

        with pytest.raises(MalformedEvidenceIdError):
            decode_evidence_id(candidate)

    def test_span_reference_rejects_missing_range(self) -> None:
        """A span reference without offsets is not a valid reference."""
        with pytest.raises(ValueError):
            EvidenceReference(
                kind=EvidenceKind.SPAN,
                document_node_id=uuid4(),
                content_hash_prefix=_HASH_PREFIX,
            )
