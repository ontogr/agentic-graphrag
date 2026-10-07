"""Docling-native chunking.

This module wraps docling's ``HybridChunker`` to produce ``Chunk`` objects with
``PageProvenance``. It imports docling only when it chunks a document, so importing
this module does not require the ``docling`` extra.
"""

from typing import Any, Literal

from pydantic import Field

from agrag.chunking.base import DEFAULT_TOKENIZER, Chunker, ChunkerMissingExtraError
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.provenance import BoundingBox, PageProvenance, PageSpan


def _build_tokenizer(name: str, max_tokens: int) -> Any:
    """Build the tokenizer that docling's chunker counts with.

    Args:
        name: A tokenizer name. A name with a slash is a Hugging Face model id.
        max_tokens: The token budget of a chunk.

    Returns:
        The docling tokenizer.
    """
    from agrag.chunking._docling_adapters import build_tokenizer  # noqa: PLC0415

    return build_tokenizer(name, max_tokens)


class DoclingChunker(Chunker):
    """Splits a parsed docling document with docling's hybrid chunker.

    The chunker reads the parsed document that the docling loader keeps in
    ``Document.metadata["_docling_document"]``. Each chunk has page provenance and
    the headings above it in ``heading_path``. The chunk text is the body without
    headings, but headings count against the token budget. Chunk ids include the
    fingerprint, so a re-chunk with new settings does not overwrite the old chunks.

    Attributes:
        tokenizer: The tokenizer that counts size. A name with a slash is a Hugging
            Face model id, which needs the network the first time.
        max_tokens: The most tokens in a chunk, headings included.
        merge_peers: Whether to merge small neighbours under the same headings.
        repeat_table_header: Whether each chunk of a split table repeats its header.
        omit_header_on_overflow: Whether to drop headings from a chunk when they
            will not fit the budget.
        table_format: ``"triplet"`` writes ``row, column = value`` text and
            ``"markdown"`` writes a pipe table.
    """

    tokenizer: str = DEFAULT_TOKENIZER
    max_tokens: int = Field(default=1024, gt=0)
    merge_peers: bool = True
    repeat_table_header: bool = True
    omit_header_on_overflow: bool = False
    table_format: Literal["triplet", "markdown"] = "triplet"

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
        try:
            from docling.chunking import HybridChunker  # noqa: PLC0415

            from agrag.chunking._docling_adapters import (  # noqa: PLC0415
                MarkdownTableProvider,
            )
        except ImportError as exc:
            raise ChunkerMissingExtraError(self.strategy, "docling") from exc

        options: dict[str, Any] = {}
        if self.table_format == "markdown":
            options["serializer_provider"] = MarkdownTableProvider()
        hybrid = HybridChunker(
            tokenizer=_build_tokenizer(self.tokenizer, self.max_tokens),
            merge_peers=self.merge_peers,
            repeat_table_header=self.repeat_table_header,
            omit_header_on_overflow=self.omit_header_on_overflow,
            **options,
        )
        document_id = Document.node_id_for(document_key=document.resolved_document_key)
        version_id = Document.id_for(content_hash=document.content_hash)
        chunks: list[Chunk] = []
        for index, item in enumerate(hybrid.chunk(docling_doc)):
            provenance = PageProvenance(page_spans=_page_spans_for(item, docling_doc))
            chunks.append(
                Chunk(
                    id=Chunk.id_for(
                        document_id=document_id,
                        version_id=version_id,
                        provenance=provenance,
                        index=index,
                        chunker_hash=self.fingerprint(),
                    ),
                    document_id=document_id,
                    index=index,
                    text=getattr(item, "text", ""),
                    provenance=provenance,
                    heading_path=list(getattr(item.meta, "headings", None) or []),
                    content_kind=_content_kind(item),
                )
            )
        return chunks


def _content_kind(item: Any) -> Literal["text", "table_row"]:
    """Return ``"table_row"`` when every item of a docling chunk is a table."""
    doc_items = getattr(item.meta, "doc_items", None) or []
    if doc_items and all(
        getattr(getattr(i, "label", None), "value", None) == "table" for i in doc_items
    ):
        return "table_row"
    return "text"


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
        The equivalent agrag bounding box, or ``None`` when the box is
        bottom-left and the page height cannot be determined. The flip cannot
        be computed and returning an unflipped or zero-based box will be
        wrong.
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
