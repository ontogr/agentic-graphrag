"""Checks the committed FinQA verdict items.

The items come from ``tests/fixtures/eval/verifier/build_finqa_verdicts.py``. These
checks fail when a rebuilt file has a repeated id, or a CONTRADICTORY item whose
last evidence line does not change an earlier one.
"""

import re
from pathlib import Path

import pytest

from agrag.eval.verifier import VerdictItem


FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "eval" / "verifier"
ITEMS_FILE = FIXTURE_DIR / "verdict_items.jsonl"


@pytest.fixture(scope="module")
def items() -> list[VerdictItem]:
    """Load every verdict item."""
    lines = ITEMS_FILE.read_text().splitlines()
    return [VerdictItem.model_validate_json(line) for line in lines]


class TestVerdictFixture:
    """The verdict items have unique ids and cited evidence."""

    def test_ids_are_unique(self, items: list[VerdictItem]) -> None:
        """No FinQA example is used twice."""
        assert len({item.id for item in items}) == len(items)

    def test_every_item_cites_numbered_evidence(self, items: list[VerdictItem]) -> None:
        """Each finding claims an answer and lists at least one evidence line."""
        for item in items:
            assert item.sub_questions == [item.question]
            assert item.findings.startswith("The answer is ")
            assert "\n[E1] " in item.findings

    def test_contradictory_items_cite_two_lines_for_one_item(
        self, items: list[VerdictItem]
    ) -> None:
        """The last evidence line repeats an earlier row with one value changed."""
        for item in items:
            if item.gold != "CONTRADICTORY":
                continue
            lines = re.findall(r"^\[E\d+\] (.*)$", item.findings, re.MULTILINE)
            *earlier, last = lines
            assert last not in earlier
            assert any(
                last.split(" is ")[0] == line.split(" is ")[0] for line in earlier
            )
