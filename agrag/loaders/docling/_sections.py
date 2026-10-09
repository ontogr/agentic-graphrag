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


# Six dotted parts covers "1.2.3.4.5.6"; deeper numbers are not read as depth.
_MAX_NUMBERING_DEPTH = 6
_NUMBERED = re.compile(rf"^\s*(\d+(?:\.\d+){{0,{_MAX_NUMBERING_DEPTH - 1}}})[.)]?\s+\S")
# A majority of numbered headings marks the outline as numbered; a few numbered
# titles in an otherwise unnumbered document must not reshape its sections.
_MIN_NUMBERED_SHARE = 0.5
# Fewer headings than this give too little evidence of a numbering scheme, so a
# lone "1." heading would otherwise set the depth of the whole outline.
_MIN_HEADINGS = 3


@dataclass(frozen=True, slots=True)
class DocumentBody:
    doc: DoclingDocument
    items: list[NodeItem]
    captions: frozenset[str]
    floating_members: frozenset[str]


class _FloatingScopes:
    """Floating items whose nested content the depth-first walk is still inside."""

    def __init__(self) -> None:
        self._levels: list[int] = []

    def open(self, level: int) -> None:
        self._levels.append(level)

    def contains(self, level: int) -> bool:
        """Pop ended scopes; report whether ``level`` is inside one."""
        while self._levels and level <= self._levels[-1]:
            self._levels.pop()
        return bool(self._levels)


def read_body(doc: DoclingDocument) -> DocumentBody:
    from docling_core.types.doc import ContentLayer, FloatingItem  # noqa: PLC0415

    items: list[NodeItem] = []
    captions: set[str] = set()
    members: set[str] = set()
    floating = _FloatingScopes()
    for item, level in doc.iterate_items(
        with_groups=False, included_content_layers={ContentLayer.BODY}
    ):
        if floating.contains(level):
            members.add(item.self_ref)
        items.append(item)
        if isinstance(item, FloatingItem):
            floating.open(level)
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


class _SectionTree:
    """Sections in document order, each nested under the heading open above it."""

    def __init__(self) -> None:
        self.sections: list[DocumentSection] = []
        self._preamble: DocumentSection | None = None
        self._open_headings: list[tuple[int, int]] = []

    def open_heading(self, heading: str, depth: int) -> None:
        while self._open_headings and self._open_headings[-1][0] >= depth:
            self._open_headings.pop()
        parent = self._open_headings[-1][1] if self._open_headings else None
        self.sections.append(
            DocumentSection(heading=heading, depth=depth, parent=parent)
        )
        self._open_headings.append((depth, len(self.sections) - 1))

    def current(self) -> DocumentSection:
        if self._open_headings:
            return self.sections[self._open_headings[-1][1]]
        # Content before the first heading has no heading to nest under, so it
        # goes to an unnamed section; this runs only before any heading opens,
        # which keeps that section first in the output.
        if self._preamble is None:
            self._preamble = DocumentSection(heading="", depth=0)
            self.sections.append(self._preamble)
        return self._preamble


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
    tree = _SectionTree()
    list_group: str | None = None
    list_texts: list[str] = []
    list_pages: list[PageSpan] = []

    def _flush_list() -> None:
        if list_texts:
            tree.current().units.append(
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
            tree.open_heading(item.text, _heading_depth(item, depths))
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
            tree.current().units.append(unit)
    _flush_list()
    return tree.sections


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
