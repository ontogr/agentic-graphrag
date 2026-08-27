"""The Document model: one unit of source text, before chunking."""

from enum import StrEnum
from typing import Any
from uuid import NAMESPACE_OID, UUID, uuid5

from pydantic import BaseModel, Field, model_validator

from agrag.common.data_models.data_point import DataPoint


class DocumentFamily(StrEnum):
    """The shape of a document's source.

    Attributes:
        PROSE: One source file makes one document.
        RECORD: One source file makes many documents, one per record.
    """

    PROSE = "prose"
    RECORD = "record"


class SourceFormat(StrEnum):
    """A source format that a loader can read.

    The field that holds this value is named ``source_format``, not ``format``.
    ``format``
    is a Python builtin, and this project's lint rules reject builtin names for fields.
    """

    TXT = "txt"
    LOG = "log"
    MARKDOWN = "markdown"
    HTML = "html"
    ASCIIDOC = "asciidoc"
    XML = "xml"
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    TSV = "tsv"
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    IMAGE = "image"


class HeadingRef(BaseModel):
    """One heading in a document outline.

    Attributes:
        text: The heading text.
        level: The heading depth. A top-level heading has level 1.
        char_start: The start character offset of the heading in the document text. The
            chunker uses this offset to find which heading contains each chunk, since
            the
            base chunker does not detect headings on its own.
    """

    text: str
    level: int
    char_start: int


class Document(DataPoint):
    """One unit of source text, before chunking.

    A prose source, such as a Markdown file, makes one Document. A record source, such
    as a
    CSV file, makes one Document per row.

    The way the system computes ``content_hash`` depends on the loader. A text loader
    hashes
    the decoded text. A docling loader hashes the raw source bytes instead of the parsed
    output, because docling's parsed output can change between docling versions and
    between
    runs on different hardware.

    The system computes ``id`` from ``content_hash`` and ``record_id`` unless the caller
    passes ``id`` directly. Pass ``id`` only when rebuilding a document from stored
    data.

    Attributes:
        text: The document text. For a docling source, this holds docling's Markdown
        export.
            The chunker never reads this field for a docling source; see the ``Chunk``
            model
            for docling chunk content instead.
        title: The document title.
        uri: The location of the source. This value is not part of the document id.
        source_format: The format the loader used to read this document.
        family: The shape of the source: one document per file, or one document per
        record.
        content_hash: The hash that forms the document id.
        loader_name: The name of the loader that produced this document, for example
            ``"text"`` or ``"docling"``.
        loader_version: The version of the loader package. Does not affect the document
        id.
        encoding: The text encoding. Text loaders set this field; other loaders leave it
        empty.
        source_hash: The hash of the whole source file. Record-family documents set this
        field.
        char_count: The number of characters in ``text``.
        line_count: The number of lines in ``text``. Some loaders do not set this field.
        record_index: The 0-based row number in the source. Record-family documents set
        this
            field.
        record_id: The value from the configured id column. Record-family documents set
        this
            field only when the caller configures an id column.
        raw_record: The original record data. A loader sets this field only when the
        caller
            asks for it.
        heading_outline: The headings in the document, with their offsets. A text loader
        sets
            this field for a prose document.
    """

    id: UUID | None = None
    text: str
    title: str

    uri: str
    source_format: SourceFormat
    family: DocumentFamily
    content_hash: str
    loader_name: str
    loader_version: str | None = None

    encoding: str | None = None
    source_hash: str | None = None
    char_count: int
    line_count: int | None = None

    record_index: int | None = None
    record_id: str | None = None
    raw_record: dict[str, Any] | None = None

    heading_outline: list[HeadingRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _resolve_id(self) -> "Document":
        """Compute ``id`` from the content hash unless the caller passed one."""
        if self.id is None:
            self.id = self.id_for(
                content_hash=self.content_hash,
                record_id=self.record_id,
                record_index=self.record_index,
                source_hash=self.source_hash,
            )
        return self

    @property
    def resolved_id(self) -> UUID:
        """The document id, guaranteed non-``None`` once construction succeeds.

        ``id`` is typed as optional because callers may omit it and let
        ``_resolve_id`` derive it, but every constructed ``Document`` has a
        non-``None`` id by the time callers see it. Use this property instead of
        ``id`` where a non-optional value is required, such as building a ``Chunk``.

        Raises:
            RuntimeError: ``id`` is still ``None``, which means a validator was
                bypassed, for example via ``model_construct``.
        """
        if self.id is None:
            raise RuntimeError("Document.id was not resolved by its validator")
        return self.id

    @classmethod
    def id_for(
        cls,
        *,
        content_hash: str,
        record_id: str | None = None,
        record_index: int | None = None,
        source_hash: str | None = None,
    ) -> UUID:
        """Compute the document id.

        A record id, when given, wins over the content hash. Without a record id,
        a record-family document (``record_index`` is not ``None``) mixes in its
        source hash and row index, so two rows with identical text but no
        configured id column still get distinct ids.

        Args:
            content_hash: The document's content hash.
            record_id: The value from the configured id column, when the source has one.
            record_index: The 0-based row number, for a record-family document.
            source_hash: The hash of the whole source file, for a record-family
                document.

        Returns:
            The document id.
        """
        if record_id is not None:
            key = record_id
        elif record_index is not None:
            key = f"{source_hash}:{record_index}:{content_hash}"
        else:
            key = content_hash
        return uuid5(NAMESPACE_OID, f"Document:{key}")
