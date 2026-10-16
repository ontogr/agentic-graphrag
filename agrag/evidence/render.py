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
    """Replace validated inline IDs with numbered citations and a source list.

    Call after ``check_citations`` with only its valid IDs and complete fetches
    from the same scope. This function formats references, not claim support.
    Mixed invalid groups and existing Markdown links are left unchanged. Local
    sources display as text references. Numbers follow first appearance and
    group passages from the same document version. A narrower valid span keeps
    its fetched parent's metadata in the returned evidence.

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
    resolved: dict[str, FetchOutcome] = {}
    sources: dict[str, FetchOutcome] = {}
    for evidence_id in valid_ids:
        source = _source_for(evidence_id, complete)
        if source is None:
            continue
        if source.citation_markdown is not None:
            resolved[evidence_id] = source
            sources.setdefault(source.evidence_id, source)
    numbered: dict[tuple[str, str], int] = {}
    references: list[str] = []

    def replace(match: re.Match[str]) -> str:
        if answer[match.end() :].startswith("("):
            return match.group()
        parsed = parse_citations(match.group())
        if (
            not parsed.ids
            or parsed.malformed_tokens
            or any(evidence_id not in resolved for evidence_id in parsed.ids)
        ):
            return match.group()
        markers: dict[int, str] = {}
        for evidence_id in parsed.ids:
            source = resolved[evidence_id]
            reference = decode_evidence_id(evidence_id)
            key = (str(reference.document_node_id), reference.content_hash_prefix)
            label = source.citation_markdown
            if label is None:
                continue
            if key not in numbered:
                numbered[key] = len(numbered) + 1
                references.append(f"[{numbered[key]}] {label}")
            number = numbered[key]
            marker = f"[{number}]"
            if label.startswith("[") and "](" in label:
                destination = label.rsplit("](", 1)[1]
                marker = f"[{marker}]({destination}"
            markers[number] = marker
        return " ".join(markers.values())

    rendered = _INLINE.sub(replace, answer)
    if references:
        rendered += "\n\n### Sources\n\n" + "\n\n".join(references)
    return rendered, list(sources.values())


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
