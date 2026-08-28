"""Shared helpers for the corpus readers."""

import hashlib
from pathlib import PurePosixPath
from typing import BinaryIO

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.loaders.corpus.errors import DocumentTooLargeError, MalformedRecordError
from agrag.loaders.corpus.types import DecodedText, ReadOptions, SourceRef


EXTENSION_FORMAT: dict[str, SourceFormat] = {
    ".txt": SourceFormat.TXT,
    ".log": SourceFormat.LOG,
    ".md": SourceFormat.MARKDOWN,
    ".markdown": SourceFormat.MARKDOWN,
    ".html": SourceFormat.HTML,
    ".htm": SourceFormat.HTML,
    ".adoc": SourceFormat.ASCIIDOC,
    ".asciidoc": SourceFormat.ASCIIDOC,
    ".xml": SourceFormat.XML,
    ".json": SourceFormat.JSON,
    ".jsonl": SourceFormat.JSONL,
    ".ndjson": SourceFormat.JSONL,
    ".csv": SourceFormat.CSV,
    ".tsv": SourceFormat.TSV,
}

_DEFAULT_TEXT_COLUMNS = ("text", "body", "content", "description")


def read_within_limit(stream: BinaryIO, source: SourceRef, opts: ReadOptions) -> bytes:
    """Read a source's bytes without exceeding ``max_document_bytes``.

    Rejects a source whose known size already exceeds the limit before reading, and
    caps the actual read one byte past the limit so a source with no reported size
    cannot be buffered past the configured bound either.

    Args:
        stream: The open binary stream for the source.
        source: The source being read.
        opts: The read options, for ``max_document_bytes``.

    Returns:
        The source's raw bytes.

    Raises:
        DocumentTooLargeError: The source is, or would be, over the limit.
        ValueError: ``opts.max_document_bytes`` is not a positive integer.
    """
    limit = opts.max_document_bytes
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise ValueError("max_document_bytes must be a positive integer")
    if source.byte_size is not None and source.byte_size > opts.max_document_bytes:
        raise DocumentTooLargeError(
            f"{source.uri} is {source.byte_size} bytes, over the "
            f"{opts.max_document_bytes} limit"
        )
    raw = stream.read(opts.max_document_bytes + 1)
    if len(raw) > opts.max_document_bytes:
        raise DocumentTooLargeError(
            f"{source.uri} is over the {opts.max_document_bytes} byte limit"
        )
    return raw


def build_prose_document(
    *,
    source: SourceRef,
    text: str,
    encoding: str,
    source_format: SourceFormat,
    loader_name: str,
    opts: ReadOptions,
    title: str,
    heading_outline: list | None = None,
) -> Document:
    """Build a prose-family Document from final text.

    This function hashes ``text`` to form the content hash, so callers must pass the
    final text (the extracted main content for HTML, the raw decoded text otherwise).

    Args:
        source: The source the text came from.
        text: The final document text.
        encoding: The encoding used to decode the source.
        source_format: The format the loader used.
        loader_name: The name to record for the loader.
        opts: The read options, used for the ``store_text`` flag.
        title: The document title.
        heading_outline: The detected headings, when the loader tracks them.

    Returns:
        The built Document.
    """
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return Document(
        text=text if opts.store_text else "",
        title=title,
        uri=source.uri,
        source_format=source_format,
        family=DocumentFamily.PROSE,
        content_hash=content_hash,
        loader_name=loader_name,
        encoding=encoding,
        char_count=len(text),
        line_count=text.count("\n") + 1,
        heading_outline=list(heading_outline or []),
    )


