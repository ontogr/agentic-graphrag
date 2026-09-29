"""Docling-native chunking.

This module wraps docling's ``HybridChunker`` to produce ``Chunk`` objects with
``PageProvenance``. It imports docling inside the chunking method so that importing
the module does not require the ``docling`` extra.
"""

from typing import Any

from agrag.chunking.base import Chunker
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.provenance import BoundingBox, PageProvenance, PageSpan


class DoclingChunker(Chunker):
    """Splits a parsed docling document with docling's hybrid chunker.

    The chunker reads the parsed document that the docling loader keeps in
    ``Document.metadata["_docling_document"]``. Each chunk has page provenance.
    Chunk ids come from the chunk index, so they are not stable across a re-parse.
    """

    @property
    def strategy(self) -> str:
        """The strategy name, ``"docling"``."""
        return "docling"

    def _split(self, document: Document) -> list[Chunk]:
        docling_doc = document.metadata.get("_docling_document")
        if docling_doc is None:
            raise self._error(
                document, 0, "the document has no parsed docling document"
            )
        from docling.chunking import HybridChunker  # noqa: PLC0415

        document_id = Document.node_id_for(document_key=document.resolved_document_key)
        version_id = Document.id_for(content_hash=document.content_hash)
        chunks: list[Chunk] = []
        for index, item in enumerate(HybridChunker().chunk(docling_doc)):
            page_spans = _page_spans_for(item, docling_doc)
            provenance = PageProvenance(page_spans=page_spans)
            chunks.append(
                Chunk(
                    id=Chunk.id_for(
                        document_id=document_id,
                        version_id=version_id,
                        provenance=provenance,
                        index=index,
                    ),
                    document_id=document_id,
                    index=index,
                    text=getattr(item, "text", ""),
                    provenance=provenance,
                    content_kind="text",
                )
            )
        return chunks


def _page_height(docling_doc: object, page_no: int) -> float:
    """Look up a docling page's height, in document coordinate units.

    Args:
        docling_doc: The parsed docling document.
        page_no: The page number to look up.

    Returns:
        The page height, or ``0.0`` when the document has no matching page.
    """
    pages = getattr(docling_doc, "pages", None) or {}
    page = pages.get(page_no)
    size = getattr(page, "size", None)
    return float(getattr(size, "height", 0.0))


def _to_agrag_bbox(bbox: Any, docling_doc: object, page_no: int) -> BoundingBox | None:
    """Map a docling ``BoundingBox`` to agrag's ``BoundingBox``.

    docling exposes boxes as ``l/t/r/b`` and marks whether the origin is top-left
    or bottom-left. agrag uses a top-left origin (``y0`` is the top edge). A
    bottom-left box measures ``t``/``b`` from the page's bottom edge, so converting
    it needs the page height, not just relabeling ``t`` and ``b``: the new top is
    ``page_height - old_t`` and the new bottom is ``page_height - old_b``.

    Args:
        bbox: The docling bounding box to convert.
        docling_doc: The parsed docling document, used to look up the page height
            for a bottom-left box.
        page_no: The page the box is on.

    Returns:
        The equivalent agrag bounding box, or ``None`` when the box is bottom-left
        and the page height cannot be determined, since the flip cannot be
        computed and returning an unflipped or zero-based box would be wrong.
    """
    left = float(bbox.l)
    right = float(bbox.r)
    if "BOTTOMLEFT" in str(getattr(bbox, "coord_origin", "")):
        page_height = _page_height(docling_doc, page_no)
        if page_height <= 0.0:
            return None
        top = page_height - float(bbox.t)
        bottom = page_height - float(bbox.b)
        return BoundingBox(x0=left, y0=top, x1=right, y1=bottom)
    return BoundingBox(x0=left, y0=float(bbox.t), x1=right, y1=float(bbox.b))


def _page_spans_for(item: object, docling_doc: object) -> list[PageSpan]:
    """Build the page spans for one docling chunk.

    Args:
        item: A docling chunk with ``meta.doc_items`` provenance.
        docling_doc: The parsed docling document the chunk came from, used to look
            up page heights for bottom-left boxes.

    Returns:
        One ``PageSpan`` per (page, bounding box) the chunk covers, in page order.
        A bottom-left box on a page whose height cannot be determined is omitted,
        since its coordinates cannot be converted.
    """
    spans: list[PageSpan] = []
    doc_items: list[Any] = getattr(getattr(item, "meta", None), "doc_items", []) or []
    for doc_item in doc_items:
        for prov in getattr(doc_item, "prov", []) or []:
            bbox = getattr(prov, "bbox", None)
            if bbox is None:
                continue
            page_no = int(getattr(prov, "page_no", 0))
            converted = _to_agrag_bbox(bbox, docling_doc, page_no)
            if converted is None:
                continue
            spans.append(PageSpan(page_no=page_no, bbox=converted))
    spans.sort(key=lambda span: span.page_no)
    return spans
