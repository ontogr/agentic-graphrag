"""Check that cited evidence ids trace to evidence the caller fetched.

The check confirms traceability only. A ``valid`` verdict means the citation names
text that was fetched in scope. It does not show that the text supports a claim.
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from uuid import UUID

from agrag.common.data_models.evidence import (
    CitationCheck,
    CitationResult,
    CitationVerdict,
    EvidenceKind,
    EvidenceReference,
)
from agrag.evidence._shared import scope_node_ids
from agrag.evidence.ids import MalformedEvidenceIdError, decode_evidence_id


_BRACKET = re.compile(r"\[([^\[\]\n]*)(\]|(?=\[|\n|$))")
_CITATION_LIKE = re.compile(r"ev\w*:|\bE\d+\b|^\d+$", re.I)


@dataclass(frozen=True)
class ParsedCitations:
    """Evidence ids and malformed citation-like tokens found in text."""

    ids: tuple[str, ...]
    malformed_tokens: tuple[str, ...]


def parse_citations(text: str) -> ParsedCitations:
    """Extract canonical evidence ids and malformed citation-like tokens.

    IDs may appear alone or grouped in brackets with comma or semicolon
    separators. Markdown links are ignored unless their label contains an
    evidence-id-like token.
    """
    ids: list[str] = []
    malformed: list[str] = []
    for match in _BRACKET.finditer(text):
        body, close = match.groups()
        if not _CITATION_LIKE.search(body.strip()):
            continue
        if text[match.end() :].startswith("(") and not re.search(r"ev\w*:", body, re.I):
            continue
        invalid = close != "]"
        for raw_token in re.split(r"[,;]", body):
            token = raw_token.strip()
            try:
                decode_evidence_id(token)
            except MalformedEvidenceIdError:
                invalid = True
            else:
                ids.append(token)
        if invalid:
            malformed.append(match.group().rstrip())
    return ParsedCitations(
        ids=tuple(dict.fromkeys(ids)), malformed_tokens=tuple(malformed)
    )


async def check_citations(
    evidence_ids: Sequence[str],
    fetched_ids: Iterable[str],
    *,
    scope: frozenset[str],
) -> CitationResult:
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
        evidence_ids: Evidence ids the answer cites.
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

    checks = [
        CitationCheck(
            cited_id=cited_id,
            verdict=_verdict(cited_id, allowed, fetched_exact, fetched_spans),
        )
        for cited_id in evidence_ids
    ]
    return CitationResult(checks=checks, truncated=False)


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
