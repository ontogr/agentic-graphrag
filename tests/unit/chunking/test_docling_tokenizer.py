"""Tests for the tokenizer that DoclingChunker gives to docling's hybrid chunker.

The adapter counts tokens with the tokenizer the text strategies use, so token sizes
mean the same for every strategy. Sockets stay disabled: no vocabulary downloads.
"""

import pytest


pytest.importorskip("docling_core")

from chonkie.tokenizer import AutoTokenizer  # noqa: E402

from agrag.chunking.docling import _build_tokenizer  # noqa: E402


class TestBuildTokenizer:
    """_build_tokenizer picks the agrag adapter or a Hugging Face tokenizer."""

    @pytest.mark.parametrize(
        "text", ["", "plain words here", "日本語 é \U0001f600 mix"]
    )
    def test_count_equals_the_text_strategies_count(self, text: str) -> None:
        """The adapter and chonkie count the same tokens for the same text."""
        tokenizer = _build_tokenizer("o200k_base", 100)

        assert tokenizer.count_tokens(text) == AutoTokenizer("o200k_base").count_tokens(
            text
        )

    def test_reports_the_token_budget(self) -> None:
        """get_max_tokens returns the budget that the chunker was given."""
        assert _build_tokenizer("o200k_base", 321).get_max_tokens() == 321

    def test_underlying_tokenizer_is_a_counting_callable(self) -> None:
        """Docling's splitter needs a callable that returns a token count."""
        counter = _build_tokenizer("o200k_base", 10).get_tokenizer()

        assert callable(counter)
        assert counter("one two three") == AutoTokenizer("o200k_base").count_tokens(
            "one two three"
        )

    def test_unknown_name_fails_when_built(self) -> None:
        """A tokenizer name that cannot load raises at build time."""
        with pytest.raises(Exception, match="no-such-tokenizer"):
            _build_tokenizer("no-such-tokenizer", 10)

    def test_a_name_with_a_slash_selects_hugging_face(self) -> None:
        """A model id goes to the Hugging Face loader, which needs the network."""
        with pytest.raises(Exception) as raised:  # noqa: PT011
            _build_tokenizer("someorg/some-model", 10)

        assert "SocketBlockedError" in type(raised.value).__name__ or (
            "someorg" in str(raised.value)
        )
