"""Plumbing types for the corpus loaders.

These types support the loader, decode, and walk machinery. They are feature-local to
``agrag.loaders.corpus`` and are not domain models. The shapes follow the design in
``thoughts/shared/research/2026-08-27-text-only-ingestion-formats.md`` section 3.2.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class SourceRef:
    """A locatable input, before any bytes are read.

    Attributes:
        uri: The location of the source, as the caller gave it.
        extension: The lowercased file extension, with its leading dot.
        byte_size: The size of the source in bytes. ``None`` when the backend cannot
        cheaply
            stat the source.
        mime_type: The detected MIME type, when the loader can detect one.
        modified_at: The last-modified time of the source, when the backend reports it.
    """

    uri: str
    extension: str
    byte_size: int | None = None
    mime_type: str | None = None
    modified_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class DecodedText:
    """Output of the four-step decode pipeline.

    Attributes:
        text: The decoded text, NFKC-normalized with LF line endings.
        encoding: The encoding used to decode the bytes.
        had_bom: Whether the source started with a byte-order mark.
        content_hash: The sha256 hash of the normalized text.
        char_count: The number of characters in ``text``.
        line_count: The number of lines in ``text``.
    """

    text: str
    encoding: str
    had_bom: bool
    content_hash: str
    char_count: int
    line_count: int


class ErrorPolicy(StrEnum):
    """The action to take when one source in a batch fails.

    RAISE: Stop the whole run with the first error.
    SKIP: Drop the failing source and count it.
    QUARANTINE: Set the failing source aside for review and count it.
    """

    RAISE = "raise"
    SKIP = "skip"
    QUARANTINE = "quarantine"


class JsonMode(StrEnum):
    """How to read a JSON source.

    AUTO: Read an array as records and an object as one document.
    RECORDS: Read a top-level array as one document per element.
    DOCUMENT: Read a top-level array as one document that holds the whole array.
    """

    AUTO = "auto"
    RECORDS = "records"
    DOCUMENT = "document"


class CsvMode(StrEnum):
    """How to read a CSV or TSV source.

    ROWS: Read one document per row.
    TABLE: Read the whole table as one document.
    """

    ROWS = "rows"
    TABLE = "table"


@dataclass(frozen=True, slots=True)
class ReadOptions:
    """Per-source reader configuration.

    Frozen so it is safe to share across worker processes.

    Attributes:
        encoding: The text encoding to use. ``None`` lets the decoder detect it.
        max_document_bytes: The largest prose source the loader will read.
        store_text: When false, the document text is an empty string.
        store_raw_record: When true, a record document keeps its raw row data.
        on_error: The error policy to apply inside the reader.
        text_column: The column that holds document text. Required for record sources.
        id_column: The column whose value becomes the document id.
        title_column: The column whose value becomes the document title.
        json_mode: The JSON reading mode.
        csv_mode: The CSV reading mode.
        csv_delimiter: The column separator. ``None`` infers it from the extension.
        html_selector: The CSS selector for the main content of an HTML source.
    """

    encoding: str | None = None
    max_document_bytes: int = 32 * 1024 * 1024
    store_text: bool = True
    store_raw_record: bool = False
    on_error: ErrorPolicy = ErrorPolicy.RAISE

    text_column: str | None = None
    id_column: str | None = None
    title_column: str | None = None
    json_mode: JsonMode = JsonMode.AUTO
    csv_mode: CsvMode = CsvMode.ROWS
    csv_delimiter: str | None = None

    html_selector: str | None = None


@dataclass(frozen=True, slots=True)
class LoaderCursor:
    """Resume point for a corpus walk.

    Ordering is deterministic, so a cursor is replayable.

    Attributes:
        uri: The source to resume after. ``None`` means start at the beginning.
        record_index: The record to resume after within the source. ``None`` means the
        start.
    """

    uri: str | None = None
    record_index: int | None = None


@dataclass(slots=True)
class LoadStats:
    """Running tally of a corpus walk.

    Attributes:
        documents: The number of documents read so far.
        sources: The number of sources read so far.
        bytes_read: The number of bytes read so far.
        skipped: The number of sources skipped so far.
        quarantined: The number of sources quarantined so far.
        quarantined_items: The uri and reason for each quarantined source so far.
    """

    documents: int = 0
    sources: int = 0
    bytes_read: int = 0
    skipped: int = 0
    quarantined: int = 0
    quarantined_items: list[tuple[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class IngestResult:
    """The result of one ingest call.

    Attributes:
        documents: The number of documents the call produced.
        sources: The number of sources the call read.
        skipped: The number of sources the call skipped.
        quarantined: The number of sources the call moved to quarantine.
        quarantined_items: The uri and reason for each quarantined source.
    """

    documents: int = 0
    sources: int = 0
    skipped: int = 0
    quarantined: int = 0
    quarantined_items: list[tuple[str, str]] = field(default_factory=list)
