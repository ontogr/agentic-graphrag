"""Tests for the pure escalation rules.

Chunks and results are built by hand. No extractor runs. The tests pin the
eligibility rules, the ranking, the budget ceiling, and the report lines.
"""

import hashlib
from typing import Literal
from uuid import uuid4

import pytest

from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    PropertySpec,
)
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion._escalation import (
    accept_escalated,
    budget_limit,
    combine_results,
    format_escalation,
    kept_entities,
    labels_with_properties,
    plan_escalation,
    select_for_escalation,
)
from agrag.ingestion.reports.escalation_report import EscalationReport
from agrag.ingestion.settings import ExtractionSettings


_LONG = "one two three four five six seven eight nine ten"
_SHORT = "one two three"


def _chunk(text: str = _LONG) -> Chunk:
    """Build a chunk with the given text."""
    return Chunk(
        id=uuid4(),
        document_id=uuid4(),
        text=text,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )


def _result(
    chunk: Chunk, *scores: float | None, label: str = "Person", name: str = "gliner"
) -> ExtractionResult:
    """Build a result with one entity per score, in order."""
    return ExtractionResult(
        entities=[
            ExtractedEntity(
                chunk_id=chunk.id,
                label=label,
                text=f"e{position}",
                char_start=position * 3,
                char_end=position * 3 + 2,
                confidence=score,
            )
            for position, score in enumerate(scores)
        ],
        relations=[],
        extractor_name=name,
    )


def _with_relation(result: ExtractionResult) -> ExtractionResult:
    """Return the result with one relation between its first two entities."""
    relation = ExtractedRelation(
        chunk_id=result.entities[0].chunk_id,
        label="RELATED_TO",
        source_index=0,
        target_index=1,
    )
    return result.model_copy(update={"relations": [relation]})


def _select(
    scores_per_chunk: list[tuple[float | None, ...]],
    *,
    budget: float | Literal["all"] = "all",
    text: str = _LONG,
) -> list[int]:
    """Select from chunks that each carry the given entity scores."""
    chunks = [_chunk(text) for _ in scores_per_chunk]
    results = [_result(c, *s) for c, s in zip(chunks, scores_per_chunk, strict=True)]
    settings = ExtractionSettings(escalation_budget=budget)
    return select_for_escalation(
        results, settings, chunks=chunks, property_labels=frozenset()
    )


