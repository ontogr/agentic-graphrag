"""Grading for BEAM: one rubric per probing question, scored by the judge.

A question score is the mean of its rubric item scores (1, 0.5 or 0). The ability
score is the mean over its questions. ``event_ordering`` questions use the
benchmark's ordering score instead: the F1 of the answer lines against the rubric
items, times the normalized rank correlation of the two orders.

The benchmark's leaderboard script reports only the rank correlation for event
ordering, so ``event_tau_norm`` and ``event_f1`` are kept next to ``score``.
"""

from agrag.eval import ChatModelJudge
from benchmarks.grading.base import Grade, Grader
from benchmarks.grading.beam_scorer import event_ordering_score, rubric_score
from benchmarks.models import BenchmarkQuestion
from benchmarks.systems.base import SystemAnswer


# One event-ordering question in ten at 90 calls, the other nine at 3 calls each.
_FULL_JUDGE_CALLS = 12


class BeamGrader(Grader):
    """Scores one answer against the rubric of its probing question.

    ``score`` is the question score. A question with a known defect in its rubric
    gets the flag ``known_bad_rubric`` and no ``score_excluding_known_bad``, so that
    the group mean of that metric leaves it out. An agent failure scores 0 on every
    metric, which counts a failed known-bad question in that mean. ``event_f1`` and
    ``event_tau_norm`` exist for ``event_ordering`` questions only; read them in
    that group. A judge reply that does not parse scores 0 for its rubric item and
    sets the flag ``parse_error``.
    """

    metrics = ("score", "score_excluding_known_bad", "event_f1", "event_tau_norm")

    def __init__(self, *, full: bool = False) -> None:
        """Set the judge calls that one question needs.

        Args:
            full: Whether the questions include event ordering. An answer line
                that matches no reference item is compared with every unused
                item, so an event-ordering question can need as many calls as
                answer lines times reference items. The estimate takes ten lines
                and nine items, the largest rubric of the full set. A question
                of another ability needs one call for each rubric item.
        """
        self.judge_calls_per_question = _FULL_JUDGE_CALLS if full else 2

    async def grade(
        self, question: BenchmarkQuestion, answer: SystemAnswer, judge: ChatModelJudge
    ) -> Grade:
        """Score one answer."""
        rubric = question.reference["rubric"]
        scores: dict[str, float] = {}
        flags: list[str] = []
        if question.group == "event_ordering":
            ordering = await event_ordering_score(judge, rubric, answer.text)
            scores["score"] = ordering.final_score
            scores["event_f1"] = ordering.f1
            scores["event_tau_norm"] = ordering.tau_norm
        else:
            scores["score"], parse_error = await rubric_score(
                judge, rubric, answer.text
            )
            if parse_error:
                flags.append("parse_error")
        if question.reference.get("known_bad_rubric"):
            flags.append("known_bad_rubric")
        else:
            scores["score_excluding_known_bad"] = scores["score"]
        return Grade(scores=scores, flags=flags)
