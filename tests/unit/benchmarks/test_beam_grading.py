"""Tests the BEAM scorer and grader on canned judge replies and hand-worked orders."""

import hashlib
import json

import pytest

from benchmarks.grading.beam import BeamGrader
from benchmarks.grading.beam_scorer import (
    JudgeReplyError,
    align_with_llm,
    event_ordering_score,
    ordering_score,
    parse_json_response,
    rubric_score,
    unified_llm_judge_base_prompt,
)
from benchmarks.models import BenchmarkQuestion
from benchmarks.systems.base import SystemAnswer


class _Judge:
    """Answers each prompt with the first canned reply whose key is in the prompt."""

    def __init__(self, replies: dict[str, str]) -> None:
        self.replies = replies
        self.prompts: list[str] = []

    async def a_generate(self, prompt: str, schema=None) -> str:
        self.prompts.append(prompt)
        return next(reply for key, reply in self.replies.items() if key in prompt)


class _Equivalence:
    """Says YES when a (reference item, answer line) pair is in its match set."""

    def __init__(self, matches: set[tuple[str, str]]) -> None:
        self.matches = matches
        self.asked: list[tuple[str, str]] = []

    async def a_generate(self, prompt: str, schema=None) -> str:
        first = prompt.split("First snippet: ", 1)[1].split(" \n", 1)[0]
        second = prompt.split("Second snippet: ", 1)[1].rstrip("\n")
        self.asked.append((first, second))
        return "YES" if (first, second) in self.matches else "NO"


def _score(value: float) -> str:
    return json.dumps({"score": value, "reason": "r"})


class TestPrompt:
    """The judge prompt is the upstream text."""

    def test_matches_the_pinned_upstream_digest(self):
        """An edit to the ported prompt changes its digest."""
        digest = hashlib.sha256(unified_llm_judge_base_prompt.encode()).hexdigest()

        assert digest == (
            "593373c642a288a7b590577d8a8fc92c3f9a2b70e2f64ad6e59a040a6c56b7f5"
        )


class TestParseJsonResponse:
    """Judge replies that wrap or surround their JSON."""

    @pytest.mark.parametrize(
        "reply",
        [
            '{"score": 1.0, "reason": "ok"}',
            '```json\n{"score": 1.0, "reason": "ok"}\n```',
            'Here is my verdict: {"score": 1.0, "reason": "ok"} Thanks.',
        ],
    )
    def test_reads_the_object(self, reply):
        """A bare, fenced or embedded object parses to the same dict."""
        assert parse_json_response(reply) == {"score": 1.0, "reason": "ok"}

    def test_a_reply_without_json_raises(self):
        """Prose alone is an error."""
        with pytest.raises(JudgeReplyError):
            parse_json_response("I think it is fine.")


class TestRubricScore:
    """A rubric is scored item by item."""

    async def test_is_the_mean_of_the_item_scores(self):
        """Items that score 1, 0.5 and 0 average to 0.5."""
        judge = _Judge(
            {"item one": _score(1.0), "item two": _score(0.5), "item three": _score(0)}
        )

        score, failed = await rubric_score(
            judge,
            ["item one", "item two", "item three"],
            "the answer",  # type: ignore[arg-type]
        )

        assert score == pytest.approx(0.5)
        assert failed is False
        assert all("the answer" in p for p in judge.prompts)

    async def test_a_reply_that_does_not_parse_scores_zero_and_is_flagged(self):
        """The bad item adds 0 to the sum, and the caller learns of it."""
        judge = _Judge({"item one": _score(1.0), "item two": "no idea"})

        score, failed = await rubric_score(judge, ["item one", "item two"], "a")  # type: ignore[arg-type]

        assert score == pytest.approx(0.5)
        assert failed is True


class TestOrderingScore:
    """The event-ordering formula on hand-worked cases."""

    @pytest.mark.parametrize(
        ("reference", "system", "f1", "tau_norm"),
        [
            (["A", "B", "C"], ["A", "B", "C"], 1.0, 1.0),
            (["A", "B", "C"], ["C", "B", "A"], 1.0, 0.0),
            # One of three pairs is swapped: tau-b is 1/3, scaled to 2/3.
            (["A", "B", "C"], ["A", "C", "B"], 1.0, 2 / 3),
            # B is missing: P=1, R=2/3, F1=0.8. Ranks are [1,2,3] and [1,4,2].
            (["A", "B", "C"], ["A", "C"], 0.8, 2 / 3),
            # X is extra: P=2/3, R=1, F1=0.8. Ranks are [1,2,4] and [1,3,2].
            (["A", "B"], ["A", "X", "B"], 0.8, 2 / 3),
        ],
    )
    def test_f1_and_normalized_tau_b(self, reference, system, f1, tau_norm):
        """Each case gives the F1, the scaled tau-b and their product."""
        score = ordering_score(reference, system)

        assert score.f1 == pytest.approx(f1)
        assert score.tau_norm == pytest.approx(tau_norm)
        assert score.final_score == pytest.approx(f1 * tau_norm)

    @pytest.mark.filterwarnings("ignore:One or more sample arguments")
    def test_a_single_ranked_item_has_no_correlation_and_scores_zero(self):
        """Tau-b is undefined for one item, which counts as 0 and not as NaN."""
        score = ordering_score(["A"], ["A"])

        assert score.tau_norm == 0.0
        assert score.final_score == 0.0

    def test_nothing_matched_scores_zero(self):
        """No shared line gives F1 0."""
        assert ordering_score(["A", "B"], ["X", "Y"]).final_score == 0.0


