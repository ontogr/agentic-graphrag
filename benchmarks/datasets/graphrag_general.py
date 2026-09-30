"""GraphRAG-Bench: general questions on novels and on oncology guidelines.

The fixture lists the questions, their reference answers and evidence, and the hash of
each document. The document text comes from a pinned Hugging Face revision at run
time. The Medical corpus is one string of newline-separated guideline extracts, and
each extract is one document. Each novel is one document. The text is kept verbatim.
"""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from agrag.common.data_models.document import Document
from agrag.common.data_models.graph_schema import GraphSchema
from benchmarks.datasets.base import DatasetAdapter, Domain, text_document
from benchmarks.datasets.fetch import HashMismatchError, fetch_hf_file
from benchmarks.grading.graphrag_general import GraphRagGrader
from benchmarks.models import Corpus, CorpusManifest, Mode
from benchmarks.schemas.graphrag_general import MEDICAL, NOVEL


DATASET_NAME = "graphrag-bench"
REPO = "GraphRAG-Bench/GraphRAG-Bench"
REVISION = "dc3a111e77dbaf8bbaf51ef331f3cfc9b1b5c546"
CORPUS_FILES = {
    "medical": "Datasets/Corpus/medical.json",
    "novel": "Datasets/Corpus/novel.json",
}
QUESTION_FILES = {
    "medical": "Datasets/Questions/medical_questions.json",
    "novel": "Datasets/Questions/novel_questions.json",
}
FILE_SHA256 = {
    "Datasets/Corpus/medical.json": (
        "12eff34c994dcf101f83968c832bce15dab3c19176da855706f8c9b5cc208758"
    ),
    "Datasets/Corpus/novel.json": (
        "0e79a0dae5a420e8ee0ecffb04f7ddf8d441a4d868fbbe5a011baa2196b9702f"
    ),
    "Datasets/Questions/medical_questions.json": (
        "9af76a619e24d84f5509ba10274fbba465e901140a34c4429821f68686f0277b"
    ),
    "Datasets/Questions/novel_questions.json": (
        "90214823709fc5ff5858e1688c4efd56d64995ebbbcc70f6ab9e8953cc7dc43f"
    ),
}
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "graphrag_general"


def medical_pieces(blob: str) -> list[str]:
    """Split the Medical corpus into its guideline extracts, one per line."""
    pieces = blob.split("\n")
    if pieces and not pieces[-1]:
        pieces.pop()
    return pieces


def medical_piece_id(index: int) -> str:
    """Return the document id of the Medical extract at ``index``."""
    return f"medical-{index:02d}"


def text_sha256(text: str) -> str:
    """Return the SHA-256 of a document text as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def document_source(file: str, part: str) -> str:
    """Return where the fetch step gets one document of a corpus file."""
    return f"hf://datasets/{REPO}@{REVISION}/{file}#{part}"


def corpus_texts(kind: str) -> dict[str, str]:
    """Fetch a corpus file and return its document texts by document id.

    Args:
        kind: ``medical`` or ``novel``.

    Raises:
        HashMismatchError: The fetched file differs from its pinned hash.
    """
    file = CORPUS_FILES[kind]
    path = fetch_hf_file(REPO, file, revision=REVISION, sha256=FILE_SHA256[file])
    records = json.loads(path.read_text(encoding="utf-8"))
    if kind == "medical":
        pieces = medical_pieces(records[0]["context"])
        return {medical_piece_id(i): piece for i, piece in enumerate(pieces)}
    return {record["corpus_name"]: record["context"] for record in records}


class GraphRagAdapter(DatasetAdapter):
    """The lite and full selections of GraphRAG-Bench."""

    def load(self, mode: Mode) -> CorpusManifest:
        """Return the manifest of one mode from its fixture."""
        text = (FIXTURE_DIR / f"{mode}.json").read_text(encoding="utf-8")
        return CorpusManifest.model_validate_json(text)

    def documents(self, corpus: Corpus) -> Sequence[Document]:
        """Fetch the corpus text and build one document per extract or novel.

        Raises:
            HashMismatchError: A file or a document differs from its pinned hash.
        """
        kind = "medical" if corpus.schema_name == MEDICAL.name else "novel"
        texts = corpus_texts(kind)
        documents = []
        for entry in corpus.documents:
            text = texts[entry.id]
            if text_sha256(text) != entry.sha256:
                raise HashMismatchError(f"{entry.id}: text differs from the fixture")
            documents.append(text_document(text, uri=entry.uri, title=entry.id))
        return documents

    def schema(self, corpus: Corpus) -> GraphSchema:
        """Return the schema of the corpus: guidelines or general prose."""
        return MEDICAL if corpus.schema_name == MEDICAL.name else NOVEL


DOMAIN = Domain(adapter=GraphRagAdapter(), grader=GraphRagGrader())