class TestRanking:
    """Eligible chunks rank by relation evidence, then weakest score, then order."""

    def test_weakest_minimum_score_comes_first(self) -> None:
        """A chunk ranks by its lowest span score."""
        assert _select([(0.7,), (0.55,), (0.65,)]) == [1, 2, 0]

    def test_one_weak_span_among_strong_spans_makes_the_chunk_eligible(self) -> None:
        """The minimum decides, so a strong mean does not hide a weak span."""
        assert _select([(0.99, 0.99, 0.6), (0.95,)]) == [0]

    def test_ties_break_by_chunk_order(self) -> None:
        """Equal scores keep the order of the chunks in the batch."""
        assert _select([(0.6,), (0.6,), (0.6,)]) == [0, 1, 2]

    def test_zero_entity_chunks_rank_last(self) -> None:
        """A long chunk with no entities ranks after every scored chunk."""
        chunks = [_chunk(), _chunk(), _chunk()]
        results = [
            _result(chunks[0]),
            _result(chunks[1], 0.7),
            _result(chunks[2], 0.5),
        ]

        selected = select_for_escalation(
            results,
            ExtractionSettings(escalation_budget="all"),
            chunks=chunks,
            property_labels=frozenset(),
        )

        assert selected == [2, 1, 0]

    def test_property_only_chunks_rank_after_weak_chunks(self) -> None:
        """A strong chunk with a property type ranks after a weak chunk."""
        chunks = [_chunk(), _chunk()]
        results = [_result(chunks[0], 0.99, label="Contract"), _result(chunks[1], 0.7)]

        selected = select_for_escalation(
            results,
            ExtractionSettings(escalation_budget="all"),
            chunks=chunks,
            property_labels=frozenset({"Contract"}),
        )

        assert selected == [1, 0]

    @staticmethod
    def test_two_kept_spans_without_relations_rank_first() -> None:
        """A chunk with two kept spans and no relation ranks ahead of a weak one."""
        chunks = [_chunk(), _chunk()]
        results = [
            _result(chunks[0], 0.95, 0.9, label="Contract"),
            _with_relation(_result(chunks[1], 0.5, 0.9)),
        ]

        selected = select_for_escalation(
            results,
            ExtractionSettings(escalation_budget=0.5),
            chunks=chunks,
            property_labels=frozenset({"Contract"}),
        )

        assert selected == [0]

    @staticmethod
    def test_relation_free_chunks_rank_by_weakest_score() -> None:
        """Within the relation-free group, the weaker chunk ranks first."""
        chunks = [_chunk(), _chunk()]
        results = [
            _result(chunks[0], 0.95, 0.8, label="Contract"),
            _result(chunks[1], 0.95, 0.7, label="Contract"),
        ]

        selected = select_for_escalation(
            results,
            ExtractionSettings(escalation_budget="all"),
            chunks=chunks,
            property_labels=frozenset({"Contract"}),
        )

        assert selected == [1, 0]

    @staticmethod
    def test_single_kept_span_without_relation_does_not_rank_first() -> None:
        """One kept span with no relation stays behind a chunk with a relation."""
        chunks = [_chunk(), _chunk()]
        results = [
            _result(chunks[0], 0.99, label="Contract"),
            _with_relation(_result(chunks[1], 0.6, 0.9)),
        ]

        selected = select_for_escalation(
            results,
            ExtractionSettings(escalation_budget="all"),
            chunks=chunks,
            property_labels=frozenset({"Contract"}),
        )

        assert selected == [1, 0]

    @staticmethod
    def test_without_relations_single_span_chunks_rank_weakest_first() -> None:
        """Without relations, single kept spans rank weakest first, then no span."""
        chunks = [_chunk() for _ in range(4)]
        results = [
            _result(chunks[0], 0.7),
            _result(chunks[1], 0.55),
            _result(chunks[2], 0.65),
            _result(chunks[3]),
        ]

        selected = select_for_escalation(
            results,
            ExtractionSettings(escalation_budget="all"),
            chunks=chunks,
            property_labels=frozenset(),
        )

        assert selected == [1, 2, 0, 3]

    @staticmethod
    def test_zero_relation_count_includes_chunks_the_budget_cuts() -> None:
        """Eligible relation-free chunks are counted even when the budget cuts them."""
        chunks = [_chunk() for _ in range(4)]
        results = [
            _result(chunks[0], 0.95, 0.9, label="Contract"),
            _result(chunks[1], 0.95, 0.8, label="Contract"),
            _with_relation(_result(chunks[2], 0.5, 0.9)),
            _result(chunks[3], 0.95, 0.9),
        ]

        plan = plan_escalation(
            results,
            ExtractionSettings(escalation_budget=0.25),
            chunks=chunks,
            property_labels=frozenset({"Contract"}),
        )

        assert len(plan.selected) == 1
        assert plan.zero_relation == 2


