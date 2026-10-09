"""FinanceBench: questions on SEC filings and earnings releases.

The fixture lists the questions, their reference answers and evidence, and the hash
of each PDF. The PDFs come from a pinned commit of the benchmark repository at run
time, and Docling converts each one to Markdown. The conversion is slow on a CPU, so
its result is kept in the download cache, keyed by the PDF hash and the Docling
version.
"""

from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import TemporaryDirectory

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.loaders.corpus.errors import MissingExtraError
from agrag.loaders.corpus.types import ReadOptions, SourceRef
from benchmarks.datasets.base import DatasetAdapter, Domain
from benchmarks.datasets.fetch import CACHE_DIR, fetch_url
from benchmarks.grading.financial import FinancialGrader
from benchmarks.models import Corpus, CorpusManifest, Mode
from benchmarks.schemas.financial import FINANCIAL


DATASET_NAME = "financebench"
REPO = "patronus-ai/financebench"
COMMIT = "cc39aeb4afdf33909ee1412188bf89035950c2eb"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}"
QUESTIONS_FILE = "data/financebench_open_source.jsonl"
QUESTIONS_SHA256 = "a5a2aa673e573e55675fc3c0f9aa38c1cf59d2abc91edb077534f71f10a71877"
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "financial"
PDF_CACHE = CACHE_DIR / "financial"


def pdf_url(doc_name: str) -> str:
    """Return the URL of a PDF at the pinned commit.

    Args:
        doc_name: The FinanceBench document name, without the extension.

    Returns:
        The raw download URL of the PDF.
    """
    return f"{RAW_URL}/pdfs/{doc_name}.pdf"


def convert_pdf(path: Path, uri: str) -> str:
    """Convert a PDF to Markdown with the Docling loader.

    Args:
        path: The PDF file.
        uri: The document uri, for error messages.

    Returns:
        The Markdown text of the PDF.

    Raises:
        DocumentConversionError: Docling could not convert the PDF.
    """
    from agrag.loaders.docling.loader import DoclingPdfLoader  # noqa: PLC0415

    options = ReadOptions(max_document_bytes=path.stat().st_size + 1)
    source = SourceRef(uri=uri, extension=".pdf", byte_size=path.stat().st_size)
    with path.open("rb") as stream:
        (document,) = DoclingPdfLoader().load(source, stream, options)
    return document.text


def select_pages(source: Path, pages: Sequence[int], dest: Path) -> None:
    """Write the chosen zero-based pages of a PDF, in the order given, to ``dest``.

    Args:
        source: The PDF to read.
        pages: The zero-based pages to copy.
        dest: The file to write.
    """
    import pypdfium2  # noqa: PLC0415

    with pypdfium2.PdfDocument(source) as pdf, pypdfium2.PdfDocument.new() as chosen:
        chosen.import_pages(pdf, list(pages))
        chosen.save(dest)


def pdf_document(
    path: Path, *, uri: str, sha256: str, pages: Sequence[int] | None = None
) -> Document:
    """Build a prose document from a PDF, reusing a cached conversion.

    Args:
        path: The downloaded PDF.
        uri: The document uri.
        sha256: The hash of the PDF, which becomes the content hash.
        pages: The zero-based pages to convert, or None to convert them all.

    Returns:
        The prose document holding the Markdown of the PDF.

    Raises:
        MissingExtraError: The docling extra is not installed.
        DocumentConversionError: Docling could not convert the PDF.
    """
    try:
        docling = version("docling")
    except PackageNotFoundError as exc:
        raise MissingExtraError(".pdf", "docling") from exc
    chosen = "" if pages is None else ".p" + "-".join(map(str, pages))
    cached = PDF_CACHE / f"{sha256}{chosen}.docling-{docling}.md"
    if cached.exists():
        text = cached.read_text(encoding="utf-8")
    elif pages is None:
        text = convert_pdf(path, uri)
        cached.write_text(text, encoding="utf-8")
    else:
        # Docling stalls on a PDF made of several selected pages, so each page
        # converts alone.
        parts = []
        with TemporaryDirectory() as folder:
            for page in pages:
                sliced = Path(folder) / f"{page}.pdf"
                select_pages(path, [page], sliced)
                parts.append(convert_pdf(sliced, uri))
        text = "\n\n".join(parts)
        cached.write_text(text, encoding="utf-8")
    return Document(
        text=text,
        title=uri,
        uri=uri,
        source_format=SourceFormat.PDF,
        family=DocumentFamily.PROSE,
        content_hash=sha256,
        loader_name="docling",
        loader_version=docling,
        char_count=len(text),
        line_count=text.count("\n") + 1,
    )


class FinancialAdapter(DatasetAdapter):
    """The lite and full selections of FinanceBench."""

    def load(self, mode: Mode) -> CorpusManifest:
        """Return the manifest of one mode from its fixture.

        Args:
            mode: ``lite`` or ``full``.

        Returns:
            The corpora and questions of the mode.
        """
        text = (FIXTURE_DIR / f"{mode}.json").read_text(encoding="utf-8")
        return CorpusManifest.model_validate_json(text)

    def documents(self, corpus: Corpus) -> Sequence[Document]:
        """Download each PDF, check its hash and convert it with Docling.

        Args:
            corpus: The corpus whose documents to build.

        Returns:
            One prose document for each corpus document.

        Raises:
            MissingExtraError: The docling extra is not installed.
            HashMismatchError: A PDF differs from the fixture hash.
        """
        PDF_CACHE.mkdir(parents=True, exist_ok=True)
        documents = []
        for entry in corpus.documents:
            path = fetch_url(
                entry.source, entry.sha256, PDF_CACHE / f"{entry.sha256}.pdf"
            )
            documents.append(
                pdf_document(
                    path, uri=entry.uri, sha256=entry.sha256, pages=entry.pages
                )
            )
        return documents

    def schema(self, corpus: Corpus) -> GraphSchema:
        """Return the financial schema.

        Args:
            corpus: The corpus, which every financial corpus shares a schema with.

        Returns:
            The financial graph schema.
        """
        return FINANCIAL


DOMAIN = Domain(
    adapter=FinancialAdapter(),
    grader=FinancialGrader(),
    full_grader=FinancialGrader(full=True),
)
