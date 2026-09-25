"""Tests for the extraction quality metrics.

Each test builds a predicted and a gold ``ExtractionResult`` for one chunk,
measures a fresh metric on them, and reads the scores back. No model runs.
"""

from uuid import UUID

import pytest
from deepeval.test_case import LLMTestCase

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.eval.extraction import (
    ExtractionGold,
    MicroScores,
    entity_quality_metric,
    extraction_case,
    micro_scores,
    relation_quality_metric,
    run_extractor,
)
from agrag.ingestion.extract import Extractor


CHUNK_ID = UUID(int=1)


def entity(label: str, start: int, end: int) -> ExtractedEntity:
    """Build a gold or predicted entity span."""
    return ExtractedEntity(
        chunk_id=CHUNK_ID, label=label, text="x", char_start=start, char_end=end
    )


def relation(label: str, source: int, target: int) -> ExtractedRelation:
    """Build a relation between two entity positions."""
    return ExtractedRelation(
        chunk_id=CHUNK_ID, label=label, source_index=source, target_index=target
    )


def result(
    entities: list[ExtractedEntity], relations: list[ExtractedRelation] | None = None
) -> ExtractionResult:
    """Build an extraction result for the fixed test chunk."""
    return ExtractionResult(
        entities=entities, relations=relations or [], extractor_name="test"
    )


def entity_f1(
    predicted: ExtractionResult, gold: ExtractionResult
) -> tuple[float, float]:
    """Return the exact and relaxed entity F1 of one case."""
    scores = pooled([extraction_case("text", predicted, gold)])
    return scores.entities_exact.f1, scores.entities_relaxed.f1


def pooled(cases: list[LLMTestCase]) -> MicroScores:
    """Measure both metrics on every case and pool them."""
    metrics = []
    for case in cases:
        for build in (entity_quality_metric, relation_quality_metric):
            metric = build()
            metric.measure(case)
            metrics.append(metric)
    return micro_scores(metrics)


def relation_score(
    predicted: ExtractionResult,
    gold: ExtractionResult,
    symmetric: frozenset[str] = frozenset(),
) -> float:
    """Return the exact relation F1 of one case."""
    metric = relation_quality_metric(symmetric_labels=symmetric)
    return metric.measure(extraction_case("text", predicted, gold))


class TestEntityQuality:
    """Entity F1 aligns predictions to gold one to one."""

    def test_one_trailing_character_counts_only_when_relaxed(self) -> None:
        """A span one character too long misses exact and hits relaxed."""
        exact, relaxed = entity_f1(
            result([entity("kpi", 0, 10)]), result([entity("kpi", 0, 9)])
        )

        assert exact == 0.0
        assert relaxed == 1.0

    def test_same_span_with_another_label_does_not_align(self) -> None:
        """The label must match even when the span is identical."""
        exact, relaxed = entity_f1(
            result([entity("cy", 0, 5)]), result([entity("py", 0, 5)])
        )

        assert exact == 0.0
        assert relaxed == 0.0

    def test_two_predictions_on_one_gold_span_leave_one_false_positive(self) -> None:
        """One prediction is a true positive and the other a false positive."""
        exact, _ = entity_f1(
            result([entity("kpi", 0, 5), entity("kpi", 0, 5)]),
            result([entity("kpi", 0, 5)]),
        )

        # precision 1/2, recall 1 -> F1 2/3
        assert exact == pytest.approx(2 / 3)

    @pytest.mark.parametrize(("predicted_end", "aligned"), [(2, True), (1, False)])
    def test_overlap_of_half_aligns_and_less_does_not(
        self, predicted_end: int, aligned: bool
    ) -> None:
        """Overlap exactly 0.5 aligns in relaxed mode. Just under does not."""
        gold = result([entity("kpi", 0, 4)])

        _, relaxed = entity_f1(result([entity("kpi", 0, predicted_end)]), gold)

        assert (relaxed == 1.0) is aligned

    def test_best_overlap_wins_a_contested_gold_entity(self) -> None:
        """Of two overlapping predictions, the closer one takes the gold entity."""
        metric = entity_quality_metric()
        gold = result([entity("kpi", 0, 10)])
        predicted = result([entity("kpi", 0, 6), entity("kpi", 0, 9)])

        metric.measure(extraction_case("text", predicted, gold))

        assert metric.score_breakdown["relaxed_y_pred"] == [1, 1]
        assert metric.score_breakdown["per_label"] == {
            "kpi": {"tp": 0, "fp": 2, "fn": 1}
        }

    def test_empty_prediction_and_gold_scores_one(self) -> None:
        """Nothing to find and nothing found is a perfect score."""
        assert entity_f1(result([]), result([]))[0] == 1.0

    def test_missing_every_gold_entity_scores_zero(self) -> None:
        """Gold present and nothing predicted scores 0."""
        assert entity_f1(result([]), result([entity("kpi", 0, 5)]))[0] == 0.0

    def test_predictions_with_no_gold_score_zero(self) -> None:
        """Nothing gold but predictions present scores 0."""
        assert entity_f1(result([entity("kpi", 0, 5)]), result([]))[0] == 0.0


