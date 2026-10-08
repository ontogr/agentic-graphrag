"""Turn a parsed Docling document into sections and units."""

from docling_core.types.doc import (
    BoundingBox as DoclingBox,
)
from docling_core.types.doc import (
    CodeItem,
    ContentLayer,
    CoordOrigin,
    DocItemLabel,
    DoclingDocument,
    FloatingItem,
    FormulaItem,
    ListItem,
    PictureItem,
    SectionHeaderItem,
    TableItem,
    TextItem,
    TitleItem,
)

from agrag.common.data_models.document import DocumentSection, Unit, UnitKind
from agrag.common.data_models.provenance import BoundingBox, PageSpan


_BODY = {ContentLayer.BODY}
_SKIPPED_LABELS = {DocItemLabel.PAGE_HEADER, DocItemLabel.PAGE_FOOTER}


def _top_left(box: DoclingBox, height: float) -> DoclingBox:
    if box.coord_origin == CoordOrigin.BOTTOMLEFT:
        return box.to_top_left_origin(height)
    return box


def _pages(item: TextItem | FloatingItem, doc: DoclingDocument) -> list[PageSpan]:
    spans: list[PageSpan] = []
    for prov in item.prov:
        page = doc.pages.get(prov.page_no)
        if page is None and prov.bbox.coord_origin == CoordOrigin.BOTTOMLEFT:
            continue
        height = page.size.height if page is not None else 0.0
        box = _top_left(prov.bbox, height)
        spans.append(
            PageSpan(
                page_no=prov.page_no,
                bbox=BoundingBox(x0=box.l, y0=box.t, x1=box.r, y1=box.b),
            )
        )
    return spans


def _under_floating(item: TextItem, doc: DoclingDocument) -> bool:
    """Return whether the item sits inside a table or picture."""
    parent = item.parent.resolve(doc) if item.parent else None
    while parent is not None:
        if isinstance(parent, FloatingItem):
            return True
        parent = parent.parent.resolve(doc) if getattr(parent, "parent", None) else None
    return False


def _caption(item: FloatingItem, doc: DoclingDocument) -> str | None:
    texts = []
    for ref in item.captions:
        target = ref.resolve(doc)
        if isinstance(target, TextItem):
            texts.append(target.text)
    return " ".join(texts) or None


def _table_rows(table: TableItem) -> tuple[list[list[str]], int]:
    # A spanned cell is one cell that fills every grid slot it covers.
    grid = table.data.grid
    rows = [[cell.text for cell in row] for row in grid]
    header_rows = 0
    for row in grid:
        if not any(cell.column_header for cell in row):
            break
        header_rows += 1
    return rows, header_rows


def sections_from_docling(
    doc: DoclingDocument, depths: dict[str, int] | None = None
) -> list[DocumentSection]:
    """Return the sections of a parsed document, in reading order.

    A title has depth 0 and a section header has the depth of its level. Content
    before the first heading goes in a section with an empty heading. A list becomes
    one unit. A table or picture caption goes with the table or picture. Page headers,
    page footers and anything outside the document body are left out.

    Args:
        doc: The parsed document.
        depths: The depth to use for a heading, by item reference, in place of the
            level that Docling gave it.

    Returns:
        The sections. A section sits under the nearest earlier heading that is
        shallower than it.
    """
    depths = depths or {}
    captioned = {
        ref.cref
        for item, _ in doc.iterate_items(
            with_groups=False, included_content_layers=_BODY
        )
        if isinstance(item, FloatingItem)
        for ref in item.captions
    }
    sections: list[DocumentSection] = []
    open_headings: list[tuple[int, int]] = []
    root: int | None = None
    list_group: str | None = None

    def current() -> DocumentSection:
        nonlocal root
        if open_headings:
            return sections[open_headings[-1][1]]
        if root is None:
            sections.append(DocumentSection(heading="", depth=0))
            root = len(sections) - 1
        return sections[root]

    for item, _ in doc.iterate_items(with_groups=False, included_content_layers=_BODY):
        if item.self_ref in captioned:
            continue
        if isinstance(item, TextItem) and (
            item.label in _SKIPPED_LABELS or _under_floating(item, doc)
        ):
            continue
        if isinstance(item, TitleItem | SectionHeaderItem):
            depth = 0
            if isinstance(item, SectionHeaderItem):
                depth = depths.get(item.self_ref, item.level)
            while open_headings and open_headings[-1][0] >= depth:
                open_headings.pop()
            parent = open_headings[-1][1] if open_headings else None
            sections.append(
                DocumentSection(heading=item.text, depth=depth, parent=parent)
            )
            open_headings.append((depth, len(sections) - 1))
            list_group = None
            continue
        if isinstance(item, ListItem):
            group = item.parent.cref if item.parent else None
            units = current().units
            last = units[-1] if units else None
            if last and last.kind == UnitKind.LIST and group and group == list_group:
                last.text += "\n" + item.text
                last.pages.extend(_pages(item, doc))
            else:
                units.append(
                    Unit(kind=UnitKind.LIST, text=item.text, pages=_pages(item, doc))
                )
            list_group = group
            continue
        list_group = None
        unit = _unit(item, doc)
        if unit is not None:
            current().units.append(unit)
    return sections


def _unit(item: object, doc: DoclingDocument) -> Unit | None:
    if isinstance(item, TableItem):
        rows, header_rows = _table_rows(item)
        caption = _caption(item, doc)
        return Unit(
            kind=UnitKind.TABLE,
            text=caption or "",
            caption=caption,
            rows=rows,
            header_rows=header_rows,
            pages=_pages(item, doc),
        )
    if isinstance(item, PictureItem):
        caption = _caption(item, doc)
        return Unit(
            kind=UnitKind.FIGURE,
            text=caption or "",
            caption=caption,
            pages=_pages(item, doc),
        )
    if isinstance(item, CodeItem):
        return Unit(kind=UnitKind.CODE, text=item.text, pages=_pages(item, doc))
    if isinstance(item, FormulaItem):
        return Unit(kind=UnitKind.FORMULA, text=item.text, pages=_pages(item, doc))
    if isinstance(item, TextItem):
        kind = (
            UnitKind.FOOTNOTE
            if item.label == DocItemLabel.FOOTNOTE
            else UnitKind.PARAGRAPH
        )
        return Unit(kind=kind, text=item.text, pages=_pages(item, doc))
    return None
