"""Loader for the answer-quality fixture, shared by the eval tests."""

import json
from pathlib import Path
from typing import TypedDict


FIXTURE_DIR = (
    Path(__file__).resolve().parents[2] / "fixtures" / "eval" / "answer_quality"
)


class Question(TypedDict):
    """One question with its reference answer.

    Attributes:
        id: The FinQA example id.
        document: The file name of the page that holds the answer.
        question: The question text.
        reference: The reference answer.
    """

    id: str
    document: str
    question: str
    reference: str


def load_questions() -> list[Question]:
    """Read ``questions.jsonl`` from the fixture folder."""
    lines = (FIXTURE_DIR / "questions.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines if line]