def resolve_text_column(headers: list[str], text_column: str | None) -> str:
    """Pick the column that holds document text.

    When the caller passes ``text_column``, this function returns it after confirming
    the
    column exists. When the caller passes nothing, this function returns a common text
    column name (``text``, ``body``, ``content``, or ``description``) if present, and
    otherwise the last column.

    Args:
        headers: The column names in the record source.
        text_column: The column the caller asked for, when given.

    Returns:
        The chosen text column name.

    Raises:
        MalformedRecordError: The caller named a column that the source does not have,
            or the source has no columns at all.
    """
    if text_column is not None:
        if text_column not in headers:
            raise MalformedRecordError(
                f"text_column {text_column!r} not found in columns {headers!r}"
            )
        return text_column

    if not headers:
        raise MalformedRecordError("record has no columns to infer a text column from")

    for candidate in _DEFAULT_TEXT_COLUMNS:
        if candidate in headers:
            return candidate
    return headers[-1]


def source_title(source: SourceRef, fallback: str = "") -> str:
    """Derive a document title from the source uri.

    Args:
        source: The source to name.
        fallback: The title to use when the uri has no useful name.

    Returns:
        The file stem, or the fallback when the uri is not a file path.
    """
    name = PurePosixPath(source.uri).name
    return name or fallback


def record_source_hash(raw: bytes) -> str:
    """Hash the whole raw source bytes for a record-family document.

    Args:
        raw: The raw source bytes.

    Returns:
        The sha256 hex digest of the bytes.
    """
    return hashlib.sha256(raw).hexdigest()


def _resolve_record_id(
    record: dict, id_column: str | None, source: SourceRef
) -> str | None:
    """Resolve and validate the record id column, when configured.

    Args:
        record: The parsed record data.
        id_column: The column whose value becomes the record id, when configured.
        source: The source the record came from, for error messages.

    Returns:
        The record id, or ``None`` when no id column is configured.

    Raises:
        MalformedRecordError: The id column is configured but missing, null, or blank
            in this record. Silently falling back would collapse every such record
            onto the same document id.
    """
    if id_column is None:
        return None
    if id_column not in record or record[id_column] is None:
        raise MalformedRecordError(
            f"id_column {id_column!r} is missing or null in a record from {source.uri}"
        )
    value = str(record[id_column]).strip()
    if not value:
        raise MalformedRecordError(
            f"id_column {id_column!r} is blank in a record from {source.uri}"
        )
    return value


def _resolve_title(record: dict, title_column: str | None, fallback: str) -> str:
    """Resolve the record title from the configured title column.

    Args:
        record: The parsed record data.
        title_column: The column whose value becomes the title, when configured.
        fallback: The title to use when no title column is configured, or its value
            is missing or null in this record.

    Returns:
        The resolved title.
    """
    if title_column is None:
        return fallback
    value = record.get(title_column)
    return str(value) if value is not None else fallback


def build_record_document(
    *,
    source: SourceRef,
    decoded: DecodedText,
    source_format: SourceFormat,
    loader_name: str,
    opts: ReadOptions,
    record_index: int,
    record: dict,
    source_hash: str,
    title: str,
) -> Document:
    """Build a record-family Document from one row.

    Args:
        source: The source the record came from.
        decoded: The decoded text and its metadata.
        source_format: The format the loader used.
        loader_name: The name to record for the loader.
        opts: The read options, used for the id, title, and text columns.
        record_index: The 0-based row number.
        record: The parsed record data.
        source_hash: The hash of the whole source file.
        title: The fallback document title, used when ``opts.title_column`` is unset
            or absent from this record.

    Returns:
        The built Document.

    Raises:
        MalformedRecordError: ``opts.id_column`` is configured but missing, null, or
            blank in this record.
    """
    text_column = resolve_text_column(list(record.keys()), opts.text_column)
    raw_value = record.get(text_column)
    text = "" if raw_value is None else str(raw_value)
    record_id = _resolve_record_id(record, opts.id_column, source)
    resolved_title = _resolve_title(record, opts.title_column, title)
    raw_record = record if opts.store_raw_record else None
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return Document(
        text=text if opts.store_text else "",
        title=resolved_title,
        uri=source.uri,
        source_format=source_format,
        family=DocumentFamily.RECORD,
        content_hash=content_hash,
        loader_name=loader_name,
        encoding=decoded.encoding,
        source_hash=source_hash,
        char_count=len(text),
        record_index=record_index,
        record_id=record_id,
        raw_record=raw_record,
    )
