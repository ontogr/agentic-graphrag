"""Checks that the answer-quality fixture is complete and self-consistent.

The fixture is FinQA pages and questions. It comes from
tests/fixtures/eval/answer_quality/build_finqa_corpus.py.
"""

from tests.integration.eval._answer_quality import load_questions


class TestAnswerQualityFixture:
    """Every question has a reference."""

    def test_every_question_has_a_reference(self) -> None:
        """No question or reference is empty."""
        for question in load_questions():
            assert question["question"].strip()
            assert question["reference"].strip()
