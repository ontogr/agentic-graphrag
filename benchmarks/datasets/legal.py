"""LegalBench-RAG: questions on privacy policies, ANDAs and contracts.

The fixture lists the questions, their gold spans and the hash of each document.
The document text comes from a pinned Hugging Face mirror at run time.
"""

from collections.abc import Sequence
from pathlib import Path

from agrag.common.data_models.document import Document
from agrag.common.data_models.graph_schema import GraphSchema
from benchmarks.datasets.base import DatasetAdapter, Domain, text_document
from benchmarks.datasets.fetch import fetch_hf_file
from benchmarks.grading.legal_spans import LegalGrader
from benchmarks.models import Corpus, CorpusManifest, Mode
from benchmarks.schemas.legal import LEGAL


DATASET_NAME = "legalbench-rag-mini"
REPO = "awinml/legalbench-rag"
REVISION = "0263f7b2a9fb811f984ead05a0aa0d796a456124"
SOURCES = ("privacy_qa", "contractnli", "maud", "cuad")
# The SHA-256 of the four benchmark files, joined in the order of ``SOURCES``.
BENCHMARK_FILES_SHA256 = (
    "991d965c4e33873cd4db2cfc6e06786a2f313d6d9d310c798e69efde02e0906c"
)
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "legal"


def document_source(path: str) -> str:
    """Return where the fetch step gets the document at ``path``."""
    return f"hf://datasets/{REPO}@{REVISION}/corpus/{path}"


class LegalAdapter(DatasetAdapter):
    """The lite and full selections of LegalBench-RAG-mini."""

    def load(self, mode: Mode) -> CorpusManifest:
        """Return the manifest of one mode from its fixture."""
        text = (FIXTURE_DIR / f"{mode}.json").read_text(encoding="utf-8")
        return CorpusManifest.model_validate_json(text)

    def documents(self, corpus: Corpus) -> Sequence[Document]:
        """Fetch each document and keep its text exactly as gold spans index it.

        The file is read in text mode, so a CRLF pair becomes one LF, and the
        byte order mark stays as the first character. That is the text the gold
        offsets count in. A loader would strip or rewrite both.
        """
        documents = []
        for entry in corpus.documents:
            path = fetch_hf_file(
                REPO,
                f"corpus/{entry.uri}",
                revision=REVISION,
                sha256=entry.sha256,
            )
            documents.append(
                text_document(path.read_text(encoding="utf-8"), uri=entry.uri)
            )
        return documents

    def schema(self, corpus: Corpus) -> GraphSchema:
        """Return the legal schema."""
        return LEGAL


DOMAIN = Domain(adapter=LegalAdapter(), grader=LegalGrader())
