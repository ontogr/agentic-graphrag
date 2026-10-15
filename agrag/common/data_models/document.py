"""The Document model: one unit of source text, before chunking."""

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import NAMESPACE_OID, UUID, uuid5

from pydantic import BaseModel, Field, JsonValue, model_validator

from agrag.common.data_models.data_point import DataPoint
from agrag.common.data_models.graph_record import NodeRecord
from agrag.common.data_models.normalization import Normalization
from agrag.common.data_models.provenance import PageSpan, check_page_spans


DOCUMENT_LABEL = "Document"


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
    XLSX = "xlsx"
    IMAGE = "image"


class UnitKind(StrEnum):
    """The kind of content in a unit.

    Attributes:
        PARAGRAPH: A paragraph of running text.
        LIST: A list. One unit holds all the items of one list.
        CODE: A block of code.
        FORMULA: A formula.
        FOOTNOTE: A footnote.
        TABLE: A table. Its rows are in ``Unit.rows``.
        FIGURE: A picture, chart, or diagram. Its text is the caption.
    """

    PARAGRAPH = "paragraph"
    LIST = "list"
    CODE = "code"
    FORMULA = "formula"
    FOOTNOTE = "footnote"
    TABLE = "table"
    FIGURE = "figure"


class Unit(BaseModel):
    """One piece of content in a section, such as a paragraph or a table.

    Attributes:
        kind: The kind of content.
        text: The text of the unit. For a table or figure, the caption, or an empty
            string when it has none.
        char_start: The start character offset of the unit in the document text. A
            text source sets this field. A source that has no text offsets leaves it
            empty.
        char_end: The end character offset of the unit, exclusive. Set together with
            ``char_start``.
        pages: The pages and boxes the unit covers. A source with page layout sets
            this field.
        caption: The caption of a table or figure.
        rows: The cell text of a table, row by row. A spanned cell repeats its text
            in every slot it covers. Empty for other kinds.
        header_rows: The number of leading rows of a table that are headers. Zero
            when the source does not mark them; see ``header_row_count``.
    """

    kind: UnitKind
    text: str
    char_start: int | None = None
    char_end: int | None = None
    pages: list[PageSpan] = Field(default_factory=list)
    caption: str | None = None
    rows: list[list[str]] = Field(default_factory=list)
    header_rows: int = Field(default=0, ge=0)

    @property
    def header_row_count(self) -> int:
        """Return how many leading rows of a table form its header.

        The count is ``header_rows``. When the source marks no header rows, the
        first row is the header for every table format, so the count is at
        least 1.
        """
        return max(self.header_rows, 1)

    @property
    def header(self) -> list[str]:
        """Return the column names of a table, one for each column.

        The names come from the first ``header_row_count`` rows, so the first
        row supplies them for every table format when the source marks no
        header rows. Chunk rendering uses these names, and ingestion stores
        them as the Table node ``columns``. Empty when the table has no rows.
        A spanned header cell repeats its text in every slot it covers, so
        each column keeps each text once.
        """
        if not self.rows:
            return []
        width = max(len(row) for row in self.rows)
        head = self.rows[: self.header_row_count]
        names: list[str] = []
        for column in range(width):
            parts = [
                row[column] for row in head if column < len(row) and row[column].strip()
            ]
            names.append(" ".join(dict.fromkeys(parts)))
        return names

    @model_validator(mode="after")
    def _check_span(self) -> "Unit":
        start, end = self.char_start, self.char_end
        if (start is None) != (end is None):
            raise ValueError("char_start and char_end must be set together")
        if start is not None and end is not None and not 0 <= start <= end:
            raise ValueError("a unit span must satisfy 0 <= char_start <= char_end")
        return self

    @model_validator(mode="after")
    def _check_caption_text(self) -> "Unit":
        if self.kind in (
            UnitKind.TABLE,
            UnitKind.FIGURE,
        ) and self.text != (self.caption or ""):
            raise ValueError(f"a {self.kind.value} unit's text must equal its caption")
        return self