class TestEligibility:
    """The eligibility cases of the escalation rule."""

    @pytest.mark.parametrize(
        ("scores", "text", "expected"),
        [
            pytest.param((0.9,), _LONG, [], id="strong-span"),
            pytest.param((0.75,), _LONG, [], id="exactly-at-threshold-is-not-weak"),
            pytest.param((0.7499,), _LONG, [0], id="just-below-threshold"),
            pytest.param((None,), _LONG, [], id="no-score-is-not-weak"),
            pytest.param((), _LONG, [0], id="zero-entities-long-chunk"),
            pytest.param((), _SHORT, [], id="zero-entities-short-chunk"),
            pytest.param((0.4,), _LONG, [0], id="only-a-band-span-long-chunk"),
            pytest.param((0.4,), _SHORT, [], id="only-a-band-span-short-chunk"),
        ],
    )
    def test_cases(
        self, scores: tuple[float | None, ...], text: str, expected: list[int]
    ) -> None:
        """Each case is eligible or not as the rule says."""
        assert _select([scores], text=text) == expected

    def test_a_band_span_does_not_make_a_chunk_eligible_on_its_own(self) -> None:
        """A strong kept span plus a band span is not eligible."""
        assert _select([(0.9, 0.4)]) == []

    def test_band_span_does_not_count_as_a_kept_entity(self) -> None:
        """A chunk whose only span is in the band is a zero-yield chunk.

        It ranks in the zero-yield group, after a chunk with a weak kept span.
        """
        chunks = [_chunk(), _chunk()]
        results = [_result(chunks[0], 0.4), _result(chunks[1], 0.6)]

        selected = select_for_escalation(
            results,
            ExtractionSettings(escalation_budget="all"),
            chunks=chunks,
            property_labels=frozenset(),
        )

        assert selected == [1, 0]

    def test_failed_chunk_is_not_eligible(self) -> None:
        """A chunk whose primary extraction failed has no result to rank."""
        chunks = [_chunk(), _chunk()]
        results: list[ExtractionResult | None] = [None, _result(chunks[1], 0.5)]

        selected = select_for_escalation(
            results,
            ExtractionSettings(escalation_budget="all"),
            chunks=chunks,
            property_labels=frozenset(),
        )

        assert selected == [1]

    def test_property_type_makes_a_strong_chunk_eligible(self) -> None:
        """A kept span of a type that declares properties escalates."""
        chunk = _chunk()

        selected = select_for_escalation(
            [_result(chunk, 0.99, label="Contract")],
            ExtractionSettings(escalation_budget="all"),
            chunks=[chunk],
            property_labels=frozenset({"Contract"}),
        )

        assert selected == [0]

    def test_labels_with_properties_includes_children_of_a_property_type(self) -> None:
        """A child of a type that declares properties counts as one too."""
        schema = GraphSchema(
            name="s",
            version="1",
            entities=[
                EntityType(
                    label="Agreement",
                    description="A signed agreement.",
                    properties={"value": PropertySpec(type="string")},
                ),
                EntityType(
                    label="Lease",
                    description="A lease.",
                    parents=["Agreement"],
                ),
                EntityType(label="Person", description="A person."),
            ],
            relations=[],
        )

        assert labels_with_properties(schema) == frozenset({"Agreement", "Lease"})


