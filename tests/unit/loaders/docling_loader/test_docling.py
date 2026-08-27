"""Tests for the docling loader and chunker using mocks.

These unit tests mock docling's heavy conversion and chunking so they run without the
optional ``docling`` extra or network access. The integration suite exercises the real
docling pipeline (model download requires network).
"""

import hashlib
import importlib
import importlib.util
from io import BytesIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from agrag.loaders.corpus.types import ReadOptions, SourceRef


pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")

docling_missing = importlib.util.find_spec("docling") is None


@pytest.mark.skipif(docling_missing, reason="docling extra not installed")
class TestDoclingLoader:
    """The loader wraps docling's Markdown export without real conversion."""

    def test_load_wraps_docling_output(self) -> None:
        """Loader builds a Document from docling's Markdown export."""
        from agrag.loaders.docling.loader import DoclingLoader  # noqa: PLC0415

        fake_document = MagicMock()
        fake_document.export_to_markdown.return_value = "# Title\n\nBody text"
        converted = MagicMock()
        converted.document = fake_document
        raw = b"%PDF-1.4 fake content"

        _docling_converter = importlib.import_module("docling.document_converter")

        with patch.object(_docling_converter, "DocumentConverter") as mock_converter:
            mock_converter.return_value.convert.return_value = converted
            ref = SourceRef(uri="doc.pdf", extension=".pdf", byte_size=len(raw))
            docs = list(DoclingLoader().load(ref, BytesIO(raw), ReadOptions()))

        assert len(docs) == 1
        doc = docs[0]
        assert doc.text == "# Title\n\nBody text"
        assert doc.source_format.value == "pdf"
        assert doc.loader_name == "docling"
        assert doc.content_hash == hashlib.sha256(raw).hexdigest()
        assert doc.metadata["_docling_document"] is fake_document

    def test_content_hash_uses_raw_bytes(self) -> None:
        """Content hash is derived from the raw source bytes, not the parse."""
        from agrag.loaders.docling.loader import DoclingLoader  # noqa: PLC0415

        fake_document = MagicMock()
        fake_document.export_to_markdown.return_value = "x"
        converted = MagicMock()
        converted.document = fake_document
        raw = b"some pdf bytes"

        _docling_converter = importlib.import_module("docling.document_converter")

        with patch.object(_docling_converter, "DocumentConverter") as mock_converter:
            mock_converter.return_value.convert.return_value = converted
            ref = SourceRef(uri="doc.pdf", extension=".pdf", byte_size=len(raw))
            docs = list(DoclingLoader().load(ref, BytesIO(raw), ReadOptions()))

        assert docs[0].content_hash == hashlib.sha256(raw).hexdigest()


@pytest.mark.skipif(docling_missing, reason="docling extra not installed")
class TestDoclingChunking:
    """The chunker wraps docling chunks without real model-backed chunking."""

    def test_chunk_wraps_items_with_page_provenance(self) -> None:
        """Chunker yields Chunks carrying text and page provenance.

        docling's bounding box uses ``l/t/r/b`` and a top-left origin, which maps
        directly onto agrag's ``BoundingBox`` (``x0=left``, ``y0=top``).
        """

        class _Bbox:
            l = 0.0  # noqa: E741
            t = 1.0
            r = 2.0
            b = 3.0
            coord_origin = "TOPLEFT"

        class _Prov:
            page_no = 1
            bbox = _Bbox()

        class _DocItem:
            prov = [_Prov()]

        class _Meta:
            doc_items = [_DocItem()]

        class _Item:
            text = "chunk one"
            meta = _Meta()

        from agrag.loaders.docling.chunking import (  # noqa: PLC0415
            chunk_docling_document,
        )

        fake_doc = MagicMock()

        _docling_chunking = importlib.import_module("docling.chunking")

        with patch.object(_docling_chunking, "HybridChunker") as mock_chunker:
            mock_chunker.return_value.chunk.return_value = [_Item()]
            chunks = chunk_docling_document(fake_doc, uuid4())

        assert len(chunks) == 1
        assert chunks[0].text == "chunk one"
        span = chunks[0].provenance.page_spans[0]
        assert span.page_no == 1
        assert (span.bbox.x0, span.bbox.y0, span.bbox.x1, span.bbox.y1) == (
            0.0,
            1.0,
            2.0,
            3.0,
        )

    def test_chunk_flips_y_axis_for_bottom_left_origin(self) -> None:
        """A bottom-left docling origin flips the vertical axis to agrag's top-left.

        In a bottom-left system ``t`` is the higher edge (near the bottom of the
        page) and ``b`` is the lower edge (near the top), so they swap roles when
        converted to agrag's top-left ``BoundingBox``.
        """

        class _Bbox:
            l = 0.0  # noqa: E741
            t = 738.984
            r = 497.52
            b = 715.19
            coord_origin = "BOTTOMLEFT"

        class _Prov:
            page_no = 2
            bbox = _Bbox()

        class _DocItem:
            prov = [_Prov()]

        class _Meta:
            doc_items = [_DocItem()]

        class _Item:
            text = "chunk two"
            meta = _Meta()

        from agrag.loaders.docling.chunking import (  # noqa: PLC0415
            chunk_docling_document,
        )

        fake_doc = MagicMock()

        _docling_chunking = importlib.import_module("docling.chunking")

        with patch.object(_docling_chunking, "HybridChunker") as mock_chunker:
            mock_chunker.return_value.chunk.return_value = [_Item()]
            chunks = chunk_docling_document(fake_doc, uuid4())

        span = chunks[0].provenance.page_spans[0]
        assert span.page_no == 2
        assert (span.bbox.x0, span.bbox.y0, span.bbox.x1, span.bbox.y1) == (
            0.0,
            715.19,
            497.52,
            738.984,
        )
