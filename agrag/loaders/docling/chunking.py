"""Docling-native chunking.

This module wraps docling's ``HybridChunker`` to produce ``Chunk`` objects with
``PageProvenance``. It imports docling inside the chunking function so that importing
the
module does not require the ``docling`` extra.
"""

from typing import Any
from uuid import UUID

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.provenance import BoundingBox, PageProvenance, PageSpan


def chunk_docling_document(docling_doc: object, document_id: UUID) -> list[Chunk]:
    """Split a docling document into chunks with page provenance.

    A chunk that crosses a page boundary produces more than one ``PageSpan``. The spans
    come from every provenance entry across every docling item the chunk covers.

    Args:
        docling_doc: The parsed docling document to chunk.
        document_id: The id of the parent Document.

    Returns:
        The chunks, in document order.
    """
    from docling.chunking import (  # noqa: PLC0415
        HybridChunker,
    )

    chunker = HybridChunker()
    chunks: list[Chunk] = []
    for index, item in enumerate(chunker.chunk(docling_doc)):  # ty: ignore[invalid-argument-type]
        text = getattr(item, "text", "")
        page_spans = _page_spans_for(item)
        chunks.append(
            Chunk(
                document_id=document_id,
                index=index,
                text=text,
                provenance=PageProvenance(page_spans=page_spans),
                content_kind="text",
            )
        )
    return chunks


def _to_agrag_bbox(bbox: Any) -> BoundingBox:
    """Map a docling ``BoundingBox`` to agrag's ``BoundingBox``.

    docling exposes boxes as ``l/t/r/b`` and marks whether the origin is top-left
    or bottom-left. agrag uses a top-left origin (``y0`` is the top edge), so a
    bottom-left origin must have its vertical axis flipped.

    Args:
        bbox: The docling bounding box to convert.

    Returns:
        The equivalent agrag bounding box.
    """
    left = float(bbox.l)
    top = float(bbox.t)
    right = float(bbox.r)
    bottom = float(bbox.b)
    if "BOTTOMLEFT" in str(getattr(bbox, "coord_origin", "")):
        return BoundingBox(x0=left, y0=bottom, x1=right, y1=top)
    return BoundingBox(x0=left, y0=top, x1=right, y1=bottom)


def _page_spans_for(item: object) -> list[PageSpan]:
    """Build the page spans for one docling chunk.

    Args:
        item: A docling chunk with ``meta.doc_items`` provenance.

    Returns:
        One ``PageSpan`` per (page, bounding box) the chunk covers, in page order.
    """
    spans: list[PageSpan] = []
    doc_items: list[Any] = getattr(getattr(item, "meta", None), "doc_items", []) or []
    for doc_item in doc_items:
        for prov in getattr(doc_item, "prov", []) or []:
            bbox = getattr(prov, "bbox", None)
            if bbox is None:
                continue
            spans.append(
                PageSpan(
                    page_no=int(getattr(prov, "page_no", 0)),
                    bbox=_to_agrag_bbox(bbox),
                )
            )
    spans.sort(key=lambda span: span.page_no)
    return spans