class TestBudget:
    """The budget cuts the ranked list."""

    def test_budget_zero_selects_nothing(self) -> None:
        """Budget 0 means GLiNER only."""
        assert _select([(0.5,), (0.5,)], budget=0.0) == []

    def test_budget_all_selects_every_eligible_chunk(self) -> None:
        """Budget all has no ceiling."""
        assert _select([(0.5,)] * 7 + [(0.9,)], budget="all") == list(range(7))

    def test_share_of_the_batch_not_of_the_eligible_chunks(self) -> None:
        """Twenty percent of 10 chunks is 2, even when 8 are eligible."""
        scores = [(0.5 + i / 100,) for i in range(8)] + [(0.9,), (0.9,)]

        assert _select(scores, budget=0.2) == [0, 1]

    def test_budget_never_exceeds_the_eligible_count(self) -> None:
        """A large budget cannot escalate an ineligible chunk."""
        assert _select([(0.5,), (0.9,)], budget=1.0) == [0]

    def test_small_batch_rounds_up_to_one_call(self) -> None:
        """Twenty percent of 3 chunks rounds up, so one chunk escalates."""
        assert _select([(0.5,), (0.6,), (0.7,)], budget=0.2) == [0]

    @pytest.mark.parametrize(
        ("total", "eligible", "budget", "expected"),
        [
            (30, 30, 0.1, 3),
            (1240, 410, 0.2, 248),
            (10, 4, 0.2, 2),
            (5, 5, 0.0, 0),
            (5, 3, "all", 3),
            (0, 0, 0.2, 0),
            (3, 2, 0.01, 1),
            (3, 0, 0.5, 0),
        ],
    )
    def test_budget_limit(
        self,
        total: int,
        eligible: int,
        budget: float | Literal["all"],
        expected: int,
    ) -> None:
        """The limit is the ceiling of the share, capped by the eligible count."""
        assert budget_limit(total, eligible, budget) == expected

    def test_budget_needed_escalates_every_eligible_chunk(self) -> None:
        """A budget equal to the reported need escalates every eligible chunk."""
        chunks = [_chunk() for _ in range(37)]
        results = [_result(c, 0.5 if i % 3 == 0 else 0.9) for i, c in enumerate(chunks)]

        plan = plan_escalation(
            results,
            ExtractionSettings(escalation_budget=0.36),
            chunks=chunks,
            property_labels=frozenset(),
        )

        assert plan.report(len(chunks)).budget_needed == pytest.approx(13 / 37)
        assert len(plan.selected) == 13


class TestPlanReport:
    """The plan turns into the contract's report fields."""

    def test_report_counts_and_lowest_score_left(self) -> None:
        """Left-over chunks report the lowest score among them."""
        chunks = [_chunk() for _ in range(5)]
        results = [
            _result(c, s)
            for c, s in zip(chunks, (0.5, 0.6, 0.7, 0.9, 0.95), strict=True)
        ]
        settings = ExtractionSettings(escalation_budget=0.4)

        report = plan_escalation(
            results, settings, chunks=chunks, property_labels=frozenset()
        ).report(len(chunks))

        assert report == EscalationReport(
            total=5,
            eligible=3,
            escalated=2,
            left_for_gliner=1,
            lowest_score_left=0.7,
            budget_needed=3 / 5,
        )

    def test_nothing_left_reports_no_lowest_score(self) -> None:
        """When the budget covers all eligible chunks, no score is left."""
        chunk = _chunk()

        report = plan_escalation(
            [_result(chunk, 0.5)],
            ExtractionSettings(escalation_budget="all"),
            chunks=[chunk],
            property_labels=frozenset(),
        ).report(1)

        assert report.left_for_gliner == 0
        assert report.lowest_score_left is None

    def test_empty_batch_reports_zero_need(self) -> None:
        """A batch with no chunks has total 0 and budget_needed 0."""
        report = plan_escalation(
            [], ExtractionSettings(), chunks=[], property_labels=frozenset()
        ).report(0)

        assert report == EscalationReport()


