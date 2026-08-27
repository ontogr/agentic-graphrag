"""Shared helpers for the corpus readers."""

import hashlib
from pathlib import PurePosixPath

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.loaders.corpus.errors import MalformedRecordError
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
        MalformedRecordError: The caller named a column that the source does not have.
    """
    if text_column is not None:
        if text_column not in headers:
            raise MalformedRecordError(
                f"text_column {text_column!r} not found in columns {headers!r}"
            )
        return text_column

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
        opts: The read options, used for the id and text columns.
        record_index: The 0-based row number.
        record: The parsed record data.
        source_hash: The hash of the whole source file.
        title: The document title.

    Returns:
        The built Document.
    """
    text_column = resolve_text_column(list(record.keys()), opts.text_column)
    text = str(record.get(text_column, ""))
    record_id = str(record[opts.id_column]) if opts.id_column else None
    raw_record = record if opts.store_raw_record else None
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return Document(
        text=text,
        title=title,
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
