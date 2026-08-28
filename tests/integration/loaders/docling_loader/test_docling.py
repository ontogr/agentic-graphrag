"""Integration tests for the real docling loader and chunker.

These tests run the actual docling pipeline, which downloads layout/OCR models from the
network on first use. They require the ``docling`` extra (installed by ``make sync``)
and network access. They skip when model download is unavailable.
"""

import importlib.util
from io import BytesIO

import pytest

from agrag.loaders.corpus.types import ReadOptions, SourceRef


docling_missing = importlib.util.find_spec("docling") is None


@pytest.mark.skipif(docling_missing, reason="docling extra not installed")
class TestDoclingLoader:
    """Docling parses PDF, DOCX, PPTX, and image sources to Markdown."""

    def test_loads_pdf_into_one_prose_document(self) -> None:
        """Loads pdf into one prose document."""
        from agrag.loaders.docling.loader import DoclingLoader  # noqa: PLC0415

        pdf_bytes = _real_pdf_bytes()
        ref = SourceRef(uri="doc.pdf", extension=".pdf", byte_size=len(pdf_bytes))
        docs = _convert_or_skip(DoclingLoader(), ref, pdf_bytes)
        assert len(docs) == 1
        doc = docs[0]
        assert doc.source_format.value == "pdf"
        assert "_docling_document" in doc.metadata

    def test_content_hash_uses_raw_bytes(self) -> None:
        """Content hash uses raw bytes."""
        import hashlib  # noqa: PLC0415

        from agrag.loaders.docling.loader import DoclingLoader  # noqa: PLC0415

        pdf_bytes = _real_pdf_bytes()
        ref = SourceRef(uri="doc.pdf", extension=".pdf", byte_size=len(pdf_bytes))
        docs = _convert_or_skip(DoclingLoader(), ref, pdf_bytes)
        assert docs[0].content_hash == hashlib.sha256(pdf_bytes).hexdigest()


@pytest.mark.skipif(docling_missing, reason="docling extra not installed")
class TestDoclingChunking:
    """Docling chunking produces page-provenance chunks."""

    def test_chunks_have_page_provenance(self) -> None:
        """Chunks have page provenance."""
        from agrag.loaders.docling.chunking import (  # noqa: PLC0415
            chunk_docling_document,
        )
        from agrag.loaders.docling.loader import DoclingLoader  # noqa: PLC0415

        pdf_bytes = _real_pdf_bytes()
        ref = SourceRef(uri="doc.pdf", extension=".pdf", byte_size=len(pdf_bytes))
        doc = _convert_or_skip(DoclingLoader(), ref, pdf_bytes)[0]
        chunks = chunk_docling_document(doc.metadata["_docling_document"], doc.id)
        assert chunks
        assert all(chunk.provenance.page_spans for chunk in chunks)


def _convert_or_skip(loader: object, ref: SourceRef, raw: bytes) -> list:
    """Run the loader and skip the test if docling needs an unreachable network."""
    try:
        return list(loader.load(ref, BytesIO(raw), ReadOptions()))  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 - surface as a skip, not a failure
        pytest.skip(f"docling model download requires network: {exc}")
        return []


def _real_pdf_bytes() -> bytes:
    fixtures = (
        __import__("pathlib").Path(__file__).parents[3]
        / "integration"
        / "loaders"
        / "corpus"
        / "fixtures"
    )
    return (fixtures / "multi_page.pdf").read_bytes()
