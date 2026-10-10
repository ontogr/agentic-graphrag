"""Tests the dry-run bound and its spend cap check."""

import pytest

from benchmarks.datasets.base import text_document
from benchmarks.harness.config import BENCH_CHUNKING, SPEND_CAPS, SpendCap
from benchmarks.harness.dry_run import (
    SpendCapError,
    check_cap,
    count_chunks,
    dry_run,
)
from tests.unit.benchmarks.fakes import COST, DOMAIN


def _bound():
    manifest = DOMAIN.adapter.load("lite")
    documents = {c.id: DOMAIN.adapter.documents(c) for c in manifest.corpora}
    return dry_run(
        manifest,
        documents,
        chunking=BENCH_CHUNKING,
        cost=COST,
        judge_calls_per_question=1,
    )


class TestDryRun:
    """The cost bound of a run."""

    def test_a_longer_document_makes_more_chunks(self):
        """A longer document makes more chunks."""
        short = text_document("word " * 100, uri="a")
        long = text_document("word " * 5000, uri="b")

        assert count_chunks([long], BENCH_CHUNKING) > count_chunks(
            [short], BENCH_CHUNKING
        )


class TestCheckCap:
    """Comparison of the bound with the spend cap."""

    def test_passes_under_a_configured_cap(self, monkeypatch):
        """Passes under a configured cap."""
        bound = _bound()
        monkeypatch.setitem(
            SPEND_CAPS, ("d", "lite"), SpendCap(bound.llm_calls, bound.tokens)
        )

        assert check_cap(bound, "d", "lite").overridden is False

    def test_raises_above_the_cap(self, monkeypatch):
        """Raises above the cap."""
        bound = _bound()
        monkeypatch.setitem(
            SPEND_CAPS, ("d", "lite"), SpendCap(bound.llm_calls - 1, bound.tokens)
        )

        with pytest.raises(SpendCapError, match="above the cap"):
            check_cap(bound, "d", "lite")

    def test_raises_without_a_cap_or_flags(self):
        """Raises without a cap or flags."""
        with pytest.raises(SpendCapError, match="no spend cap"):
            check_cap(_bound(), "d", "lite")

    def test_one_flag_alone_is_not_enough_without_a_cap(self):
        """One flag alone is not enough without a cap."""
        with pytest.raises(SpendCapError, match="no spend cap"):
            check_cap(_bound(), "d", "lite", max_llm_calls=10**6)
