"""Encode and decode evidence ids.

A span id has the form ``ev1:s:<document_node_id>:<hash16>:<start>-<end>``, and a
chunk id has the form ``ev1:c:<document_node_id>:<hash16>:<chunk_id>``. The
document node id and the chunk id are lowercase hyphenated UUIDs. The hash is the
first 16 lowercase hex characters of the content hash. The ``ev1`` prefix is the
format version. The decoder accepts only the exact canonical form, so two ids that
name the same reference are the same string.
"""

import re

from pydantic import ValidationError

from agrag.common.data_models.evidence import EvidenceKind, EvidenceReference


_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_HASH_PREFIX = r"[0-9a-f]{16}"
_OFFSET = r"0|[1-9][0-9]{0,11}"
_SPAN_PATTERN = re.compile(rf"ev1:s:({_UUID}):({_HASH_PREFIX}):({_OFFSET})-({_OFFSET})")
_CHUNK_PATTERN = re.compile(rf"ev1:c:({_UUID}):({_HASH_PREFIX}):({_UUID})")


class MalformedEvidenceIdError(ValueError):
    """An evidence id does not decode to a valid reference."""


def encode_evidence_id(reference: EvidenceReference) -> str:
    """Return the evidence id of a reference.

    Args:
        reference: A span or chunk reference.

    Returns:
        The canonical id string.
    """
    if reference.kind is EvidenceKind.SPAN:
        return (
            f"ev1:s:{reference.document_node_id}:{reference.content_hash_prefix}:"
            f"{reference.char_start}-{reference.char_end}"
        )
    return (
        f"ev1:c:{reference.document_node_id}:{reference.content_hash_prefix}:"
        f"{reference.chunk_id}"
    )


def decode_evidence_id(evidence_id: str) -> EvidenceReference:
    """Return the reference an evidence id names.

    Args:
        evidence_id: A string produced by ``encode_evidence_id``.

    Returns:
        The decoded reference. Its content hash is the 16-character prefix.

    Raises:
        MalformedEvidenceIdError: The string is not a canonical evidence id, or it
            names a range that is empty or reversed.
    """
    try:
        return _parse(evidence_id)
    except ValidationError as exc:
        raise MalformedEvidenceIdError(str(exc)) from exc


def _parse(evidence_id: str) -> EvidenceReference:
    """Match an id against the two canonical forms and build its reference."""
    span = _SPAN_PATTERN.fullmatch(evidence_id)
    if span is not None:
        document, prefix, start, end = span.groups()
        return EvidenceReference(
            kind=EvidenceKind.SPAN,
            document_node_id=document,
            content_hash_prefix=prefix,
            char_start=int(start),
            char_end=int(end),
        )
    chunk = _CHUNK_PATTERN.fullmatch(evidence_id)
    if chunk is not None:
        document, prefix, chunk_id = chunk.groups()
        return EvidenceReference(
            kind=EvidenceKind.CHUNK,
            document_node_id=document,
            content_hash_prefix=prefix,
            chunk_id=chunk_id,
        )
    raise MalformedEvidenceIdError("not an evidence id")
