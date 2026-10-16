"""Render validated evidence citations without changing their fetched provenance."""

import re
from collections.abc import Sequence

from agrag.common.data_models.evidence import EvidenceKind, FetchOutcome, FetchStatus
from agrag.evidence.citation import parse_citations
from agrag.evidence.ids import MalformedEvidenceIdError, decode_evidence_id


_INLINE = re.compile(r"\[[^\[\]\n]+\]")


def render_citations(
    answer: str,
    valid_ids: Sequence[str],
    fetched: Sequence[FetchOutcome],
) -> tuple[str, list[FetchOutcome]]:
    """Replace validated inline IDs with readable Markdown source references.

    Call after ``check_citations`` with only its valid IDs and complete fetches
    from the same scope. This function formats references, not claim support.
    Mixed invalid groups and existing Markdown links are left unchanged. Local
    sources become non-link references; no web URL is inferred from an ID.
    A narrower valid span uses its fetched parent's metadata while labeling its
    own offsets. The parent outcome remains unchanged in the source list.

    Args:
        answer: Answer containing square-bracket evidence IDs, alone or grouped.
        valid_ids: IDs accepted by the final citation validation pass.
        fetched: Actual fetch outcomes from that run or session.

    Returns:
        Markdown answer and deduplicated fetched sources in citation order.
    """
    complete = {
        item.evidence_id: item
        for item in fetched
        if item.status is FetchStatus.OK and not item.partial
    }
    labels: dict[str, str] = {}
    sources: dict[str, FetchOutcome] = {}
    for evidence_id in valid_ids:
        source = _source_for(evidence_id, complete)
        if source is None:
            continue
        reference = decode_evidence_id(evidence_id)
        label = source.format_citation(reference=reference)
        if label is not None:
            labels[evidence_id] = label
            sources.setdefault(source.evidence_id, source)

    def replace(match: re.Match[str]) -> str:
        if answer[match.end() :].startswith("("):
            return match.group()
        parsed = parse_citations(match.group())
        if (
            not parsed.ids
            or parsed.malformed_tokens
            or any(evidence_id not in labels for evidence_id in parsed.ids)
        ):
            return match.group()
        return "; ".join(labels[evidence_id] for evidence_id in parsed.ids)

    return _INLINE.sub(replace, answer), list(sources.values())


def _source_for(
    evidence_id: str, complete: dict[str, FetchOutcome]
) -> FetchOutcome | None:
    """Resolve an exact fetch or one containing span, never a union of fetches."""
    try:
        cited = decode_evidence_id(evidence_id)
    except MalformedEvidenceIdError:
        return None
    if evidence_id in complete:
        return complete[evidence_id]
    if cited.kind is not EvidenceKind.SPAN:
        return None
    for source in complete.values():
        try:
            parent = decode_evidence_id(source.evidence_id)
        except MalformedEvidenceIdError:
            continue
        if (
            parent.kind is EvidenceKind.SPAN
            and parent.document_node_id == cited.document_node_id
            and parent.content_hash_prefix == cited.content_hash_prefix
            and parent.char_start is not None
            and cited.char_start is not None
            and parent.char_end is not None
            and cited.char_end is not None
            and parent.char_start
            <= cited.char_start
            < cited.char_end
            <= parent.char_end
        ):
            return source
    return None
