"""Check that cited evidence ids trace to evidence the caller fetched.

The check confirms traceability only. A ``valid`` verdict means the citation names
text that was fetched in scope. It does not show that the text supports a claim.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from uuid import UUID

from agrag.common.data_models.evidence import (
    CitationCheck,
    CitationVerdict,
    EvidenceKind,
    EvidenceReference,
)
from agrag.evidence._shared import scope_node_ids
from agrag.evidence.ids import MalformedEvidenceIdError, decode_evidence_id


async def check_citations(
    cited_ids: Sequence[str],
    fetched_ids: Iterable[str],
    *,
    scope: frozenset[str],
) -> list[CitationCheck]:
    """Return one verdict for each cited evidence id, in the order given.

    A citation is ``valid`` when its document is in scope and it was fetched. A
    span citation is also valid when its range lies inside a fetched span of the
    same document and content hash. A wider range is ``not_fetched``. A chunk
    citation must equal a fetched id. A citation of a document outside the scope
    is ``unavailable``, even when the caller fetched it earlier. A string that
    does not decode is ``malformed``.

    Pass only the ids whose fetch returned ``ok``. An id from a ``truncated`` or
    ``partial`` outcome names more text than the caller received.

    Args:
        cited_ids: Evidence ids the answer cites.
        fetched_ids: Evidence ids the caller fetched. A malformed entry is
            ignored.
        scope: Keys of the documents the caller may read.

    Returns:
        One check for each cited id, in the same order.
    """
    allowed = scope_node_ids(scope)
    fetched_exact: set[str] = set()
    fetched_spans: dict[tuple[UUID, str], list[tuple[int, int]]] = defaultdict(list)
    for evidence_id in fetched_ids:
        try:
            reference = decode_evidence_id(evidence_id)
        except MalformedEvidenceIdError:
            continue
        fetched_exact.add(evidence_id)
        if reference.kind is EvidenceKind.SPAN:
            fetched_spans[
                (reference.document_node_id, reference.content_hash_prefix)
            ].append(_span_bounds(reference))

    return [
        CitationCheck(
            cited_id=cited_id,
            verdict=_verdict(cited_id, allowed, fetched_exact, fetched_spans),
        )
        for cited_id in cited_ids
    ]


def _span_bounds(reference: EvidenceReference) -> tuple[int, int]:
    """Return the offsets of a span reference."""
    if reference.char_start is None or reference.char_end is None:
        raise ValueError("a span reference needs char_start and char_end")
    return reference.char_start, reference.char_end


def _verdict(
    cited_id: str,
    allowed: frozenset[str],
    fetched_exact: set[str],
    fetched_spans: dict[tuple[UUID, str], list[tuple[int, int]]],
) -> CitationVerdict:
    """Return the verdict for one cited id."""
    try:
        reference = decode_evidence_id(cited_id)
    except MalformedEvidenceIdError:
        return CitationVerdict.MALFORMED
    if str(reference.document_node_id) not in allowed:
        return CitationVerdict.UNAVAILABLE
    if cited_id in fetched_exact:
        return CitationVerdict.VALID
    if reference.kind is EvidenceKind.SPAN:
        start, end = _span_bounds(reference)
        key = (reference.document_node_id, reference.content_hash_prefix)
        if any(
            fetched_start <= start and end <= fetched_end
            for fetched_start, fetched_end in fetched_spans.get(key, [])
        ):
            return CitationVerdict.VALID
    return CitationVerdict.NOT_FETCHED
