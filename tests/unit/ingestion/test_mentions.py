"""Tests for the text search that finds LLM-reported mentions in a chunk."""

import pytest

from agrag.ingestion._mentions import endpoint_key, locate_mentions, mention_key


class TestMentionKey:
    """mention_key collapses whitespace so two spellings compare equal."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Ada", "Ada"),
            ("  Ada   Lovelace ", "Ada Lovelace"),
            ("Ada\nLovelace", "Ada Lovelace"),
            ("   ", ""),
        ],
    )
    def test_collapses_whitespace(self, text: str, expected: str) -> None:
        """Runs of whitespace become one space and the ends are trimmed."""
        assert mention_key(text) == expected


class TestEndpointKey:
    """endpoint_key ignores case and spacing."""

    def test_matches_across_case_and_spacing(self) -> None:
        """Two spellings of one name give one key."""
        assert endpoint_key("ADA   lovelace") == endpoint_key("Ada\nLovelace")


class TestLocateMentions:
    """locate_mentions maps each (label, text) pair to a span or None."""

    def test_returns_the_span_of_a_unique_mention(self) -> None:
        """A name that occurs once gets its exact span."""
        chunk = "Ada Lovelace worked at Acme."

        (span,) = locate_mentions([("Person", "Ada Lovelace")], chunk)

        assert span == (0, 12)
        assert chunk[span[0] : span[1]] == "Ada Lovelace"

    def test_does_not_match_inside_a_longer_word(self) -> None:
        """Ada is not found in Canada."""
        assert locate_mentions([("Person", "Ada")], "She lives in Canada.") == [None]

    def test_does_not_match_a_longer_number(self) -> None:
        """1.6 is not found in 11.62."""
        assert locate_mentions([("Value", "1.6")], "It rose to 11.62.") == [None]

    def test_matches_text_that_starts_or_ends_with_punctuation(self) -> None:
        """Word boundaries apply only to word characters at the edge."""
        chunk = "Cost $5M in the U.S. last year."

        spans = locate_mentions([("Money", "$5M"), ("Location", "U.S.")], chunk)

        assert spans == [(5, 8), (16, 20)]

    def test_matches_across_a_line_break(self) -> None:
        """A model answers on one line; the chunk may wrap the name."""
        chunk = "She joined the Analytical\nEngine Company."

        (span,) = locate_mentions(
            [("Organization", "Analytical Engine Company")], chunk
        )

        assert span is not None
        assert chunk[span[0] : span[1]] == "Analytical\nEngine Company"

    def test_is_case_sensitive(self) -> None:
        """A lower-case spelling does not match an upper-case mention."""
        assert locate_mentions([("Organization", "US")], "Tell us more.") == [None]

    def test_maps_the_nth_listing_to_the_nth_occurrence(self) -> None:
        """Two listings of the same label and text take the first two occurrences."""
        chunk = "Ada met Bob. Ada left. Ada returned."

        spans = locate_mentions(
            [("Person", "Ada"), ("Person", "Ada"), ("Person", "Ada")], chunk
        )

        assert spans == [(0, 3), (13, 16), (23, 26)]

    def test_drops_a_listing_past_the_last_occurrence(self) -> None:
        """A text listed twice that occurs once keeps only the first listing."""
        chunk = "Ada left."

        spans = locate_mentions([("Person", "Ada"), ("Person", "Ada")], chunk)

        assert spans == [(0, 3), None]

    def test_two_labels_share_one_occurrence(self) -> None:
        """One name under two labels keeps both labels on the same span."""
        chunk = "Apple released the iPhone."

        spans = locate_mentions(
            [("Product", "Apple"), ("Organization", "Apple")], chunk
        )

        assert spans == [(0, 5), (0, 5)]

    def test_drops_empty_and_absent_text(self) -> None:
        """Empty text and text that is not in the chunk have no span."""
        spans = locate_mentions(
            [("Person", ""), ("Person", "   "), ("Person", "Ghost")], "Ada left."
        )

        assert spans == [None, None, None]

    def test_returns_one_entry_per_mention_in_order(self) -> None:
        """The result lines up with the input, with None holes for drops."""
        chunk = "Ada works at Acme."

        spans = locate_mentions(
            [("Person", "Ada"), ("Person", "Ghost"), ("Organization", "Acme")], chunk
        )

        assert spans == [(0, 3), None, (13, 17)]
