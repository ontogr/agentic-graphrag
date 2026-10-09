"""Turn a parsed Docling document into sections and units."""

from dataclasses import dataclass

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
    NodeItem,
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


@dataclass(frozen=True, slots=True)
class DocumentBody:
    """The body items of a parsed document, read in one walk.

    Attributes:
        doc: The parsed document. Pages and caption references resolve through it.
        items: The body items in reading order. Groups are left out.
        captions: The references of the items that caption a table or picture.
        floating_members: The references of the items that sit inside a table or
            picture.
    """

    doc: DoclingDocument
    items: list[NodeItem]
    captions: frozenset[str]
    floating_members: frozenset[str]


def read_body(doc: DoclingDocument) -> DocumentBody:
    """Walk the body of a parsed document once.

    Args:
        doc: The parsed document.

    Returns:
        The body items, with the captions and the members of tables and pictures.
    """
    items: list[NodeItem] = []
    captions: set[str] = set()
    members: set[str] = set()
    # The levels of the open tables and pictures. The walk is depth first, so every
    # item at a deeper level than an open one sits inside it.
    open_floating: list[int] = []
    for item, level in doc.iterate_items(
        with_groups=False, included_content_layers=_BODY
    ):
        while open_floating and level <= open_floating[-1]:
            open_floating.pop()
        if open_floating:
            members.add(item.self_ref)
        items.append(item)
        if isinstance(item, FloatingItem):
            open_floating.append(level)
            captions.update(ref.cref for ref in item.captions)
    return DocumentBody(
        doc=doc,
        items=items,
        captions=frozenset(captions),
        floating_members=frozenset(members),
    )


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


def _caption(item: FloatingItem, doc: DoclingDocument) -> str | None:
    texts = []
    for ref in item.captions:
        target = ref.resolve(doc)
        if isinstance(target, TextItem):
            texts.append(target.text)
    return " ".join(texts) or None


def _table_rows(table: TableItem) -> tuple[list[list[str]], int]:
    grid = table.data.grid
    rows = [[cell.text for cell in row] for row in grid]
    header_rows = 0
    for row in grid:
        if not any(cell.column_header for cell in row):
            break
        header_rows += 1
    return rows, header_rows


def _open_section(
    sections: list[DocumentSection],
    open_headings: list[tuple[int, int]],
    heading: str,
    depth: int,
) -> None:
    """Start a section under the nearest open heading that is shallower than it.

    Args:
        sections: The sections so far. The new section is appended here.
        open_headings: The (depth, index) pairs of the headings that contain the
            next item. Popped to the new section's parent, then pushed.
        heading: The heading text.
        depth: The depth of the heading.
    """
    while open_headings and open_headings[-1][0] >= depth:
        open_headings.pop()
    parent = open_headings[-1][1] if open_headings else None
    sections.append(DocumentSection(heading=heading, depth=depth, parent=parent))
    open_headings.append((depth, len(sections) - 1))


def _append_list_item(
    units: list[Unit], item: ListItem, doc: DoclingDocument, group_before: str | None
) -> str | None:
    """Add a list item to the list unit that it continues, or start a new one.

    Args:
        units: The units of the section that holds the item.
        item: The list item.
        doc: The parsed document, for the item pages.
        group_before: The list group of the item before this one.

    Returns:
        The list group of this item, which the caller passes for the next item.
    """
    group = item.parent.cref if item.parent else None
    last = units[-1] if units else None
    if last and last.kind == UnitKind.LIST and group and group == group_before:
        last.text += "\n" + item.text
        last.pages.extend(_pages(item, doc))
    else:
        units.append(Unit(kind=UnitKind.LIST, text=item.text, pages=_pages(item, doc)))
    return group


def _without_empty_root(sections: list[DocumentSection]) -> list[DocumentSection]:
    """Drop the root section at index 0 when no content went into it.

    No heading section has the root as its parent, so only the parent indexes of the
    other sections shift.
    """
    if sections[0].units:
        return sections
    return [
        section.model_copy(
            update={"parent": None if section.parent is None else section.parent - 1}
        )
        for section in sections[1:]
    ]


def sections_from_docling(
    body: DocumentBody, depths: dict[str, int] | None = None
) -> list[DocumentSection]:
    """Return the sections of a parsed document, in reading order.

    A title has depth 0 and a section header has the depth of its level. Content
    before the first heading goes in a section with an empty heading. A list becomes
    one unit. A table or picture caption goes with the table or picture. Page headers,
    page footers and anything outside the document body are left out.

    Args:
        body: The body of the parsed document, from ``read_body``.
        depths: The depth to use for a heading, by item reference, in place of the
            level that Docling gave it.

    Returns:
        The sections. A section sits under the nearest earlier heading that is
        shallower than it.
    """
    depths = depths or {}
    doc = body.doc
    # The root holds the content before the first heading. It is dropped if empty.
    sections = [DocumentSection(heading="", depth=0)]
    open_headings: list[tuple[int, int]] = []
    list_group: str | None = None
    for item in body.items:
        if item.self_ref in body.captions:
            continue
        if isinstance(item, TextItem) and (
            item.label in _SKIPPED_LABELS or item.self_ref in body.floating_members
        ):
            continue
        if isinstance(item, TitleItem | SectionHeaderItem):
            depth = 0
            if isinstance(item, SectionHeaderItem):
                depth = depths.get(item.self_ref, item.level)
            _open_section(sections, open_headings, item.text, depth)
            list_group = None
            continue
        current = sections[open_headings[-1][1]] if open_headings else sections[0]
        if isinstance(item, ListItem):
            list_group = _append_list_item(current.units, item, doc, list_group)
            continue
        list_group = None
        unit = _unit(item, doc)
        if unit is not None:
            current.units.append(unit)
    return _without_empty_root(sections)


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
