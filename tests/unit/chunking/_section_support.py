"""Helpers shared by the section chunker tests."""

import hashlib

from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    DocumentSection,
    SourceFormat,
    Unit,
    UnitKind,
)
from agrag.common.data_models.provenance import BoundingBox, PageSpan


def paragraph(text: str) -> Unit:
    """Build a paragraph unit that has no source offsets."""
    return Unit(kind=UnitKind.PARAGRAPH, text=text)


def page_unit(text: str, page_no: int) -> Unit:
    """Build a paragraph unit on one page."""
    box = BoundingBox(x0=0, y0=0, x1=1, y1=1)
    return Unit(
        kind=UnitKind.PARAGRAPH,
        text=text,
        pages=[PageSpan(page_no=page_no, bbox=box)],
    )


def text_document(
    paragraphs: list[str], *, content_hash: str | None = None, key: str = "doc.txt"
) -> Document:
    """Build a one-section text document whose units point into its text."""
    text = "\n\n".join(paragraphs)
    units = []
    start = 0
    for body in paragraphs:
        units.append(
            Unit(
                kind=UnitKind.PARAGRAPH,
                text=body,
                char_start=start,
                char_end=start + len(body),
            )
        )
        start += len(body) + 2
    return Document(
        text=text,
        title="t",
        uri=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=content_hash or hashlib.sha256(text.encode("utf-8")).hexdigest(),
        loader_name="text",
        char_count=len(text),
        sections=[DocumentSection(heading="", depth=0, units=units)],
    )


def sectioned_document(
    sections: list[DocumentSection], *, content_hash: str | None = None
) -> Document:
    """Build a document with no text offsets around the given sections."""
    return Document(
        text="",
        title="t",
        uri="doc.pdf",
        source_format=SourceFormat.PDF,
        family=DocumentFamily.PROSE,
        content_hash=content_hash
        or hashlib.sha256(repr(sections).encode("utf-8")).hexdigest(),
        loader_name="docling",
        char_count=0,
        sections=sections,
    )


def record_document(text: str) -> Document:
    """Build a record row: text with no sections."""
    return Document(
        text=text,
        title="row",
        uri="rows.csv",
        source_format=SourceFormat.CSV,
        family=DocumentFamily.RECORD,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        loader_name="csv",
        char_count=len(text),
        record_index=0,
    )
