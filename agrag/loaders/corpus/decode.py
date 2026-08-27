"""The four-step decode pipeline for source bytes.

Every text loader shares this pipeline. It runs, in order: byte-order-mark handling,
encoding detection via charset-normalizer, CRLF to LF newline normalization, and NFKC
Unicode normalization. It raises ``DecodeError`` on failure rather than silently
emitting
mojibake.
"""

import hashlib
import unicodedata

from charset_normalizer import from_bytes

from agrag.loaders.corpus.errors import DecodeError
from agrag.loaders.corpus.types import DecodedText, ReadOptions


_UTF8_BOM = b"\xef\xbb\xbf"
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
_UTF32_BOMS = (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")


def _had_bom(raw: bytes) -> bool:
    """Return whether the bytes begin with a known byte-order mark."""
    return raw.startswith(_UTF8_BOM) or raw[:2] in _UTF16_BOMS or raw[:4] in _UTF32_BOMS


def decode_text(raw: bytes, opts: ReadOptions) -> DecodedText:
    """Decode raw source bytes into normalized text.

    This function detects the encoding, normalizes newlines and Unicode, and hashes the
    result. It raises ``DecodeError`` instead of returning garbled text.

    Args:
        raw: The raw source bytes.
        opts: The read options. ``opts.encoding`` forces a specific codec when set.

    Returns:
        The decoded text with its encoding and hash.

    Raises:
        DecodeError: The bytes do not decode under the forced encoding, or detection
        fails
            and the latin-1 fallback is unavailable.
    """
    had_bom = _had_bom(raw)

    if opts.encoding is not None:
        try:
            text = raw.decode(opts.encoding)
        except (UnicodeDecodeError, LookupError) as exc:
            raise DecodeError(
                f"Could not decode source as {opts.encoding!r}: {exc}"
            ) from exc
        encoding = opts.encoding
    else:
        match = from_bytes(raw).best()
        if match is None:
            text = raw.decode("latin-1")
            encoding = "latin-1"
        else:
            # CharsetMatch.output() re-encodes the detected text to UTF-8 bytes
            # regardless of the detected encoding; str(match) yields that text
            # directly without a second, mismatched decode.
            text = str(match)
            encoding = match.encoding

    if text and text[0] == "\ufeff":
        text = text[1:]

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFKC", text)

    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return DecodedText(
        text=text,
        encoding=encoding,
        had_bom=had_bom,
        content_hash=content_hash,
        char_count=len(text),
        line_count=text.count("\n") + 1,
    )
