"""Readable citations keep fetched provenance and escape untrusted source metadata.

Run with ``uv run pytest tests/unit/evidence/test_render.py``. These pure rendering
cases cover unsafe Markdown that does not require a database to reproduce.
"""

import pytest

from agrag.common.data_models.evidence import FetchOutcome, FetchStatus
from agrag.evidence import render_citations
from tests.integration.retrieval.evidence._corpus import span_evidence_id


_TEXT = "The lamp was repaired in April."
_ID = span_evidence_id("report", _TEXT, 0, len(_TEXT))
_NARROW = span_evidence_id("report", _TEXT, 4, 8)


class TestReadableCitations:
    """Only complete, validated evidence becomes a readable source reference."""

    def test_grouped_and_narrower_citations_keep_the_fetched_parent(self) -> None:
        """Repeated and narrower citations share a source number and real fetch."""
        fetched = FetchOutcome(
            evidence_id=_ID,
            status=FetchStatus.OK,
            text=_TEXT,
            title="Maintenance report",
            uri="https://example.org/report?q=(lamp)&year=2026",
            covered_range=(0, len(_TEXT)),
        )
        answer, sources = render_citations(
            f"Lamp [{_NARROW}; {_ID}]. Again [{_NARROW}].",
            [_NARROW, _ID],
            [fetched],
        )

        assert answer == (
            "Lamp [[1]](https://example.org/report?q=%28lamp%29&year=2026). "
            "Again [[1]](https://example.org/report?q=%28lamp%29&year=2026)."
            "\n\n### Sources\n\n"
            "[1] [Maintenance report]"
            "(https://example.org/report?q=%28lamp%29&year=2026)"
        )
        assert sources == [fetched]
        assert sources[0].evidence_id == _ID
        assert sources[0].text == _TEXT

    def test_numbers_follow_first_use_and_group_passages_by_document_version(
        self,
    ) -> None:
        """Source order follows the answer while fetched passages retain their IDs."""
        local_id = span_evidence_id("local-report", _TEXT, 0, 31)
        local = FetchOutcome(
            evidence_id=local_id, status=FetchStatus.OK, title="Local report"
        )
        first = FetchOutcome(
            evidence_id=_ID,
            status=FetchStatus.OK,
            title="Maintenance report",
            uri="https://example.org/report",
        )
        second = first.model_copy(update={"evidence_id": _NARROW})

        answer, sources = render_citations(
            f"Local [{local_id}]. Remote [{_ID}; {_NARROW}]. Again [{_NARROW}].",
            [_NARROW, _ID, local_id],
            [first, second, local],
        )

        assert answer == (
            "Local [1]. Remote [[2]](https://example.org/report). "
            "Again [[2]](https://example.org/report)."
            "\n\n### Sources\n\n[1] Local report"
            "\n\n[2] [Maintenance report](https://example.org/report)"
        )
        assert {source.evidence_id for source in sources} == {local_id, _ID, _NARROW}

    @pytest.mark.parametrize(
        "uri",
        [
            "/home/user/report.pdf",
            "file:///home/user/report.pdf",
            "inline://report",
            "javascript:alert(1)",
            "https://user:secret@example.org/report",
            "https://example.org:bad/report",
            "https://example.org/\nreport",
            "https:///report",
        ],
    )
    def test_local_and_unsafe_sources_are_not_links(self, uri: str) -> None:
        """Unsafe destinations stay non-clickable and title markup stays literal."""
        fetched = FetchOutcome(
            evidence_id=_ID,
            status=FetchStatus.OK,
            text=_TEXT,
            title="Report [draft] <script>\n*April*",
            uri=uri,
            covered_range=(0, 31),
        )
        answer, _ = render_citations(f"Claim [{_ID}].", [_ID], [fetched])

        assert answer == (
            "Claim [1].\n\n### Sources\n\n"
            "[1] Report \\[draft\\] &lt;script&gt; \\*April\\*"
        )
        assert fetched.model_dump()["citation_markdown"] == (
            "Report \\[draft\\] &lt;script&gt; \\*April\\*"
        )

    def test_invalid_mixed_groups_and_incomplete_fetches_stay_visible(self) -> None:
        """A truncated fetch cannot become a source link despite a supplied ID."""
        fetched = FetchOutcome(
            evidence_id=_ID, status=FetchStatus.TRUNCATED, text="The lamp"
        )
        text = f"Claim [{_ID}, ev1:bad]. Other [{_ID}]."

        answer, sources = render_citations(text, [_ID], [fetched])

        assert answer == text
        assert sources == []

    def test_existing_markdown_links_are_not_nested(self) -> None:
        """Formatting canonical brackets does not rewrite existing Markdown links."""
        fetched = FetchOutcome(
            evidence_id=_ID,
            status=FetchStatus.OK,
            title="Report",
            uri="https://example.org/report",
        )
        answer, _ = render_citations(
            f"Claim [{_ID}](https://wrong.example/report).", [_ID], [fetched]
        )

        assert answer == f"Claim [{_ID}](https://wrong.example/report)."
