"""Checks the committed FinQA verdict items.

The items come from ``tests/fixtures/eval/verifier/build_finqa_verdicts.py``. These
checks fail when a rebuilt file has the wrong class counts, a repeated id, or an
INSUFFICIENT or CONTRADICTORY item whose evidence does not differ from a PASS item.
"""

import re
from collections import Counter
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
    """The verdict items are balanced, unique and small."""

    def test_has_twenty_items_per_class(self, items: list[VerdictItem]) -> None:
        """Each of the three verdicts has 20 items."""
        assert len(items) == 60
        assert Counter(item.gold for item in items) == {
            "PASS": 20,
            "INSUFFICIENT": 20,
            "CONTRADICTORY": 20,
        }

    def test_ids_are_unique(self, items: list[VerdictItem]) -> None:
        """No FinQA example is used twice."""
        assert len({item.id for item in items}) == len(items)

    def test_file_is_small(self) -> None:
        """The fixture stays under 200 KB."""
        assert ITEMS_FILE.stat().st_size < 200_000

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
