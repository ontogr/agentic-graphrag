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

    @staticmethod
    def test_matches_across_case_and_spacing() -> None:
        """Two spellings of one name give one key."""
        assert endpoint_key("ADA   lovelace") == endpoint_key("Ada\nLovelace")


class TestLocateMentions:
    """locate_mentions maps each (label, text) pair to a span or None."""

    @staticmethod
    def test_returns_the_span_of_a_unique_mention() -> None:
        """A name that occurs once gets its exact span."""
        chunk = "Ada Lovelace worked at Acme."

        (span,) = locate_mentions([("Person", "Ada Lovelace")], chunk)

        assert span == (0, 12)
        assert chunk[span[0] : span[1]] == "Ada Lovelace"

    @staticmethod
    def test_does_not_match_inside_a_longer_word() -> None:
        """Ada is not found in Canada."""
        assert locate_mentions([("Person", "Ada")], "She lives in Canada.") == [None]

    @staticmethod
    def test_does_not_match_a_longer_number() -> None:
        """1.6 is not found in 11.62."""
        assert locate_mentions([("Value", "1.6")], "It rose to 11.62.") == [None]

    @staticmethod
    def test_matches_text_that_starts_or_ends_with_punctuation() -> None:
        """A punctuated edge matches when the chunk has a non-word neighbor."""
        chunk = "Cost $5M in the U.S. last year."

        spans = locate_mentions([("Money", "$5M"), ("Location", "U.S.")], chunk)

        assert spans == [(5, 8), (16, 20)]

    @staticmethod
    def test_does_not_match_a_punctuated_name_inside_a_longer_token() -> None:
        """U.S. is not found inside U.S.A."""
        assert locate_mentions([("Location", "U.S.")], "Born in U.S.A.") == [None]

    @staticmethod
    def test_matches_across_a_line_break() -> None:
        """A model answers on one line; the chunk may wrap the name."""
        chunk = "She joined the Analytical\nEngine Company."

        (span,) = locate_mentions(
            [("Organization", "Analytical Engine Company")], chunk
        )

        assert span is not None
        assert chunk[span[0] : span[1]] == "Analytical\nEngine Company"

    @staticmethod
    def test_is_case_sensitive() -> None:
        """A lower-case spelling does not match an upper-case mention."""
        assert locate_mentions([("Organization", "US")], "Tell us more.") == [None]

    @staticmethod
    def test_maps_the_nth_listing_to_the_nth_occurrence() -> None:
        """Two listings of the same label and text take the first two occurrences."""
        chunk = "Ada met Bob. Ada left. Ada returned."

        spans = locate_mentions(
            [("Person", "Ada"), ("Person", "Ada"), ("Person", "Ada")], chunk
        )

        assert spans == [(0, 3), (13, 16), (23, 26)]

    @staticmethod
    def test_drops_a_listing_past_the_last_occurrence() -> None:
        """A text listed twice that occurs once keeps only the first listing."""
        chunk = "Ada left."

        spans = locate_mentions([("Person", "Ada"), ("Person", "Ada")], chunk)

        assert spans == [(0, 3), None]

    @staticmethod
    def test_two_labels_share_one_occurrence() -> None:
        """One name under two labels keeps both labels on the same span."""
        chunk = "Apple released the iPhone."

        spans = locate_mentions(
            [("Product", "Apple"), ("Organization", "Apple")], chunk
        )

        assert spans == [(0, 5), (0, 5)]

    @staticmethod
    def test_drops_empty_and_absent_text() -> None:
        """Empty text and text that is not in the chunk have no span."""
        spans = locate_mentions(
            [("Person", ""), ("Person", "   "), ("Person", "Ghost")], "Ada left."
        )

        assert spans == [None, None, None]

    @staticmethod
    def test_returns_one_entry_per_mention_in_order() -> None:
        """The result lines up with the input, with None holes for drops."""
        chunk = "Ada works at Acme."

        spans = locate_mentions(
            [("Person", "Ada"), ("Person", "Ghost"), ("Organization", "Acme")], chunk
        )

        assert spans == [(0, 3), None, (13, 17)]
