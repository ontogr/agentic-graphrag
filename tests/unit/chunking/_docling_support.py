"""Builds in-memory Docling documents for the chunker tests."""

from docling_core.types.doc import (
    BoundingBox,
    DocItemLabel,
    DoclingDocument,
    TableCell,
    TableData,
)
from docling_core.types.doc.document import ProvenanceItem

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat


def _prov(page_no: int = 1) -> ProvenanceItem:
    return ProvenanceItem(
        page_no=page_no, bbox=BoundingBox(l=0, t=0, r=10, b=10), charspan=(0, 1)
    )


def table_data(rows: list[list[str]]) -> TableData:
    """Build table data whose first row is the column header."""
    cells = [
        TableCell(
            text=text,
            start_row_offset_idx=r,
            end_row_offset_idx=r + 1,
            start_col_offset_idx=c,
            end_col_offset_idx=c + 1,
            column_header=r == 0,
        )
        for r, row in enumerate(rows)
        for c, text in enumerate(row)
    ]
    return TableData(table_cells=cells, num_rows=len(rows), num_cols=len(rows[0]))


def docling_document(
    *,
    sections: list[tuple[str, list[str]]] | None = None,
    table: list[list[str]] | None = None,
    table_heading: str | None = None,
    uri: str = "memory://docling",
    content_hash: str = "h",
) -> Document:
    """Build an agrag Document that carries an in-memory DoclingDocument.

    Args:
        sections: A heading and its paragraphs, per section.
        table: Rows of a table, header first, added under ``table_heading``.
        table_heading: The heading of the section that holds the table.
        uri: The document uri.
        content_hash: The document content hash.
    """
    parsed = DoclingDocument(name="test")
    for heading, paragraphs in sections or []:
        parent = parsed.add_heading(heading, level=1, prov=_prov())
        for paragraph in paragraphs:
            parsed.add_text(
                label=DocItemLabel.TEXT, text=paragraph, parent=parent, prov=_prov()
            )
    if table is not None:
        parent = (
            parsed.add_heading(table_heading, level=1, prov=_prov())
            if table_heading
            else None
        )
        parsed.add_table(data=table_data(table), parent=parent, prov=_prov(2))
    return Document(
        text="parsed",
        title="t",
        uri=uri,
        source_format=SourceFormat.PDF,
        family=DocumentFamily.PROSE,
        content_hash=content_hash,
        loader_name="docling",
        char_count=6,
        metadata={"_docling_document": parsed},
    )
