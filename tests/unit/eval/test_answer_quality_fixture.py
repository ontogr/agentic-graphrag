"""Checks that the answer-quality fixture is complete and self-consistent.

The fixture is FinQA pages and questions. It comes from
tests/fixtures/eval/answer_quality/build_finqa_corpus.py.
"""

from tests.integration.eval._answer_quality import FIXTURE_DIR, load_questions


class TestAnswerQualityFixture:
    """Every question has a reference and points to a document that exists."""

    def test_has_one_document_and_two_questions(self) -> None:
        """The corpus holds one page and two questions."""
        documents = sorted((FIXTURE_DIR / "documents").glob("*.md"))
        questions = load_questions()

        assert len(documents) == 1
        assert len(questions) == 2
        assert {question["document"] for question in questions} == {
            document.name for document in documents
        }

    def test_every_question_has_a_reference(self) -> None:
        """No question or reference is empty."""
        for question in load_questions():
            assert question["question"].strip()
            assert question["reference"].strip()

    def test_documents_are_small(self) -> None:
        """The whole fixture stays under 200 KB."""
        total = sum(
            path.stat().st_size for path in FIXTURE_DIR.rglob("*") if path.is_file()
        )

        assert total < 200_000
