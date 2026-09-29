"""Tests for the opt-in semantic, neural and code chunkers when their extra is absent.

Each chunker builds without its extra and reports its settings and fingerprint. Its
``chunk()`` call raises ``ChunkerMissingExtraError`` that names the extra to install.
The byte-to-character conversion of the code chunker is a pure function and runs here
without tree-sitter.
"""

import chonkie
import pytest

from agrag.chunking import (
    Chunking,
    ChunkingError,
    CodeChunker,
    NeuralChunker,
    SemanticChunker,
)
from agrag.chunking.base import ChunkerMissingExtraError
from agrag.chunking.extras import byte_spans_to_char_spans
from tests.unit.chunking._support import make_document


_CASES = [
    (SemanticChunker, "chunk-semantic", "SemanticChunker"),
    (NeuralChunker, "chunk-neural", "NeuralChunker"),
    (CodeChunker, "chunk-code", "CodeChunker"),
]


def _without_extra(monkeypatch: pytest.MonkeyPatch, chonkie_name: str) -> None:
    """Make chonkie's class fail as it does when its optional package is missing."""

    def missing(*args: object, **kwargs: object) -> None:
        raise ImportError(f"{chonkie_name} needs an optional package")

    monkeypatch.setattr(chonkie, chonkie_name, missing)


class TestWithoutTheExtra:
    """A missing package gives a clear error at chunk time, not at construction."""

    @pytest.mark.parametrize(("cls", "extra", "chonkie_name"), _CASES)
    def test_builds_and_fingerprints_without_the_extra(
        self, cls, extra: str, chonkie_name: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Construction needs no optional package."""
        _without_extra(monkeypatch, chonkie_name)

        chunker = cls()

        assert len(chunker.fingerprint()) == 16
        assert chunker.settings()["strategy"] == chunker.strategy

    @pytest.mark.parametrize(("cls", "extra", "chonkie_name"), _CASES)
    def test_chunk_raises_an_error_that_names_the_extra(
        self, cls, extra: str, chonkie_name: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The message tells the user which extra to install."""
        _without_extra(monkeypatch, chonkie_name)

        with pytest.raises(ChunkerMissingExtraError, match=extra) as raised:
            cls().chunk(make_document("def f():\n    return 1\n"))

        assert raised.value.extra == extra
        assert isinstance(raised.value, ChunkingError)

    def test_rules_accept_the_extra_chunkers(self) -> None:
        """A Chunking can hold them and fingerprint them."""
        chunking = Chunking(fallback=CodeChunker(language="python"))

        assert chunking.fingerprint() != Chunking(fallback=CodeChunker()).fingerprint()

    def test_each_setting_changes_the_fingerprint(self) -> None:
        """Settings are part of the hash."""
        assert (
            SemanticChunker().fingerprint()
            != SemanticChunker(threshold=0.5).fingerprint()
        )
        assert (
            NeuralChunker().fingerprint()
            != NeuralChunker(model="some/model").fingerprint()
        )
        assert CodeChunker().fingerprint() != CodeChunker(chunk_size=64).fingerprint()


class TestByteSpansToCharSpans:
    """tree-sitter reports byte offsets; agrag needs character offsets."""

    def test_ascii_text_is_unchanged(self) -> None:
        """For ASCII, bytes and characters agree."""
        assert byte_spans_to_char_spans("abc def", [(0, 3), (4, 7)]) == [(0, 3), (4, 7)]

    def test_multibyte_text_maps_to_characters(self) -> None:
        """A comment with an accent and CJK text shifts byte offsets."""
        text = "# café 日本\nx = 1\n"
        encoded = text.encode("utf-8")
        start = encoded.index(b"x = 1")

        spans = byte_spans_to_char_spans(text, [(0, start), (start, len(encoded))])

        assert [text[a:b] for a, b in spans] == ["# café 日本\n", "x = 1\n"]

    def test_empty_span_list(self) -> None:
        """Nothing in, nothing out."""
        assert byte_spans_to_char_spans("abc", []) == []
