"""Tests for the four-step text decode pipeline."""

from agrag.loaders.corpus.decode import _had_bom, decode_text
from agrag.loaders.corpus.errors import DecodeError
from agrag.loaders.corpus.types import ReadOptions


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

        monkeypatch.setattr(
            "agrag.loaders.corpus.decode.from_bytes", lambda raw: _NoMatch()
        )
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
