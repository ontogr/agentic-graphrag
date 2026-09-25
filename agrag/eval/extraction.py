"""Extraction quality: entity and relation-triple F1 against gold annotations.

A gold annotation for one chunk is a hand-written ``ExtractionResult``. Scoring
has two steps. First, each predicted entity is aligned to a gold entity of the
same label. Second, each predicted relation is mapped through that alignment to
gold entity indices and compared as a ``(source, label, target)`` triple. Exact
alignment needs the same character span. Relaxed alignment needs an overlap
(intersection over union) of at least 0.5. Both are one to one: when several
predictions overlap one gold entity, the best overlap wins and the rest count
as false positives.

Every case reports exact and relaxed results. The exact score gates. A large gap
between the two shows a span boundary problem, not a missed entity. The
counting is scikit-learn's ``precision_recall_fscore_support``. Use
``micro_scores`` for the dataset score, because a mean of per-chunk scores
weights a short chunk the same as a long one.
"""

import asyncio
from collections.abc import Iterable, Sequence
from uuid import NAMESPACE_URL, uuid5

from deepeval.test_case import LLMTestCase
from pydantic import BaseModel
from sklearn.metrics import precision_recall_fscore_support

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.provenance import TextProvenance
from agrag.eval.adapter import ScoreMetric, ScoreResult, parse_json_case, to_json_case
from agrag.ingestion.extract import Extractor


_CONCURRENCY = 8
_RELAXED_MIN_OVERLAP = 0.5
_ENTITY = "entity"
_RELATION = "relation"

_MODES = ("", "relaxed_")


class ExtractionGold(BaseModel):
    """One gold-annotated chunk of text.

    Attributes:
        id: A stable id for the item. It seeds the chunk and document ids.
        text: The chunk text the extractor reads.
        gold: The annotation. Entity offsets index into ``text``.
    """

    id: str
    text: str
    gold: ExtractionResult


class Scores(BaseModel):
    """Precision, recall and F1.

    Attributes:
        precision: Correct predictions over all predictions.
        recall: Correct predictions over all gold items.
        f1: The harmonic mean of precision and recall.
    """

    precision: float
    recall: float
    f1: float


class MicroScores(BaseModel):
    """Dataset scores pooled over every item, for entities and relations.

    Attributes:
        entities_exact: Entity scores with exact span matching.
        entities_relaxed: Entity scores with overlap of at least 0.5.
        relations_exact: Relation triple scores over exact entity alignment.
        relations_relaxed: Relation triple scores over relaxed entity alignment.
    """

    entities_exact: Scores
    entities_relaxed: Scores
    relations_exact: Scores
    relations_relaxed: Scores


def extraction_case(
    chunk_text: str, predicted: ExtractionResult, gold: ExtractionResult
) -> LLMTestCase:
    """Build a test case that holds a predicted and a gold extraction.

    Args:
        chunk_text: The text the extractor read.
        predicted: The extractor output.
        gold: The gold annotation.
    """
    return to_json_case(chunk_text, predicted, gold)


