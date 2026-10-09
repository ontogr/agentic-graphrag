"""Provenance types for a chunk.

A chunk's provenance shows where its text came from in the source. The shape of the
provenance depends on which chunker made the chunk.
"""

from typing import Literal

from pydantic import BaseModel, model_validator


class TextProvenance(BaseModel):
    """The location of a chunk inside flattened document text.

    The offsets index the normalized text in ``Document.text``, not the raw source.
    See ``Normalization``.

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


def check_page_spans(page_spans: list[PageSpan]) -> None:
    """Check that page spans number from 1, have ordered boxes, and are in order.

    Args:
        page_spans: The spans to check, in the order they were read.

    Raises:
        ValueError: A page number is below 1, a box has x0 > x1 or y0 > y1, or
            the page numbers are out of order.
    """
    for span in page_spans:
        if span.page_no < 1:
            raise ValueError(f"page_no {span.page_no} must be >= 1")
        box = span.bbox
        if not (box.x0 <= box.x1 and box.y0 <= box.y1):
            raise ValueError("a bbox needs x0 <= x1 and y0 <= y1")
    page_nos = [span.page_no for span in page_spans]
    if page_nos != sorted(page_nos):
        raise ValueError("page spans are out of order")


class PageProvenance(BaseModel):
    """The location of a chunk across one or more pages.

    A chunk can start on one page and end on the next page. Each entry in ``page_spans``
    covers one page.

    Attributes:
        kind: The literal tag ``"page"``. Marks this as page provenance.
        page_spans: The page spans for this chunk. Has more than one entry when
            the chunk crosses a page boundary.
    """

    kind: Literal["page"] = "page"
    page_spans: list[PageSpan]

    @model_validator(mode="after")
    def _check_page_spans(self) -> "PageProvenance":
        check_page_spans(self.page_spans)
        return self