class TestFormatEscalation:
    """The log lines follow the documented format."""

    def test_full_example(self) -> None:
        """All five lines appear when a run has left-over chunks and failures."""
        report = EscalationReport(
            mode="hybrid",
            total=1240,
            eligible=410,
            escalated=248,
            left_for_gliner=162,
            lowest_score_left=0.62,
            failed=3,
            budget_needed=410 / 1240,
            primary_seconds=41.23,
            escalation_seconds=96.8,
        )

        assert format_escalation(report, ExtractionSettings(escalation_budget=0.2)) == [
            "mode hybrid | chunks 1,240 | eligible 410 (33%) | "
            "escalated 248 (budget 20%)",
            "left for GLiNER only 162 | lowest score left 0.62",
            "budget needed 34% to escalate all eligible chunks",
            "escalation failed on 3 chunks | first result kept",
            "time first extractor 41.2s | escalation 96.8s",
        ]

    def test_only_the_first_line_when_nothing_is_left(self) -> None:
        """No left-over chunks means no second or third line."""
        report = EscalationReport(
            mode="hybrid", total=10, eligible=2, escalated=2, budget_needed=0.2
        )

        assert format_escalation(report, ExtractionSettings(escalation_budget=0.2)) == [
            "mode hybrid | chunks 10 | eligible 2 (20%) | escalated 2 (budget 20%)"
        ]

    def test_budget_all_and_missing_score(self) -> None:
        """Budget all prints as all, and a missing score drops that part."""
        report = EscalationReport(
            mode="hybrid",
            total=4,
            eligible=2,
            escalated=1,
            left_for_gliner=1,
            budget_needed=0.5,
        )

        assert format_escalation(
            report, ExtractionSettings(escalation_budget="all")
        ) == [
            "mode hybrid | chunks 4 | eligible 2 (50%) | escalated 1 (budget all)",
            "left for GLiNER only 1",
            "budget needed 50% to escalate all eligible chunks",
        ]

    def test_gliner_mode_omits_budget_and_escalation(self) -> None:
        """Gliner mode prints the mode and the chunk count only."""
        report = EscalationReport(mode="gliner", total=1240, primary_seconds=41.23)

        assert format_escalation(report, ExtractionSettings(escalation_budget=0.2)) == [
            "mode gliner | chunks 1,240",
            "time first extractor 41.2s | escalation 0.0s",
        ]

    def test_llm_mode_shows_skipped_short_and_failures(self) -> None:
        """Llm mode counts the short chunks and names the failed LLM calls."""
        report = EscalationReport(
            mode="llm",
            total=1240,
            skipped_short=200,
            eligible=1040,
            escalated=1040,
            failed=3,
        )

        assert format_escalation(report, ExtractionSettings(escalation_budget=0.2)) == [
            "mode llm | chunks 1,240 | skipped short 200 | escalated 1,040",
            "llm failed on 3 chunks",
        ]

    def test_empty_report_logs_nothing(self) -> None:
        """A run with no chunks has nothing to say."""
        assert format_escalation(EscalationReport(), ExtractionSettings()) == []


class TestAcceptEscalated:
    """An empty LLM answer never wipes out entities that GLiNER found."""

    @pytest.mark.parametrize(
        ("first_scores", "llm_scores", "expected"),
        [
            pytest.param((0.5,), (None,), True, id="llm-found-entities"),
            pytest.param((), (None,), True, id="llm-found-entities-first-empty"),
            pytest.param((0.5,), (), False, id="empty-answer-first-has-entities"),
            pytest.param((), (), True, id="both-empty"),
        ],
    )
    def test_cases(
        self,
        first_scores: tuple[float | None, ...],
        llm_scores: tuple[float | None, ...],
        expected: bool,
    ) -> None:
        """The answer is accepted unless it is empty and the first result is not."""
        chunk = _chunk()

        assert (
            accept_escalated(
                _result(chunk, *first_scores),
                _result(chunk, *llm_scores, name="llm"),
            )
            is expected
        )