async def run_extractor(
    extractor: Extractor,
    items: Sequence[ExtractionGold],
    schema: GraphSchema,
    *,
    concurrency: int = _CONCURRENCY,
) -> list[LLMTestCase]:
    """Run an extractor over gold items and build one test case per item.

    Chunk and document ids come from the item id, so runs are repeatable.

    Args:
        extractor: The extractor under test.
        items: The gold-annotated chunks.
        schema: The schema the extractor works to.
        concurrency: The most extractor calls that run at once. Lower it for an
            endpoint that limits concurrent requests.

    Returns:
        One test case per item, in the order of ``items``.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def run(item: ExtractionGold) -> LLMTestCase:
        chunk = Chunk(
            id=uuid5(NAMESPACE_URL, item.id),
            document_id=uuid5(NAMESPACE_URL, f"{item.id}#document"),
            text=item.text,
            provenance=TextProvenance(char_start=0, char_end=len(item.text)),
        )
        async with semaphore:
            predicted = await extractor.extract(chunk, schema)
        return extraction_case(item.text, predicted, item.gold)

    return list(await asyncio.gather(*(run(item) for item in items)))


def entity_quality_metric(*, threshold: float = 0.0) -> ScoreMetric:
    """Build a metric for entity F1 on one test case.

    The case score is the exact F1. Use a new metric for each case, and pass the
    measured metrics to ``micro_scores``. The default threshold is 0 because the
    gate belongs on the dataset score.

    Args:
        threshold: The minimum case score that counts as success.
    """
    return ScoreMetric("Entity quality", _score_entities, threshold)


def relation_quality_metric(
    *, symmetric_labels: frozenset[str] = frozenset(), threshold: float = 0.0
) -> ScoreMetric:
    """Build a metric for relation triple F1 on one test case.

    A relation counts only when both endpoints align to gold entities and the
    triple is in gold. Use a new metric for each case.

    Args:
        symmetric_labels: Relation labels with no direction. Their two endpoints
            are sorted before comparison.
        threshold: The minimum case score that counts as success.
    """

    def scorer(test_case: LLMTestCase) -> ScoreResult:
        return _score_relations(test_case, symmetric_labels)

    return ScoreMetric("Relation quality", scorer, threshold)


def micro_scores(metrics: Iterable[ScoreMetric]) -> MicroScores:
    """Pool measured entity and relation metrics into dataset scores.

    Args:
        metrics: Metrics from ``entity_quality_metric`` and
            ``relation_quality_metric``, after ``measure``.

    Raises:
        ValueError: No entity metric or no relation metric was given.
    """
    pooled: dict[tuple[str, str], tuple[list[int], list[int]]] = {
        (kind, mode): ([], []) for kind in (_ENTITY, _RELATION) for mode in _MODES
    }
    seen: set[str] = set()
    for metric in metrics:
        breakdown = metric.score_breakdown
        seen.add(breakdown["kind"])
        for mode in _MODES:
            y_true, y_pred = pooled[(breakdown["kind"], mode)]
            y_true += breakdown[f"{mode}y_true"]
            y_pred += breakdown[f"{mode}y_pred"]
    for kind in (_ENTITY, _RELATION):
        if kind not in seen:
            raise ValueError(f"no measured {kind} metric to pool")
    return MicroScores(
        entities_exact=_scores(*pooled[(_ENTITY, "")]),
        entities_relaxed=_scores(*pooled[(_ENTITY, "relaxed_")]),
        relations_exact=_scores(*pooled[(_RELATION, "")]),
        relations_relaxed=_scores(*pooled[(_RELATION, "relaxed_")]),
    )


def _overlap(a: ExtractedEntity, b: ExtractedEntity) -> float:
    """Return the intersection over union of two character spans."""
    inside = min(a.char_end, b.char_end) - max(a.char_start, b.char_start)
    if inside <= 0:
        return 0.0
    return inside / (max(a.char_end, b.char_end) - min(a.char_start, b.char_start))


def _align(
    predicted: list[ExtractedEntity], gold: list[ExtractedEntity], min_overlap: float
) -> dict[int, int]:
    """Map predicted entity indices to gold indices, one to one, best overlap first."""
    candidates = sorted(
        (
            (-_overlap(p, g), i, j)
            for i, p in enumerate(predicted)
            for j, g in enumerate(gold)
            if p.label == g.label
        ),
    )
    aligned: dict[int, int] = {}
    taken: set[int] = set()
    for negative_overlap, i, j in candidates:
        if -negative_overlap < min_overlap:
            break
        if i not in aligned and j not in taken:
            aligned[i] = j
            taken.add(j)
    return aligned


def _encode(
    true_positives: int, false_positives: int, false_negatives: int
) -> tuple[list[int], list[int]]:
    """Return 0/1 label lists over the union of gold and predicted items."""
    y_true = [1] * true_positives + [0] * false_positives + [1] * false_negatives
    y_pred = [1] * true_positives + [1] * false_positives + [0] * false_negatives
    return y_true, y_pred


def _scores(y_true: list[int], y_pred: list[int]) -> Scores:
    """Score label lists. No gold and no predictions is a perfect score."""
    if not y_true:
        return Scores(precision=1.0, recall=1.0, f1=1.0)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    return Scores(precision=float(precision), recall=float(recall), f1=float(f1))


def _triple(
    source: int, label: str, target: int, symmetric: frozenset[str]
) -> tuple[int, str, int]:
    """Return the comparison key of a relation, sorting endpoints if symmetric."""
    if label in symmetric and source > target:
        source, target = target, source
    return (source, label, target)


def _entity_breakdown(
    predicted: ExtractionResult, gold: ExtractionResult, min_overlap: float
) -> tuple[list[int], list[int], dict[str, dict[str, int]]]:
    """Return label lists and per-label counts for one alignment mode."""
    aligned = _align(predicted.entities, gold.entities, min_overlap)
    hits = len(aligned)
    y_true, y_pred = _encode(
        hits, len(predicted.entities) - hits, len(gold.entities) - hits
    )
    per_label: dict[str, dict[str, int]] = {}
    for label in {e.label for e in (*predicted.entities, *gold.entities)}:
        per_label[label] = {"tp": 0, "fp": 0, "fn": 0}
    for i, entity in enumerate(predicted.entities):
        per_label[entity.label]["tp" if i in aligned else "fp"] += 1
    gold_hits = set(aligned.values())
    for j, entity in enumerate(gold.entities):
        if j not in gold_hits:
            per_label[entity.label]["fn"] += 1
    return y_true, y_pred, per_label


def _score_entities(test_case: LLMTestCase) -> ScoreResult:
    """Score the entities of one case with exact and relaxed alignment."""
    predicted, gold = parse_json_case(test_case, ExtractionResult)
    y_true, y_pred, per_label = _entity_breakdown(predicted, gold, 1.0)
    relaxed_true, relaxed_pred, _ = _entity_breakdown(
        predicted, gold, _RELAXED_MIN_OVERLAP
    )
    exact = _scores(y_true, y_pred)
    relaxed = _scores(relaxed_true, relaxed_pred)
    return ScoreResult(
        exact.f1,
        f"exact F1 {exact.f1:.2f}, relaxed F1 {relaxed.f1:.2f}",
        {
            "kind": _ENTITY,
            "y_true": y_true,
            "y_pred": y_pred,
            "relaxed_y_true": relaxed_true,
            "relaxed_y_pred": relaxed_pred,
            "per_label": per_label,
        },
    )


def _relation_labels(
    predicted: ExtractionResult,
    gold: ExtractionResult,
    min_overlap: float,
    symmetric: frozenset[str],
) -> tuple[list[int], list[int]]:
    """Return label lists for the relation triples of one alignment mode."""
    aligned = _align(predicted.entities, gold.entities, min_overlap)
    gold_triples = {
        _triple(r.source_index, r.label, r.target_index, symmetric)
        for r in gold.relations
    }
    matched: set[tuple[int, str, int] | None] = set()
    false_positives = 0
    for relation in predicted.relations:
        source = aligned.get(relation.source_index)
        target = aligned.get(relation.target_index)
        triple = (
            None
            if source is None or target is None
            else _triple(source, relation.label, target, symmetric)
        )
        if triple in gold_triples and triple not in matched:
            matched.add(triple)
        else:
            false_positives += 1
    return _encode(len(matched), false_positives, len(gold_triples) - len(matched))


def _score_relations(test_case: LLMTestCase, symmetric: frozenset[str]) -> ScoreResult:
    """Score the relation triples of one case with exact and relaxed alignment."""
    predicted, gold = parse_json_case(test_case, ExtractionResult)
    y_true, y_pred = _relation_labels(predicted, gold, 1.0, symmetric)
    relaxed_true, relaxed_pred = _relation_labels(
        predicted, gold, _RELAXED_MIN_OVERLAP, symmetric
    )
    exact = _scores(y_true, y_pred)
    relaxed = _scores(relaxed_true, relaxed_pred)
    return ScoreResult(
        exact.f1,
        f"exact F1 {exact.f1:.2f}, relaxed F1 {relaxed.f1:.2f}",
        {
            "kind": _RELATION,
            "y_true": y_true,
            "y_pred": y_pred,
            "relaxed_y_true": relaxed_true,
            "relaxed_y_pred": relaxed_pred,
        },
    )
