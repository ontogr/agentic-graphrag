"""Provenance types for a chunk.

A chunk's provenance shows where its text came from in the source. The shape of the
provenance depends on which chunker made the chunk.
"""

from typing import Literal

from pydantic import BaseModel


class TextProvenance(BaseModel):
    """The location of a chunk inside flattened document text.

    Attributes:
        kind: The literal tag ``"text"``. Marks this as text provenance.
        char_start: The start character offset in the document text.
        char_end: The end character offset in the document text.
        line_start: The start line number. Empty when the loader does not track lines.
        line_end: The end line number. Empty when the loader does not track lines.
    """

    kind: Literal["text"] = "text"
    char_start: int
    char_end: int
    line_start: int | None = None
    line_end: int | None = None


class BoundingBox(BaseModel):
    """A box on a page, in page coordinates.

    Attributes:
        x0: The left edge.
        y0: The top edge.
        x1: The right edge.
        y1: The bottom edge.
    """

    x0: float
    y0: float
    x1: float
    y1: float


class PageSpan(BaseModel):
    """One page's part of a chunk.

    Attributes:
        page_no: The page number.
        bbox: The box on the page that holds this part of the chunk.
    """

    page_no: int
    bbox: BoundingBox


class PageProvenance(BaseModel):
    """The location of a chunk across one or more pages.

    A chunk can start on one page and end on the next page. Each entry in ``page_spans``
    covers one page.

    Attributes:
        kind: The literal tag ``"page"``. Marks this as page provenance.
        page_spans: The page spans for this chunk. Has more than one entry when the
        chunk
            crosses a page boundary.
    """

    kind: Literal["page"] = "page"
    page_spans: list[PageSpan]