class DocumentSection(BaseModel):
    """One heading of a document and the content directly under it.

    Sections are in reading order. A section has no text of its own: the units hold
    it. Content before the first heading, or in a document with no headings, goes in
    a section with an empty heading.

    Attributes:
        heading: The heading text. Empty for a section made for content that has no
            heading.
        depth: The heading depth. A top-level heading has depth 1. A document title
            or a section made for content with no heading has depth 0.
        parent: The positional index in ``Document.sections`` of the section that
            contains this one. ``None`` for a section that sits directly under
            the document. The index must come before this section, and the
            parent must be shallower. Always an int index, never a key or id.
        source_id: The id of the source record, such as a chat message id.
        units: The content directly under the heading, in reading order.
    """

    heading: str
    depth: int = Field(ge=0)
    parent: int | None = None
    source_id: str | None = None
    units: list[Unit] = Field(default_factory=list)


def _check_unit_provenance(unit: Unit, index: int, unit_index: int) -> None:
    try:
        check_page_spans(unit.pages)
    except ValueError as error:
        raise ValueError(f"section {index} unit {unit_index}: {error}") from error


class Document(DataPoint):
    """One unit of source text, before chunking.

    A prose source, such as a Markdown file, makes one Document. A record source,
    such as a CSV file, makes one Document per row.

    ``content_hash`` is always the sha256 of ``text``, whatever the loader. The
    chunk offsets index ``text``, so the hash names the text they point into.
    ``source_hash`` is the sha256 of the raw source bytes, and it is kept apart so
    that a change of converter output is still visible as a content change.

    ``id`` is always the persisted Document node id for ``document_key``. The
    system computes it, and an explicit ``id`` must equal that value.

    Attributes:
        text: The document text. For a docling source, this holds the docling
            Markdown export. The chunker does not read it for a docling source: the
            chunks come from ``sections``. The loaders leave it empty when
            ``store_text`` is off.
        title: The document title.
        published_at: The date the source says it was published, or ``None``.
        content_date: The date the content describes, or ``None``.
        uri: The location of the source. It is not part of the node id, which
            follows ``document_key``.
        source_format: The format the loader used to read this document.
        family: The shape of the source: one document per file, or one document per
            record.
        content_hash: The sha256 hex digest of ``text`` as UTF-8 bytes.
        loader_name: The name of the loader that produced this document, for example
            ``"text"`` or ``"docling"``.
        loader_version: The version of the loader package. Does not affect the
            document id.
        encoding: The text encoding. Text loaders set this field. Other loaders
            leave it empty.
        source_hash: The sha256 hex digest of the raw bytes of the source file.
            Every document read from a file sets this field. Inline text leaves it
            ``None``.
        char_count: The number of characters in ``text``.
        line_count: The number of lines in ``text``. Some loaders do not set this field.
        record_index: The 0-based row number in the source. Record-family documents
            set this field.
        record_id: The value from the configured id column. Record-family documents
            set this field only when the caller configures an id column.
        raw_record: The original record data. A loader sets this field only when the
            caller asks for it.
        sections: The headings of the document and the content under them, in reading
            order. A non-blank document with no headings has one section with an
            empty heading. A record row has none: its text is one unit of content.
            A document read without its text (``store_text`` off) has none either.
        document_key: The stable identifier for this document's persisted graph node.
            Independent of ``id``, which changes with every content edit. Defaults to
            ``uri`` when not supplied.
        normalization: How the loader normalized ``text``. ``None`` for a document
            that no text loader made, such as a docling document or one built by hand.
        schema_name: The name of the schema of the run that wrote the document.
            ``None`` for a document that no run stamped.
        schema_version: The version string of that schema.
        schema_fingerprint: The structure hash of that schema (see
            ``agrag.common.schema_fingerprint``).
        extraction_fingerprint: The hash of the descriptions, the extraction
            settings and the model name of that run.
    """

    id: UUID | None = None
    text: str
    title: str
    published_at: date | None = None
    content_date: date | None = None

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
    raw_record: dict[str, JsonValue] | None = None

    sections: list[DocumentSection] = Field(default_factory=list)
    document_key: str | None = None
    normalization: Normalization | None = None
    schema_name: str | None = None
    schema_version: str | None = None
    schema_fingerprint: str | None = None
    extraction_fingerprint: str | None = None

    @model_validator(mode="after")
    def _check_sections(self) -> "Document":
        last_end = 0
        for index, section in enumerate(self.sections):
            if section.parent is not None:
                if not 0 <= section.parent < index:
                    raise ValueError(
                        f"section {index} has parent {section.parent}, "
                        "which does not come before it"
                    )
                if section.depth <= self.sections[section.parent].depth:
                    raise ValueError(f"section {index} must be deeper than its parent")
            for unit_index, unit in enumerate(section.units):
                _check_unit_provenance(unit, index, unit_index)
                if unit.char_start is not None:
                    if unit.char_end is None:
                        raise ValueError(
                            f"section {index} unit {unit_index} "
                            "has char_start without char_end"
                        )
                    if not 0 <= unit.char_start <= unit.char_end <= len(self.text):
                        raise ValueError(
                            f"section {index} unit {unit_index} "
                            "spans outside the document text"
                        )
                    if unit.char_start < last_end:
                        raise ValueError(
                            f"section {index} unit {unit_index} "
                            "starts before the previous unit ends"
                        )
                    last_end = unit.char_end
                    if self.text[unit.char_start : unit.char_end] != unit.text:
                        raise ValueError(
                            f"section {index} unit {unit_index} "
                            "does not match the document text"
                        )
        return self

    @model_validator(mode="after")
    def _resolve_identity(self) -> "Document":
        """Default the document key, then set ``id`` from it.

        Raises:
            ValueError: ``id`` was passed and does not match the node id of the
                document key.
        """
        if self.document_key is None:
            if self.record_id is not None:
                self.document_key = f"{self.uri}:{self.record_id}"
            elif self.record_index is not None:
                self.document_key = f"{self.uri}:{self.record_index}"
            else:
                self.document_key = self.uri
        node_id = Document.node_id_for(document_key=self.resolved_document_key)
        if self.id is None:
            self.id = node_id
        elif self.id != node_id:
            raise ValueError(
                f"id {self.id} does not match the node id {node_id} "
                f"of document key {self.document_key!r}"
            )
        return self

    @property
    def resolved_document_key(self) -> str:
        """Return the document key. It is never ``None`` after construction succeeds.

        ``document_key`` is typed as optional because callers can omit it and
        let ``_resolve_document_key`` default it to ``uri``. Every constructed
        ``Document`` has a non-``None`` document key by the time callers see
        it. Use this property instead of ``document_key`` where a non-optional
        value is required, such as computing the persisted Document node id.

        Raises:
            RuntimeError: ``document_key`` is still ``None``, which means a validator
                was bypassed, for example via ``model_construct``.
        """
        if self.document_key is None:
            raise RuntimeError("Document.document_key was not resolved by a validator")
        return self.document_key

    @classmethod
    def node_id_for(cls, *, document_key: str) -> UUID:
        """Compute the persisted Document graph node id.

        The id is keyed on ``document_key``, not the content hash, so it stays
        the same across content changes to the same logical document. Every
        content version of a document shares one graph node with a changing
        content hash.

        Args:
            document_key: The document's stable key.

        Returns:
            The Document graph node id.
        """
        return uuid5(NAMESPACE_OID, f"Document:{document_key}")

    def to_node_record(self) -> NodeRecord:
        """Return this document as a GraphStore write record for its graph node.

        The record excludes ``text``: the persisted node exists for traversal and
        the update no-op check, not to duplicate the document body already held
        per-chunk.
        """
        properties: dict[str, object] = {
            "document_key": self.resolved_document_key,
            "uri": self.uri,
            "current_content_hash": self.content_hash,
            "title": self.title,
            "updated_at": datetime.now(UTC).isoformat(),
            "published_at": (
                self.published_at.isoformat() if self.published_at else None
            ),
            "content_date": (
                self.content_date.isoformat() if self.content_date else None
            ),
        }
        if self.schema_name is not None:
            properties["schema_name"] = self.schema_name
        if self.schema_version is not None:
            properties["schema_version"] = self.schema_version
        if self.schema_fingerprint is not None:
            properties["schema_fingerprint"] = self.schema_fingerprint
        if self.extraction_fingerprint is not None:
            properties["extraction_fingerprint"] = self.extraction_fingerprint
        return NodeRecord(
            id=self.node_id_for(document_key=self.resolved_document_key),
            labels=[DOCUMENT_LABEL],
            properties=properties,
        )