class TestRelationQuality:
    """Relation F1 compares triples over the entity alignment."""

    GOLD = result([entity("kpi", 0, 5), entity("cy", 10, 15)], [relation("REL", 0, 1)])

    def test_matching_triple_scores_one(self) -> None:
        """A predicted relation between aligned endpoints matches gold."""
        predicted = result(
            [entity("kpi", 0, 5), entity("cy", 10, 15)], [relation("REL", 0, 1)]
        )

        assert relation_score(predicted, self.GOLD) == 1.0

    def test_relation_with_an_unaligned_endpoint_is_a_false_positive(self) -> None:
        """A relation to a wrong entity counts against precision."""
        predicted = result(
            [entity("kpi", 0, 5), entity("cy", 20, 25)], [relation("REL", 0, 1)]
        )

        assert relation_score(predicted, self.GOLD) == 0.0

    def test_reversed_endpoints_match_only_for_a_symmetric_label(self) -> None:
        """Endpoint order matters unless the label is declared symmetric."""
        predicted = result(
            [entity("cy", 10, 15), entity("kpi", 0, 5)], [relation("REL", 0, 1)]
        )

        assert relation_score(predicted, self.GOLD) == 0.0
        assert relation_score(predicted, self.GOLD, frozenset({"REL"})) == 1.0

    def test_both_empty_scores_one(self) -> None:
        """No gold relations and none predicted is a perfect score."""
        assert relation_score(result([]), result([])) == 1.0


class TestMicroScores:
    """Micro scores pool counts over chunks."""

    def test_differs_from_the_mean_of_case_scores(self) -> None:
        """A large chunk weighs more than a small one."""
        small_gold = result([entity("kpi", 0, 5)], [])
        large_gold = result([entity("kpi", i * 10, i * 10 + 5) for i in range(9)], [])
        cases = [
            # Small chunk: found nothing. Case F1 0.
            extraction_case("a", result([]), small_gold),
            # Large chunk: found all nine. Case F1 1.
            extraction_case("b", large_gold, large_gold),
        ]
        case_scores = []
        for case in cases:
            metric = entity_quality_metric()
            case_scores.append(metric.measure(case))

        scores = pooled(cases)

        assert sum(case_scores) / 2 == 0.5
        # 9 true positives, 1 false negative: precision 1, recall 0.9.
        assert scores.entities_exact.f1 == pytest.approx(2 * 1 * 0.9 / 1.9)
        assert scores.entities_exact.recall == pytest.approx(0.9)

    def test_needs_both_metric_kinds(self) -> None:
        """A run with no relation metric cannot gate."""
        metric = entity_quality_metric()
        metric.measure(extraction_case("a", result([]), result([])))

        with pytest.raises(ValueError, match="relation"):
            micro_scores([metric])


class _FixedExtractor(Extractor):
    """Extractor that returns one fixed entity for every chunk."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        assert chunk.id is not None
        entity_ = ExtractedEntity(
            chunk_id=chunk.id,
            label="kpi",
            text=chunk.text[:3],
            char_start=0,
            char_end=3,
        )
        return ExtractionResult(
            entities=[entity_], relations=[], extractor_name="fixed"
        )


class TestRunExtractor:
    """run_extractor builds one case per gold item, in order."""

    async def test_returns_one_case_per_item_in_order(self) -> None:
        """Predictions come from the extractor and gold from the item."""
        schema = GraphSchema(
            name="s",
            version="1",
            entities=[EntityType(label="kpi", description="d")],
            relations=[],
        )
        items = [
            ExtractionGold(
                id=f"item-{i}", text=f"text {i}", gold=result([entity("kpi", 0, 3)])
            )
            for i in range(20)
        ]

        cases = await run_extractor(_FixedExtractor(), items, schema)

        assert [case.input for case in cases] == [item.text for item in items]
        metric = entity_quality_metric()
        assert metric.measure(cases[0]) == 1.0

    @pytest.mark.parametrize("concurrency", [0, -1])
    async def test_rejects_concurrency_below_one(self, concurrency: int) -> None:
        """A zero limit would wait forever, so it raises before any call."""
        schema = GraphSchema(name="s", version="1", entities=[], relations=[])
        item = ExtractionGold(id="item", text="text", gold=result([]))

        with pytest.raises(ValueError, match="concurrency"):
            await run_extractor(
                _FixedExtractor(), [item], schema, concurrency=concurrency
            )
