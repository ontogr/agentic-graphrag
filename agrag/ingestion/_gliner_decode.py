"""Read the output of one gliner2 call into an ExtractionResult."""

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.dropped import DroppedCount
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.ingestion.settings import ExtractionSettings


_Span = tuple[int, int]
_RelationReason = Literal["below_relation_cut", "unresolved_endpoint", "off_pattern"]


@dataclass(frozen=True, slots=True)
class _Mention:
    """One entity span with its label and score, in chunk offsets."""

    label: str
    text: str
    start: int
    end: int
    confidence: float


def _trim(chunk_text: str, start: int, end: int) -> _Span | None:
    """Return the range without the whitespace around its text, or None.

    gliner2 cuts the text of a span with ``strip()`` but reports the range it
    cut from. The range can therefore start or end on a space.

    Args:
        chunk_text: The text the offsets index.
        start: The reported start offset.
        end: The reported end offset, exclusive.

    Returns:
        The trimmed ``(start, end)``, or None when the range lies outside the
        text or holds only whitespace.
    """
    if not 0 <= start < end <= len(chunk_text):
        return None
    window = chunk_text[start:end]
    trimmed = window.strip()
    if not trimmed:
        return None
    lead = len(window) - len(window.lstrip())
    return start + lead, start + lead + len(trimmed)


def _overlaps(first: _Span, second: _Span) -> bool:
    """Return whether two half-open ranges share at least one character."""
    return first[0] < second[1] and second[0] < first[1]


def _mentions(
    raw_entities: dict[str, list[dict[str, Any]]],
    chunk_text: str,
    schema: GraphSchema,
) -> list[_Mention]:
    """Return one mention per span, in text order.

    gliner2 decodes each label on its own, so a span can come back under a
    parent label and a child label. The label with the highest score wins. On
    equal scores the deeper label wins, then the label name, so the result
    does not depend on dict order.

    Args:
        raw_entities: The ``entities`` value of a gliner2 result.
        chunk_text: The text the offsets index.
        schema: The schema that declares the labels.

    Returns:
        The surviving mentions, ordered by start and end offset.
    """
    depth = {item.label: len(schema.ancestors(item.label)) for item in schema.entities}

    def rank(mention: _Mention) -> tuple[float, int, str]:
        return mention.confidence, depth[mention.label], mention.label

    best: dict[_Span, _Mention] = {}
    for label, items in raw_entities.items():
        if label not in depth:
            continue
        for item in items:
            span = _trim(chunk_text, item["start"], item["end"])
            if span is None:
                continue
            mention = _Mention(
                label=label,
                text=chunk_text[span[0] : span[1]],
                start=span[0],
                end=span[1],
                confidence=float(item["confidence"]),
            )
            held = best.get(span)
            if held is None or rank(mention) > rank(held):
                best[span] = mention
    return sorted(best.values(), key=lambda mention: (mention.start, mention.end))


def _endpoint_index(
    endpoint: dict[str, Any],
    chunk_text: str,
    by_span: dict[_Span, int],
    by_text: dict[str, list[int]],
) -> int | None:
    """Return the index of the kept entity that a relation endpoint names.

    Relation endpoints come from the model's own candidate pool, so they need
    not equal a kept entity span. The trimmed range is tried first. Text is the
    fallback, and only when exactly one kept entity has that text.
    """
    span = _trim(chunk_text, endpoint["start"], endpoint["end"])
    if span is not None and span in by_span:
        return by_span[span]
    matches = by_text.get(str(endpoint["text"]).strip().casefold(), [])
    return matches[0] if len(matches) == 1 else None


def _endpoint_label(index: int | None, entities: list[ExtractedEntity]) -> str | None:
    """Return the label of a resolved endpoint, or None when unresolved."""
    return None if index is None else entities[index].label


