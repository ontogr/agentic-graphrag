"""Pure rules that choose which chunks the LLM extractor reads.

``Graph`` extracts a batch in two phases. The first extractor reads every
chunk. These functions then rank the chunks whose first result is weak and cut
the list at the escalation budget. Nothing here does I/O or awaits.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.ingestion._mentions import endpoint_key
from agrag.ingestion.reports.escalation_report import EscalationReport
from agrag.ingestion.settings import ExtractionSettings


# A kept span with no score ranks as if it were certain, so it never jumps
# ahead of a chunk that has a measured weak span.
_UNSCORED = 1.0

# Float noise such as 0.1 * 30 == 3.0000000000000004 must not add a chunk.
_CEIL_DIGITS = 9


@dataclass(frozen=True)
class EscalationPlan:
    """The outcome of ranking one batch.

    Attributes:
        ranked: The positions of every eligible chunk, weakest first.
        selected: The leading positions of ``ranked`` that the budget allows.
        scores: For each eligible position, its weakest span score, or
            ``None`` when the chunk has no scored span.
    """

    ranked: list[int]
    selected: list[int]
    scores: dict[int, float | None]

    def report(self, total: int) -> EscalationReport:
        """Summarise the plan as the run report of one batch.

        Args:
            total: The number of chunks in the batch, failed chunks included.

        Returns:
            The counts, the lowest score left, and the budget this batch needs.
        """
        left = self.ranked[len(self.selected) :]
        lows = [score for i in left if (score := self.scores[i]) is not None]
        return EscalationReport(
            total=total,
            eligible=len(self.ranked),
            escalated=len(self.selected),
            left_for_gliner=len(left),
            lowest_score_left=min(lows, default=None),
            budget_needed=len(self.ranked) / total if total else 0.0,
        )


def kept_entities(
    result: ExtractionResult, settings: ExtractionSettings
) -> list[ExtractedEntity]:
    """Return the entities of a result that count as kept spans.

    A kept span has a score at or above its label's threshold in
    ``settings.label_thresholds``, or the ``settings.entity_threshold`` when its
    label has none, or no score. Phase 2 passes these entities to the LLM
    extractor as candidates.

    Args:
        result: The first extractor's result for one chunk.
        settings: The entity threshold and the per-label thresholds.

    Returns:
        The kept entities in result order.
    """
    return [
        entity
        for entity in result.entities
        if entity.confidence is None
        or entity.confidence
        >= settings.label_thresholds.get(entity.label, settings.entity_threshold)
    ]


def labels_with_properties(schema: GraphSchema) -> frozenset[str]:
    """Return the entity labels whose type, or an ancestor type, has properties.

    Args:
        schema: The schema of the run.

    Returns:
        The labels whose chunks should reach the LLM extractor, because only
        an LLM extractor fills property values.
    """
    declared = {entity.label for entity in schema.entities if entity.properties}
    return frozenset(
        entity.label
        for entity in schema.entities
        if entity.label in declared
        or declared.intersection(schema.ancestors(entity.label))
    )


def budget_limit(total: int, eligible: int, budget: float | Literal["all"]) -> int:
    """Return how many eligible chunks the budget lets through.

    The budget is a share of the chunks in the batch, rounded up, and at least
    one chunk escalates when the budget is above zero and any chunk is
    eligible. A budget of zero escalates nothing.

    Args:
        total: The number of chunks in the batch.
        eligible: The number of eligible chunks.
        budget: A share of ``total`` between 0 and 1, or ``"all"`` for no
            ceiling.

    Returns:
        A count between 0 and ``eligible``.
    """
    if budget == "all":
        return eligible
    if budget <= 0:
        return 0
    share = math.ceil(round(budget * total, _CEIL_DIGITS))
    return min(eligible, max(1, share))


def plan_escalation(
    results: Sequence[ExtractionResult | None],
    settings: ExtractionSettings,
    *,
    chunks: Sequence[Chunk],
    property_labels: frozenset[str],
) -> EscalationPlan:
    """Rank the eligible chunks of a batch and cut the list at the budget.

    A chunk is eligible when any kept span scores below
    ``settings.escalation_threshold``, when it has no kept span and at least
    ``settings.min_escalation_words`` words, or when a kept span has a label in
    ``property_labels``. A kept span is an entity at or above
    ``settings.entity_threshold``, or one with no score. Chunks with a kept span
    rank by their lowest score, weakest first. Chunks with no kept span rank
    after them. Ties break by position in the batch.

    Args:
        results: The first extractor's result for each chunk, or ``None`` for a
            chunk that failed.
        settings: The thresholds, the word floor and the budget.
        chunks: The chunks of the batch, in the order of ``results``.
        property_labels: The labels that declare properties.

    Returns:
        The ranked and selected positions with their scores.
    """
    entries: list[tuple[int, float, int]] = []
    scores: dict[int, float | None] = {}
    for position, (result, chunk) in enumerate(zip(results, chunks, strict=True)):
        if result is None:
            continue
        kept = kept_entities(result, settings)
        if not kept:
            if len(chunk.text.split()) >= settings.min_escalation_words:
                entries.append((1, 0.0, position))
                scores[position] = None
            continue
        scored = [e.confidence for e in kept if e.confidence is not None]
        weakest = min(scored, default=None)
        is_weak = weakest is not None and weakest < settings.escalation_threshold
        has_properties = any(entity.label in property_labels for entity in kept)
        if is_weak or has_properties:
            entries.append((0, _UNSCORED if weakest is None else weakest, position))
            scores[position] = weakest
    entries.sort()
    ranked = [position for _, _, position in entries]
    limit = budget_limit(len(chunks), len(ranked), settings.escalation_budget)
    return EscalationPlan(ranked=ranked, selected=ranked[:limit], scores=scores)


def select_for_escalation(
    results: Sequence[ExtractionResult | None],
    settings: ExtractionSettings,
    *,
    chunks: Sequence[Chunk],
    property_labels: frozenset[str],
) -> list[int]:
    """Return the positions of the chunks the LLM extractor should read.

    Args:
        results: The first extractor's result for each chunk, or ``None`` for a
            chunk that failed.
        settings: The thresholds, the word floor and the budget.
        chunks: The chunks of the batch, in the order of ``results``.
        property_labels: The labels that declare properties.

    Returns:
        The selected positions, weakest chunk first.
    """
    return plan_escalation(
        results, settings, chunks=chunks, property_labels=property_labels
    ).selected


def accept_escalated(primary: ExtractionResult, escalated: ExtractionResult) -> bool:
    """Return whether the LLM result may replace the first result.

    An LLM answer that parsed to no entities replaces the first result only
    when the first result has no entities either, so a replacement never turns
    entities into nothing. A small LLM misses more entities than GLiNER, so an
    empty answer on a chunk where GLiNER found spans is treated as a miss.

    Args:
        primary: The first extractor's result for the chunk.
        escalated: The LLM extractor's parsed result for the same chunk.

    Returns:
        ``False`` when the first result must stay.
    """
    return bool(escalated.entities) or not primary.entities


def combine_results(
    primary: ExtractionResult, escalated: ExtractionResult
) -> ExtractionResult:
    """Return the result a chunk keeps after the LLM extractor read it.

    The result is the union of both answers. The LLM entities come first.
    An LLM entity with the same normalized name as a first-result entity takes
    that entity's span, text and confidence, because the local model measured
    them; the LLM label and properties win. Each first-result entity is matched
    at most once, in order, so two mentions that share a name keep their own
    measurements. An LLM entity with no unmatched first-result entity keeps its
    own offsets and has no confidence. First-result entities that the LLM did
    not return are appended unchanged. The LLM relations keep their indices.
    The first result's relations are re-pointed to the combined entity list and
    added unless the same source, label and target is already there. An empty
    LLM answer returns the first result unchanged.

    Args:
        primary: The first extractor's result for the chunk.
        escalated: The LLM extractor's result for the same chunk.

    Returns:
        The combined result. It keeps the LLM's extractor name and holds the
        candidates of both results.
    """
    if not escalated.entities:
        return primary
    unmatched: dict[str, list[int]] = {}
    for index, entity in enumerate(primary.entities):
        unmatched.setdefault(endpoint_key(entity.text), []).append(index)
    entities: list[ExtractedEntity] = []
    # Maps each first-result index to its combined index. Relations are
    # re-pointed through this map, so two mentions with the same name stay apart.
    combined_index: dict[int, int] = {}
    for llm_entity in escalated.entities:
        candidates = unmatched.get(endpoint_key(llm_entity.text))
        if not candidates:
            combined = llm_entity.model_copy(update={"confidence": None})
        else:
            first_index = candidates.pop(0)
            first = primary.entities[first_index]
            combined_index[first_index] = len(entities)
            combined = llm_entity.model_copy(
                update={
                    "text": first.text,
                    "char_start": first.char_start,
                    "char_end": first.char_end,
                    "confidence": first.confidence,
                }
            )
        entities.append(combined)
    for index, entity in enumerate(primary.entities):
        if index not in combined_index:
            combined_index[index] = len(entities)
            entities.append(entity)
    relations = list(escalated.relations)
    seen = {(r.source_index, r.label, r.target_index) for r in relations}
    for relation in primary.relations:
        source = combined_index[relation.source_index]
        target = combined_index[relation.target_index]
        if (source, relation.label, target) in seen:
            continue
        seen.add((source, relation.label, target))
        relations.append(
            relation.model_copy(update={"source_index": source, "target_index": target})
        )
    return escalated.model_copy(
        update={
            "entities": entities,
            "relations": relations,
            "candidates": [*primary.candidates, *escalated.candidates],
        }
    )


def format_escalation(
    report: EscalationReport, settings: ExtractionSettings
) -> list[str]:
    """Return the log lines that describe an escalation report.

    Args:
        report: The report of the run.
        settings: The settings that the run used. The budget appears in the
            first line of a ``hybrid`` run only, because it is ignored in the
            other modes.

    Returns:
        Up to five lines, the first one starting with the mode. A run with no
        chunks gives none. The second and third lines appear only when eligible
        chunks were left to the first extractor, the failure line only when an
        escalation failed, and the time line only when a phase took measurable
        time.
    """
    if report.total == 0:
        return []
    if report.mode == "gliner":
        first = f"mode gliner | chunks {report.total:,}"
    elif report.mode == "llm":
        first = (
            f"mode llm | chunks {report.total:,} | "
            f"skipped short {report.skipped_short:,} | "
            f"escalated {report.escalated:,}"
        )
    else:
        budget = (
            "all"
            if settings.escalation_budget == "all"
            else f"{settings.escalation_budget * 100:g}%"
        )
        first = (
            f"mode {report.mode} | chunks {report.total:,} | "
            f"eligible {report.eligible:,} "
            f"({report.eligible / report.total:.0%}) | "
            f"escalated {report.escalated:,} (budget {budget})"
        )
    lines = [first]
    if report.left_for_gliner:
        left = f"left for GLiNER only {report.left_for_gliner:,}"
        if report.lowest_score_left is not None:
            left += f" | lowest score left {report.lowest_score_left:.2f}"
        needed = math.ceil(round(report.budget_needed * 100, 6))
        lines += [left, f"budget needed {needed}% to escalate all eligible chunks"]
    if report.failed and report.mode == "llm":
        lines.append(f"llm failed on {report.failed:,} chunks")
    elif report.failed:
        lines.append(
            f"escalation failed on {report.failed:,} chunks | first result kept"
        )
    if report.primary_seconds or report.escalation_seconds:
        lines.append(
            f"time first extractor {report.primary_seconds:.1f}s | "
            f"escalation {report.escalation_seconds:.1f}s"
        )
    return lines