class TestAlignment:
    """Answer lines are matched to reference items by the judge."""

    async def test_replaces_a_matching_line_with_its_item_and_skips_blank_lines(self):
        """A blank line costs no judge call, and a matched item is used once."""
        judge = _Equivalence({("park trip", "walked to the park")})

        aligned = await align_with_llm(
            judge,  # type: ignore[arg-type]
            ["park trip", "lunch"],
            ["walked to the park", "", "drank tea"],
        )

        assert aligned == ["park trip", "", "drank tea"]
        assert ("park trip", "") not in judge.asked
        assert ("lunch", "") not in judge.asked
        assert ("lunch", "drank tea") in judge.asked

    async def test_a_matched_item_is_not_offered_to_later_lines(self):
        """Two lines about one event match it once."""
        judge = _Equivalence({("park trip", "went out"), ("park trip", "went again")})

        aligned = await align_with_llm(
            judge,
            ["park trip"],
            ["went out", "went again"],  # type: ignore[arg-type]
        )

        assert aligned == ["park trip", "went again"]

    async def test_event_ordering_score_splits_the_answer_on_lines(self):
        """An answer that lists the events in order scores 1."""
        judge = _Equivalence(
            {("first event", "1. first event"), ("second event", "2. second event")}
        )

        score = await event_ordering_score(
            judge,  # type: ignore[arg-type]
            ["first event", "second event"],
            "1. first event\n2. second event",
        )

        assert score.final_score == pytest.approx(1.0)


def _question(group: str, reference: dict) -> BenchmarkQuestion:
    return BenchmarkQuestion(
        id="conv1:q:0",
        corpus_id="conv1",
        messages=[{"role": "user", "content": "What?"}],
        group=group,
        reference=reference,
    )


class TestJudgeCallEstimate:
    """The judge calls that the dry run allows for."""

    def test_full_allows_for_event_ordering_and_lite_does_not(self):
        """Event-ordering questions need more calls, and only full has them."""
        assert BeamGrader(full=True).judge_calls_per_question == 8
        assert BeamGrader().judge_calls_per_question == 2


class TestBeamGrader:
    """Grading one answer."""

    async def test_a_rubric_question_scores_the_item_mean(self):
        """The score and the score without known-bad probes are the same."""
        judge = _Judge({"crit-a": _score(1.0), "crit-b": _score(0.0)})

        grade = await BeamGrader().grade(
            _question("abstention", {"rubric": ["crit-a", "crit-b"]}),
            SystemAnswer(text="a"),
            judge,  # type: ignore[arg-type]
        )

        assert grade.scores == {"score": 0.5, "score_excluding_known_bad": 0.5}
        assert grade.flags == []

    async def test_a_known_bad_rubric_is_flagged_and_left_out_of_the_clean_score(self):
        """The flag is set and the clean metric is absent."""
        judge = _Judge({"crit-a": _score(1.0)})

        grade = await BeamGrader().grade(
            _question(
                "temporal_reasoning", {"rubric": ["crit-a"], "known_bad_rubric": "x"}
            ),
            SystemAnswer(text="a"),
            judge,  # type: ignore[arg-type]
        )

        assert grade.scores == {"score": 1.0}
        assert grade.flags == ["known_bad_rubric"]

    async def test_an_event_ordering_question_reports_f1_tau_and_their_product(self):
        """The score is F1 times tau, and both parts are kept."""
        judge = _Equivalence({("A", "A"), ("B", "B")})

        grade = await BeamGrader().grade(
            _question("event_ordering", {"rubric": ["A", "B"]}),
            SystemAnswer(text="A\nB"),
            judge,  # type: ignore[arg-type]
        )

        assert grade.scores == {
            "score": 1.0,
            "event_f1": 1.0,
            "event_tau_norm": 1.0,
            "score_excluding_known_bad": 1.0,
        }

    async def test_a_reply_that_does_not_parse_sets_the_flag(self):
        """A bad judge reply shows as a flag on the question."""
        judge = _Judge({"crit-a": "unsure"})

        grade = await BeamGrader().grade(
            _question("abstention", {"rubric": ["crit-a"]}),
            SystemAnswer(text="a"),
            judge,  # type: ignore[arg-type]
        )

        assert grade.flags == ["parse_error"]
        assert grade.scores["score"] == 0.0