def _relations(
    raw_relations: dict[str, list[dict[str, Any]]],
    *,
    chunk: Chunk,
    chunk_id: UUID,
    schema: GraphSchema,
    settings: ExtractionSettings,
    entities: list[ExtractedEntity],
) -> tuple[list[ExtractedRelation], list[CandidateRecord], list[DroppedCount]]:
    """Keep the relations that pass the cut and the pattern check.

    The checks run in this order: the confidence cut, then endpoint
    resolution, then the pattern check. The first one that fails names the
    reason of the candidate. A relation from an entity to itself is dropped
    without a candidate.

    Args:
        raw_relations: The ``relation_extraction`` value of a gliner2 result.
        chunk: The chunk the result came from.
        chunk_id: The id of ``chunk``.
        schema: The schema whose ``allows`` runs the pattern check.
        settings: The thresholds and the candidate switch.
        entities: The kept entities that endpoints bind to.

    Returns:
        The kept relations and the candidates for the rest.
    """
    by_span = {(item.char_start, item.char_end): i for i, item in enumerate(entities)}
    by_text: dict[str, list[int]] = {}
    for index, item in enumerate(entities):
        by_text.setdefault(item.text.casefold(), []).append(index)
    declared = {item.label for item in schema.relations}

    kept: dict[tuple[int, int, str], float] = {}
    candidates: list[CandidateRecord] = []
    dropped: list[DroppedCount] = []
    for label, pairs in raw_relations.items():
        if label not in declared:
            continue
        cut = settings.label_thresholds.get(label, settings.relation_threshold)
        for pair in pairs:
            head, tail = pair["head"], pair["tail"]
            score = float(head["confidence"])
            source = _endpoint_index(head, chunk.text, by_span, by_text)
            target = _endpoint_index(tail, chunk.text, by_span, by_text)
            if source is not None and source == target:
                continue
            reason: _RelationReason
            if score < cut:
                reason = "below_relation_cut"
            elif source is None or target is None:
                reason = "unresolved_endpoint"
            elif not schema.allows(
                label, entities[source].label, entities[target].label
            ):
                reason = "off_pattern"
            else:
                key = (source, target, label)
                kept[key] = max(kept.get(key, 0.0), score)
                continue
            dropped.append(
                DroppedCount(
                    kind="relation",
                    label=label,
                    reason=reason,
                    count=1,
                    chunk_id=chunk_id,
                )
            )
            if settings.candidates_enabled:
                candidates.append(
                    CandidateRecord(
                        kind="relation",
                        label=label,
                        text="",
                        source_text=str(head["text"]).strip(),
                        target_text=str(tail["text"]).strip(),
                        source_label=_endpoint_label(source, entities),
                        target_label=_endpoint_label(target, entities),
                        confidence=score,
                        reason=reason,
                        chunk_id=chunk_id,
                    )
                )
    relations = [
        ExtractedRelation(
            chunk_id=chunk_id,
            label=label,
            source_index=source,
            target_index=target,
            confidence=score,
            extractors=["gliner"],
        )
        for (source, target, label), score in sorted(kept.items())
    ]
    return relations, candidates, dropped


def _band_candidates(
    band_raw: dict[str, Any],
    *,
    chunk: Chunk,
    chunk_id: UUID,
    schema: GraphSchema,
    settings: ExtractionSettings,
    entities: list[ExtractedEntity],
) -> list[CandidateRecord]:
    """Return entity candidates from the low-threshold call.

    A span is a candidate when it scores from ``band_floor`` up to, but not
    including, the cut of its label, and shares no character with a kept span.
    The low-threshold call can pick other spans than the main call, because
    gliner2 resolves overlap by the largest total score. So its output is read
    for the band only, never for kept entities.
    """
    kept_spans = [(item.char_start, item.char_end) for item in entities]
    candidates: list[CandidateRecord] = []
    for mention in _mentions(band_raw.get("entities", {}), chunk.text, schema):
        cut = settings.label_thresholds.get(mention.label, settings.entity_threshold)
        if not settings.band_floor <= mention.confidence < cut:
            continue
        span = (mention.start, mention.end)
        if any(_overlaps(span, kept) for kept in kept_spans):
            continue
        candidates.append(
            CandidateRecord(
                kind="entity",
                label=mention.label,
                text=mention.text,
                confidence=mention.confidence,
                reason="entity_band",
                chunk_id=chunk_id,
            )
        )
    return candidates


def decode_gliner(
    raw: dict[str, Any],
    band_raw: dict[str, Any] | None,
    chunk: Chunk,
    schema: GraphSchema,
    settings: ExtractionSettings,
) -> ExtractionResult:
    """Return the ExtractionResult for the output of the gliner2 calls.

    Entities come from ``raw`` only. Each span keeps its highest-scoring label
    and offsets as gliner2 reports them, trimmed of surrounding whitespace.
    Relations pass the confidence cut and then ``GraphSchema.allows``. What
    fails becomes a candidate when ``settings.candidates_enabled``.

    Args:
        raw: The result of the main call: entities at ``entity_threshold`` and
            relations from ``relation_floor``, with confidence and spans.
        band_raw: The result of the entity-only call at ``band_floor``, or None
            when no band call ran.
        chunk: The chunk both calls read.
        schema: The schema both calls used.
        settings: Thresholds and the candidate switch.

    Returns:
        The kept entities and relations, the candidates, and whether a kept
        entity has a type that declares properties.

    Raises:
        ValueError: ``chunk.id`` is ``None``.
    """
    if chunk.id is None:
        raise ValueError("Chunk must have an id for extraction.")
    chunk_id = chunk.id
    entities = [
        ExtractedEntity(
            chunk_id=chunk_id,
            label=mention.label,
            text=mention.text,
            char_start=mention.start,
            char_end=mention.end,
            confidence=mention.confidence,
        )
        for mention in _mentions(raw.get("entities", {}), chunk.text, schema)
    ]
    relations, candidates, dropped = _relations(
        raw.get("relation_extraction", {}),
        chunk=chunk,
        chunk_id=chunk_id,
        schema=schema,
        settings=settings,
        entities=entities,
    )
    if settings.candidates_enabled and band_raw is not None:
        candidates.extend(
            _band_candidates(
                band_raw,
                chunk=chunk,
                chunk_id=chunk_id,
                schema=schema,
                settings=settings,
                entities=entities,
            )
        )
    with_properties = {item.label for item in schema.entities if item.properties}
    return ExtractionResult(
        entities=entities,
        relations=relations,
        extractor_name="gliner",
        candidates=candidates,
        dropped=dropped,
        needs_properties=any(item.label in with_properties for item in entities),
    )
