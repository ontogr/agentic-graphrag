from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from docling_core.types.doc import (
        BoundingBox as DoclingBox,
    )
    from docling_core.types.doc import (
        DoclingDocument,
        FloatingItem,
        NodeItem,
        SectionHeaderItem,
        TableItem,
        TextItem,
        TitleItem,
    )

from agrag.common.data_models.document import DocumentSection, Unit, UnitKind
from agrag.common.data_models.provenance import BoundingBox, PageSpan


_NUMBERED = re.compile(r"^\s*(\d+(?:\.\d+){0,5})[.)]?\s+\S")
_MIN_NUMBERED_SHARE = 0.5
_MIN_HEADINGS = 3


@dataclass(frozen=True, slots=True)
class DocumentBody:
    doc: DoclingDocument
    items: list[NodeItem]
    captions: frozenset[str]
    floating_members: frozenset[str]


def read_body(doc: DoclingDocument) -> DocumentBody:
    from docling_core.types.doc import ContentLayer, FloatingItem  # noqa: PLC0415

    items: list[NodeItem] = []
    captions: set[str] = set()
    members: set[str] = set()
    open_floating: list[int] = []
    for item, level in doc.iterate_items(
        with_groups=False, included_content_layers={ContentLayer.BODY}
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


def numbering_depth(heading: str) -> int | None:
    match = _NUMBERED.match(heading)
    return None if match is None else match.group(1).count(".") + 1


def numbered_depths(body: DocumentBody) -> dict[str, int]:
    from docling_core.types.doc import SectionHeaderItem  # noqa: PLC0415

    headings = [item for item in body.items if isinstance(item, SectionHeaderItem)]
    if len(headings) < _MIN_HEADINGS or any(h.level != 1 for h in headings):
        return {}
    depths = {h.self_ref: numbering_depth(h.text) for h in headings}
    share = sum(depth is not None for depth in depths.values()) / len(headings)
    if share < _MIN_NUMBERED_SHARE:
        return {}
    return {ref: depth for ref, depth in depths.items() if depth is not None}


def _top_left(box: DoclingBox, height: float) -> DoclingBox:
    from docling_core.types.doc import CoordOrigin  # noqa: PLC0415

    if box.coord_origin == CoordOrigin.BOTTOMLEFT:
        return box.to_top_left_origin(height)
    return box


def _pages(item: TextItem | FloatingItem, doc: DoclingDocument) -> list[PageSpan]:
    from docling_core.types.doc import CoordOrigin  # noqa: PLC0415

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
    from docling_core.types.doc import TextItem  # noqa: PLC0415

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
    while open_headings and open_headings[-1][0] >= depth:
        open_headings.pop()
    parent = open_headings[-1][1] if open_headings else None
    sections.append(DocumentSection(heading=heading, depth=depth, parent=parent))
    open_headings.append((depth, len(sections) - 1))


def _heading_depth(
    item: TitleItem | SectionHeaderItem, depths: Mapping[str, int] | None
) -> int:
    from docling_core.types.doc import TitleItem  # noqa: PLC0415

    if isinstance(item, TitleItem):
        return 0
    return (depths or {}).get(item.self_ref, item.level)


def sections_from_docling(
    body: DocumentBody,
    depths: Mapping[str, int] | None = None,
) -> list[DocumentSection]:
    from docling_core.types.doc import (  # noqa: PLC0415
        DocItemLabel,
        ListItem,
        SectionHeaderItem,
        TextItem,
        TitleItem,
    )

    doc = body.doc
    sections: list[DocumentSection] = []
    open_headings: list[tuple[int, int]] = []
    list_group: str | None = None
    list_texts: list[str] = []
    list_pages: list[PageSpan] = []

    def _current() -> DocumentSection:
        if open_headings:
            return sections[open_headings[-1][1]]
        if not sections:
            sections.append(DocumentSection(heading="", depth=0))
        return sections[0]

    def _flush_list() -> None:
        if list_texts:
            _current().units.append(
                Unit(
                    kind=UnitKind.LIST,
                    text="\n".join(list_texts),
                    pages=[*list_pages],
                )
            )
        list_texts.clear()
        list_pages.clear()

    for item in body.items:
        if item.self_ref in body.captions:
            continue
        if isinstance(item, TextItem) and (
            item.label in {DocItemLabel.PAGE_HEADER, DocItemLabel.PAGE_FOOTER}
            or item.self_ref in body.floating_members
        ):
            continue
        if isinstance(item, TitleItem | SectionHeaderItem):
            _flush_list()
            list_group = None
            _open_section(
                sections, open_headings, item.text, _heading_depth(item, depths)
            )
            continue
        if isinstance(item, ListItem):
            group = item.parent.cref if item.parent else None
            if list_texts and (not group or group != list_group):
                _flush_list()
            list_group = group
            list_texts.append(item.text)
            list_pages.extend(_pages(item, doc))
            continue
        _flush_list()
        list_group = None
        unit = _unit(item, doc)
        if unit is not None:
            _current().units.append(unit)
    _flush_list()
    return sections


def _unit(item: NodeItem, doc: DoclingDocument) -> Unit | None:
    from docling_core.types.doc import (  # noqa: PLC0415
        CodeItem,
        DocItemLabel,
        FormulaItem,
        PictureItem,
        TableItem,
        TextItem,
    )

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
