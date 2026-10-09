"""Tests for the docling loaders with mocked conversion.

The tests mock the converter so they run fast and without models or the network. The
integration suite runs the real PDF pipeline, and ``test_docling_sections.py`` runs
the real converter on small files that need no model.
"""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest


pytest.importorskip("docling")

from docling_core.types.doc import (  # noqa: E402
    BoundingBox,
    CoordOrigin,
    DocItemLabel,
    DoclingDocument,
    ProvenanceItem,
    Size,
)

from agrag.loaders.docling._sections import (  # noqa: E402
    read_body,
    sections_from_docling,
)
from agrag.loaders.docling.loader import DoclingLoader, DoclingPdfLoader  # noqa: E402
from agrag.loaders.errors import (  # noqa: E402
    DocumentConversionError,
    DocumentTooLargeError,
)
from agrag.loaders.types import ReadOptions, SourceRef  # noqa: E402


pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")

_RAW = b"# Title\n\nbody"


def _source(uri: str = "doc.md", size: int | None = len(_RAW)) -> SourceRef:
    return SourceRef(uri=uri, extension="." + uri.rsplit(".", 1)[1], byte_size=size)


class TestSourceLimits:
    """The loader refuses a source over the byte limit before it converts."""

    def test_oversized_source_raises_before_conversion(self) -> None:
        """A source over the limit never reaches the converter."""
        with patch("agrag.loaders.docling.loader.slim_converter") as converter:
            opts = ReadOptions(max_document_bytes=len(_RAW) - 1)
            with pytest.raises(DocumentTooLargeError):
                list(DoclingLoader().load(_source(), BytesIO(_RAW), opts))

        converter.assert_not_called()

    def test_unknown_byte_size_is_still_capped_at_the_limit(self) -> None:
        """A source with no reported size cannot be read past the limit."""
        with patch("agrag.loaders.docling.loader.slim_converter") as converter:
            opts = ReadOptions(max_document_bytes=len(_RAW) - 1)
            with pytest.raises(DocumentTooLargeError):
                list(DoclingLoader().load(_source(size=None), BytesIO(_RAW), opts))

        converter.assert_not_called()

    @pytest.mark.parametrize("limit", [0, -1, True])
    def test_rejects_a_limit_that_is_not_a_positive_integer(self, limit: int) -> None:
        """A bad limit is a caller error, not a conversion error."""
        opts = ReadOptions(max_document_bytes=limit)

        with pytest.raises(ValueError, match="positive integer"):
            list(DoclingLoader().load(_source(), BytesIO(_RAW), opts))


class TestConversionFailure:
    """Any failure while docling converts a source is an ingestion error."""

    @pytest.mark.parametrize("error", ["conversion", "os", "other"])
    def test_a_failed_conversion_raises_document_conversion_error(
        self, error: str
    ) -> None:
        """Walker policies such as SKIP catch only the wrapped error."""
        from docling.exceptions import ConversionError  # noqa: PLC0415

        failure = {
            "conversion": ConversionError("no model"),
            "os": OSError("disk"),
            "other": RuntimeError("model download failed"),
        }[error]
        with patch("agrag.loaders.docling.loader.slim_converter") as converter:
            converter.return_value.convert.side_effect = failure
            with pytest.raises(DocumentConversionError):
                list(DoclingLoader().load(_source(), BytesIO(_RAW), ReadOptions()))

    def test_a_pdf_failure_is_wrapped_too(self) -> None:
        """The PDF loader wraps the same way."""
        from docling.exceptions import ConversionError  # noqa: PLC0415

        pdf = b"%PDF-1.4 fake"
        with (
            patch("agrag.loaders.docling.loader.ocr_choice", return_value="off"),
            patch("agrag.loaders.docling.loader.pdf_converter") as converter,
        ):
            converter.return_value.convert.side_effect = ConversionError("no model")
            with pytest.raises(DocumentConversionError):
                list(
                    DoclingPdfLoader().load(
                        _source("doc.pdf", len(pdf)), BytesIO(pdf), ReadOptions()
                    )
                )


class TestRouting:
    """Each loader claims its own formats."""

    def test_pdf_and_images_belong_to_the_pdf_loader_only(self) -> None:
        """The slim loader needs no model, so it claims no PDF or image."""
        assert ".pdf" in DoclingPdfLoader.extensions
        assert ".png" in DoclingPdfLoader.extensions
        assert not DoclingLoader.extensions & DoclingPdfLoader.extensions

    def test_csv_and_xml_belong_to_neither(self) -> None:
        """Rows need their identity and XML has a core reader."""
        claimed = DoclingLoader.extensions | DoclingPdfLoader.extensions

        assert not claimed & {".csv", ".tsv", ".xml", ".txt", ".json"}

    def test_only_the_pdf_loader_needs_the_extra(self) -> None:
        """A bare install reads every format except PDF and images."""
        assert DoclingLoader.extra is None
        assert DoclingLoader().is_available()
        assert DoclingPdfLoader.extra == "docling"
        with patch("importlib.util.find_spec", return_value=None):
            assert not DoclingPdfLoader().is_available()


class TestPageBoxes:
    """Page boxes use a top-left origin."""

    def _document(self, box: BoundingBox) -> DoclingDocument:
        doc = DoclingDocument(name="t")
        doc.add_page(page_no=1, size=Size(width=100, height=200))
        doc.add_text(
            label=DocItemLabel.TEXT,
            text="x",
            prov=ProvenanceItem(page_no=1, bbox=box, charspan=(0, 1)),
        )
        return doc

    def test_a_bottom_left_box_is_flipped_with_the_page_height(self) -> None:
        """The new top is the page height minus the old top."""
        box = BoundingBox(l=10, t=190, r=50, b=150, coord_origin=CoordOrigin.BOTTOMLEFT)

        (section,) = sections_from_docling(read_body(self._document(box)))

        span = section.units[0].pages[0]
        assert (span.bbox.y0, span.bbox.y1) == (10, 50)
        assert (span.bbox.x0, span.bbox.x1) == (10, 50)

    def test_a_top_left_box_is_kept(self) -> None:
        """No conversion is needed."""
        box = BoundingBox(l=1, t=2, r=3, b=4, coord_origin=CoordOrigin.TOPLEFT)

        (section,) = sections_from_docling(read_body(self._document(box)))

        assert section.units[0].pages[0].bbox.y0 == 2

    def test_a_bottom_left_box_on_an_unknown_page_is_left_out(self) -> None:
        """The flip needs the page height, so the span is dropped."""
        doc = DoclingDocument(name="t")
        box = BoundingBox(l=10, t=190, r=50, b=150, coord_origin=CoordOrigin.BOTTOMLEFT)
        doc.add_text(
            label=DocItemLabel.TEXT,
            text="x",
            prov=ProvenanceItem(page_no=7, bbox=box, charspan=(0, 1)),
        )

        (section,) = sections_from_docling(read_body(doc))

        assert section.units[0].pages == []


def test_a_loaded_document_hashes_the_raw_bytes() -> None:
    """The content hash does not depend on what docling returns."""
    with patch("agrag.loaders.docling.loader.slim_converter") as converter:
        parsed = DoclingDocument(name="t")
        converter.return_value.convert.return_value = MagicMock(document=parsed)
        (document,) = DoclingLoader().load(_source(), BytesIO(_RAW), ReadOptions())

    import hashlib  # noqa: PLC0415

    assert document.content_hash == hashlib.sha256(_RAW).hexdigest()