class TestCombineResults:
    """A non-empty LLM answer is united with GLiNER's result."""

    @staticmethod
    def _llm_entity(
        chunk: Chunk,
        text: str,
        label: str = "Person",
        *,
        start: int = 50,
        properties: dict[str, object] | None = None,
    ) -> ExtractedEntity:
        return ExtractedEntity(
            chunk_id=chunk.id,
            label=label,
            text=text,
            char_start=start,
            char_end=start + len(text),
            confidence=None,
            properties=properties or {},
        )

    def test_first_entities_the_llm_did_not_return_are_kept(self) -> None:
        """GLiNER entities that the LLM did not return follow the LLM entities."""
        chunk = _chunk()
        primary = _result(chunk, 0.6, 0.55, name="gliner")
        llm = ExtractionResult(
            entities=[self._llm_entity(chunk, "e0")],
            relations=[],
            extractor_name="baml",
        )

        combined = combine_results(primary, llm)

        assert [e.text for e in combined.entities] == ["e0", "e1"]
        assert combined.extractor_name == "baml"

    def test_span_and_confidence_are_copied_by_normalized_name(self) -> None:
        """Case and spacing do not matter; GLiNER's span, text and score win."""
        chunk = _chunk()
        first = ExtractedEntity(
            chunk_id=chunk.id,
            label="Person",
            text="Ada Lovelace",
            char_start=4,
            char_end=16,
            confidence=0.62,
        )
        primary = ExtractionResult(
            entities=[first], relations=[], extractor_name="gliner"
        )
        llm = ExtractionResult(
            entities=[self._llm_entity(chunk, "ADA   lovelace", properties={"k": 1})],
            relations=[],
            extractor_name="baml",
        )

        (entity,) = combine_results(primary, llm).entities

        assert (entity.text, entity.char_start, entity.char_end) == (
            "Ada Lovelace",
            4,
            16,
        )
        assert entity.confidence == 0.62
        assert entity.properties == {"k": 1}

    def test_llm_label_wins_on_a_conflict(self) -> None:
        """The same name with another label keeps the LLM's label."""
        chunk = _chunk()
        primary = ExtractionResult(
            entities=[
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label="Product",
                    text="Acme",
                    char_start=0,
                    char_end=4,
                    confidence=0.7,
                )
            ],
            relations=[],
            extractor_name="gliner",
        )
        llm = ExtractionResult(
            entities=[self._llm_entity(chunk, "Acme", "Organization")],
            relations=[],
            extractor_name="baml",
        )

        (entity,) = combine_results(primary, llm).entities

        assert entity.label == "Organization"
        assert entity.confidence == 0.7

    def test_entity_the_first_extractor_lacked_has_no_confidence(self) -> None:
        """An LLM-only entity keeps its own offsets and gets no confidence."""
        chunk = _chunk()
        primary = _result(chunk, 0.6, name="gliner")
        scored_llm_entity = self._llm_entity(chunk, "Grace", start=30).model_copy(
            update={"confidence": 0.9}
        )
        llm = ExtractionResult(
            entities=[scored_llm_entity],
            relations=[],
            extractor_name="baml",
        )

        entity = combine_results(primary, llm).entities[0]

        assert entity.confidence is None
        assert (entity.char_start, entity.char_end) == (30, 35)

    def test_llm_relations_keep_their_indices(self) -> None:
        """The LLM's relations stay valid because its entity order is kept."""
        chunk = _chunk()
        primary = _result(chunk, 0.6, name="gliner")
        llm = ExtractionResult(
            entities=[
                self._llm_entity(chunk, "Ada"),
                self._llm_entity(chunk, "Acme", "Organization", start=70),
            ],
            relations=[
                ExtractedRelation(
                    chunk_id=chunk.id, label="WORKS_AT", source_index=0, target_index=1
                )
            ],
            extractor_name="baml",
        )

        combined = combine_results(primary, llm)

        triples = [
            (r.label, r.source_index, r.target_index) for r in combined.relations
        ]
        assert triples == [("WORKS_AT", 0, 1)]

    def test_mentions_with_the_same_name_keep_their_own_measurements(self) -> None:
        """Two first-result mentions with one name do not share a measurement."""
        chunk = _chunk()
        first_ada = ExtractedEntity(
            chunk_id=chunk.id,
            label="Person",
            text="Ada",
            char_start=0,
            char_end=3,
            confidence=0.6,
        )
        second_ada = first_ada.model_copy(
            update={"char_start": 10, "char_end": 13, "confidence": 0.9}
        )
        primary = ExtractionResult(
            entities=[first_ada, second_ada],
            relations=[
                ExtractedRelation(
                    chunk_id=chunk.id, label="KNOWS", source_index=1, target_index=0
                )
            ],
            extractor_name="gliner",
        )
        llm = ExtractionResult(
            entities=[self._llm_entity(chunk, "Ada")],
            relations=[],
            extractor_name="baml",
        )

        combined = combine_results(primary, llm)

        spans = [(e.char_start, e.confidence) for e in combined.entities]
        assert spans == [(0, 0.6), (10, 0.9)]
        triples = [
            (r.label, r.source_index, r.target_index) for r in combined.relations
        ]
        assert triples == [("KNOWS", 1, 0)]

    def test_first_relations_are_added_with_new_indices(self) -> None:
        """A GLiNER relation is re-pointed to the combined list.

        A relation the LLM already returned is not added a second time.
        """
        chunk = _chunk()
        primary = ExtractionResult(
            entities=[
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label="Person",
                    text="Ada",
                    char_start=0,
                    char_end=3,
                    confidence=0.8,
                ),
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label="Organization",
                    text="Acme",
                    char_start=10,
                    char_end=14,
                    confidence=0.7,
                ),
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label="Location",
                    text="Paris",
                    char_start=20,
                    char_end=25,
                    confidence=0.9,
                ),
            ],
            relations=[
                ExtractedRelation(
                    chunk_id=chunk.id, label="WORKS_AT", source_index=0, target_index=1
                ),
                ExtractedRelation(
                    chunk_id=chunk.id,
                    label="LOCATED_IN",
                    source_index=1,
                    target_index=2,
                ),
            ],
            extractor_name="gliner",
        )
        llm = ExtractionResult(
            entities=[
                self._llm_entity(chunk, "Acme", "Organization"),
                self._llm_entity(chunk, "Ada"),
            ],
            relations=[
                ExtractedRelation(
                    chunk_id=chunk.id, label="WORKS_AT", source_index=1, target_index=0
                )
            ],
            extractor_name="baml",
        )

        combined = combine_results(primary, llm)

        assert [e.text for e in combined.entities] == ["Acme", "Ada", "Paris"]
        triples = [
            (r.label, r.source_index, r.target_index) for r in combined.relations
        ]
        assert triples == [("WORKS_AT", 1, 0), ("LOCATED_IN", 0, 2)]

    def test_empty_answer_keeps_the_first_result_entirely(self) -> None:
        """An empty LLM answer returns GLiNER's result unchanged."""
        chunk = _chunk()
        primary = _result(chunk, 0.6, name="gliner")
        llm = ExtractionResult(entities=[], relations=[], extractor_name="baml")

        assert combine_results(primary, llm) is primary

    def test_candidates_of_both_results_are_kept(self) -> None:
        """Band spans from GLiNER survive the merge."""
        chunk = _chunk()
        band = CandidateRecord(
            kind="entity",
            label="Person",
            text="Ada",
            confidence=0.4,
            reason="entity_band",
            chunk_id=chunk.id,
        )
        primary = _result(chunk, 0.6, name="gliner").model_copy(
            update={"candidates": [band]}
        )
        llm = ExtractionResult(
            entities=[self._llm_entity(chunk, "e0")],
            relations=[],
            extractor_name="baml",
        )

        assert combine_results(primary, llm).candidates == [band]


class TestKeptEntities:
    """Kept entities are the candidates that phase 2 passes to the LLM."""

    def test_band_entities_are_not_kept(self) -> None:
        """Only entities at or above the entity threshold, or unscored, are kept."""
        chunk = _chunk()

        kept = kept_entities(_result(chunk, 0.9, 0.4, None), ExtractionSettings())

        assert [e.confidence for e in kept] == [0.9, None]

    def test_label_threshold_replaces_the_entity_threshold(self) -> None:
        """A span kept by its label's threshold stays a candidate."""
        chunk = _chunk()
        settings = ExtractionSettings(label_thresholds={"Person": 0.2})

        kept = kept_entities(_result(chunk, 0.3, label="Person"), settings)

        assert [e.confidence for e in kept] == [0.3]
