"""Tests for extracting evidence citations from answer text."""

from agrag.evidence.citation import parse_citations


class TestParseCitations:
    """Citation parsing distinguishes malformed references from normal links."""

    def test_extracts_grouped_ids_and_reports_malformed_citation_tokens(self) -> None:
        """Grouped ids parse; citation-like invalid syntax is retained separately."""
        text = (
            "[ev1:s:12345678-1234-1234-1234-123456789abc:0123456789abcdef:1-2, "
            "ev1:c:12345678-1234-1234-1234-123456789abc:0123456789abcdef:"
            "abcdefab-cdef-abcd-efab-cdefabcdefab]; "
            "[ev2:s:bad], [E1], [1], [ev1:s:unfinished and [ordinary](https://x)"
        )

        parsed = parse_citations(text)

        assert parsed.ids == (
            "ev1:s:12345678-1234-1234-1234-123456789abc:0123456789abcdef:1-2",
            "ev1:c:12345678-1234-1234-1234-123456789abc:0123456789abcdef:"
            "abcdefab-cdef-abcd-efab-cdefabcdefab",
        )
        assert parsed.malformed_tokens == (
            "[ev2:s:bad]",
            "[E1]",
            "[1]",
            "[ev1:s:unfinished and",
        )

    def test_ordinary_markdown_links_are_not_citations(self) -> None:
        """A numeric label in a Markdown link is not treated as a citation."""
        parsed = parse_citations("[1](https://example.test) and [guide](./guide.md)")

        assert parsed.ids == ()
        assert parsed.malformed_tokens == ()
