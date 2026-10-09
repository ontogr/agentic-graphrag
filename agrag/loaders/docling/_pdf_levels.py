"""Heading depth from dotted numbers, for PDFs whose headings all have level 1."""

import re

from docling_core.types.doc import SectionHeaderItem

from agrag.loaders.docling._sections import DocumentBody


_NUMBERED = re.compile(r"^\s*(\d+(?:\.\d+){0,5})[.)]?\s+\S")
_MIN_NUMBERED_SHARE = 0.5
_MIN_HEADINGS = 3


def numbering_depth(heading: str) -> int | None:
    """Return the number of dotted parts at the start of a heading.

    Args:
        heading: The heading text, such as ``"3.2.1 Results"``.

    Returns:
        The number of parts (``3`` for ``"3.2.1 Results"``), or ``None`` when the
        heading does not start with a number.
    """
    match = _NUMBERED.match(heading)
    return None if match is None else match.group(1).count(".") + 1


def numbered_depths(body: DocumentBody) -> dict[str, int]:
    """Return the depth of each numbered heading when numbering is the only signal.

    Docling gives a PDF heading a level above 1 only when a bookmark matches it. A
    document where every heading still has level 1 gets its depths from the numbers
    in the headings, if at least half of them are numbered.

    Args:
        body: The body of the parsed document, from ``read_body``.

    Returns:
        The depth by item reference. Empty when some heading has a level above 1,
        when the document has fewer than three headings, or when fewer than half of
        the headings are numbered.
    """
    headings = [item for item in body.items if isinstance(item, SectionHeaderItem)]
    if len(headings) < _MIN_HEADINGS or any(h.level != 1 for h in headings):
        return {}
    depths = {h.self_ref: numbering_depth(h.text) for h in headings}
    share = sum(depth is not None for depth in depths.values()) / len(headings)
    if share < _MIN_NUMBERED_SHARE:
        return {}
    return {ref: depth for ref, depth in depths.items() if depth is not None}
