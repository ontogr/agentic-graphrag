"""Tests for decode_text in agrag.loaders.decode.

Covers BOM stripping and detection for UTF-8 and UTF-16, CRLF/CR
normalization to LF, NFKC normalization, latin-1 fallback when charset
detection returns no match, and a forced-encoding decode failure raising
DecodeError. Two tests monkeypatch ``agrag.loaders.decode.from_bytes``
to control the charset-detection result without needing real ambiguous
byte sequences, including a regression for reading a detected match's text
via ``str(match)`` rather than re-decoding its UTF-8 ``output()``.
"""

import pytest

from agrag.common.data_models.normalization import Normalization
from agrag.loaders.decode import _had_bom, decode_text
from agrag.loaders.errors import DecodeError
from agrag.loaders.types import ReadOptions


class TestDecodeText:
    """Verify BOM handling, encoding detection, and normalization."""

    def test_strips_utf8_bom_under_forced_encoding(self) -> None:
        """A UTF-8 BOM is removed and reported when the encoding is forced."""
        decoded = decode_text(b"\xef\xbb\xbfhello", ReadOptions(encoding="utf-8"))
        assert decoded.text == "hello"
        assert decoded.had_bom is True
        assert decoded.encoding == "utf-8"

    def test_detects_utf8_with_bom(self) -> None:
        """Detection keeps the BOM flag and strips the mark without a forced encoding."""  # noqa: E501, W505
        decoded = decode_text(b"\xef\xbb\xbfhello", ReadOptions())
        assert decoded.text == "hello"
        assert decoded.had_bom is True

    def test_strips_utf16_bom(self) -> None:
        """A UTF-16 BOM is decoded and stripped when the encoding is forced."""
        raw = "héllo".encode("utf-16")
        decoded = decode_text(raw, ReadOptions(encoding="utf-16"))
        assert decoded.text == "héllo"
        assert decoded.had_bom is True

    def test_forced_utf16_without_decoding_bom(self) -> None:
        """Forcing utf-16 decodes a UTF-16 stream with a BOM."""
        raw = "row".encode("utf-16")
        decoded = decode_text(raw, ReadOptions(encoding="utf-16"))
        assert decoded.text == "row"
        assert decoded.had_bom is True

    def test_normalizes_crlf_to_lf(self) -> None:
        """CRLF and lone CR both collapse to a single LF."""
        decoded = decode_text(b"a\r\nb\rc", ReadOptions())
        assert decoded.text == "a\nb\nc"

    def test_applies_nfkc_normalization(self) -> None:
        """Compatibility characters are normalized to their canonical form."""
        decoded = decode_text("ﬁ".encode("utf-8"), ReadOptions(encoding="utf-8"))
        assert decoded.text == "fi"

    def test_falls_back_to_latin1_when_detection_fails(self, monkeypatch) -> None:
        """When detection returns no match, the pipeline falls back to latin-1."""

        class _NoMatch:
            def best(self):
                return None

        monkeypatch.setattr("agrag.loaders.decode.from_bytes", lambda raw: _NoMatch())
        decoded = decode_text(b"\x80\x81\x82", ReadOptions())
        assert isinstance(decoded.text, str)
        assert decoded.encoding == "latin-1"

    def test_forced_encoding_failure_raises(self) -> None:
        """A forced encoding that cannot decode raises DecodeError."""
        try:
            decode_text(b"\xff\xfe", ReadOptions(encoding="ascii"))
        except DecodeError:
            return
        raise AssertionError("expected DecodeError")

    def test_computes_char_and_line_counts(self) -> None:
        """Char and line counts reflect the normalized text."""
        decoded = decode_text(b"a\nb\nc", ReadOptions())
        assert decoded.char_count == 5
        assert decoded.line_count == 3

    def test_had_bom_false_without_bom(self) -> None:
        """A plain stream reports no BOM."""
        assert _had_bom(b"plain") is False
        assert _had_bom(b"\xef\xbb\xbfx") is True

    def test_uses_detected_text_directly_for_non_utf_encodings(
        self, monkeypatch
    ) -> None:
        """A detected non-UTF match uses its own decoded text, not a re-decode.

        ``CharsetMatch.output()`` re-encodes the detected text to UTF-8 bytes
        regardless of the detected encoding, so decoding those bytes again with
        ``match.encoding`` corrupts the text. ``str(match)`` must be used instead.
        """

        class _MockMatch:
            encoding = "cp1252"

            def output(self):
                return "café".encode()

            def __str__(self) -> str:
                return "café"

        class _MockCharsetMatches:
            def best(self):
                return _MockMatch()

        monkeypatch.setattr(
            "agrag.loaders.decode.from_bytes", lambda raw: _MockCharsetMatches()
        )
        decoded = decode_text(b"irrelevant", ReadOptions())
        assert decoded.text == "café"
        assert decoded.encoding == "cp1252"


class TestNormalizationSetting:
    """ReadOptions.normalization controls what decode_text does to the text."""

    @pytest.mark.parametrize("encoding", [None, "utf-8"], ids=["detected", "forced"])
    def test_bom_keep_leaves_the_mark_at_index_zero(self, encoding: str | None) -> None:
        """The mark stays under both detected and forced decoding."""
        opts = ReadOptions(encoding=encoding, normalization=Normalization(bom="keep"))

        decoded = decode_text(b"\xef\xbb\xbfhello world text", opts)

        assert decoded.text[0] == "﻿"
        assert decoded.text[1:] == "hello world text"

    def test_bom_keep_adds_nothing_to_a_file_without_a_mark(self) -> None:
        """A file with no mark does not gain one."""
        opts = ReadOptions(normalization=Normalization(bom="keep"))

        assert decode_text(b"hello world text", opts).text == "hello world text"

    def test_newline_keep_leaves_crlf_and_cr(self) -> None:
        """Line endings are not rewritten."""
        opts = ReadOptions(normalization=Normalization(newline="keep"))

        assert decode_text(b"a\r\nb\rc", opts).text == "a\r\nb\rc"

    @pytest.mark.parametrize(
        ("form", "expected"),
        [
            ("NFKC", "fi é"),
            ("NFC", "ﬁ é"),
            ("NFD", "ﬁ é"),
            ("NFKD", "fi é"),
            ("none", "ﬁ é"),
        ],
    )
    def test_unicode_form_is_applied(self, form: str, expected: str) -> None:
        """Each form rewrites a ligature and an accent as its rules say."""
        raw = "ﬁ é".encode()
        opts = ReadOptions(
            encoding="utf-8", normalization=Normalization(unicode_form=form)
        )

        assert decode_text(raw, opts).text == expected

    def test_content_hash_depends_on_the_setting(self) -> None:
        """The hash covers the normalized text, so settings give different hashes."""
        raw = "\ufb01".encode()

        default = decode_text(raw, ReadOptions(encoding="utf-8"))
        unnormalized = decode_text(
            raw,
            ReadOptions(
                encoding="utf-8", normalization=Normalization(unicode_form="none")
            ),
        )

        assert default.content_hash != unnormalized.content_hash

    def test_raw_settings_keep_offsets_into_the_file(self) -> None:
        """With none, keep and keep, text equals the decoded file byte for byte."""
        source = "a\r\nb ﬁ é\r\n"
        opts = ReadOptions(
            encoding="utf-8",
            normalization=Normalization(
                bom="keep", newline="keep", unicode_form="none"
            ),
        )

        assert decode_text(source.encode(), opts).text == source
