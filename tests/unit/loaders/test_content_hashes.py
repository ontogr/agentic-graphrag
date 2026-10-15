"""Tests that loaders set the content hash to the hash of the document text.

``Document.content_hash`` is the sha256 of ``Document.text`` for every loader
family, so a hash names the text that the chunk offsets index. For a document
read from a file, ``Document.source_hash`` is the sha256 of the raw file bytes.
Covers inline text, prose files, record files in row and table modes, and a
Markdown file read through docling when the docling extra is installed.
"""

import hashlib
from importlib.util import find_spec
from io import BytesIO
from pathlib import Path

import pytest

from agrag.common.data_models.document import Document, SourceFormat
from agrag.loaders.common import build_prose_document
from agrag.loaders.docling.loader import DoclingLoader
from agrag.loaders.prose import TextLoader
from agrag.loaders.records import CsvLoader, JsonlLoader, JsonLoader
from agrag.loaders.types import CsvMode, ReadOptions, SourceRef


_FIXTURES = Path(__file__).parent / "fixtures"
_DOCLING_INSTALLED = find_spec("docling") is not None


def _sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _read(loader, name: str, extension: str, opts: ReadOptions) -> list[Document]:
    raw = (_FIXTURES / name).read_bytes()
    source = SourceRef(uri=name, extension=extension, byte_size=len(raw))
    return list(loader.load(source, BytesIO(raw), opts))


class TestInlineTextHash:
    """Inline text hashes the text that the document keeps."""

    def test_content_hash_is_the_sha256_of_the_text(self) -> None:
        """The hash of inline text equals the hash of the document text."""
        document = build_prose_document(
            source=SourceRef(uri="inline://sample", extension=".txt"),
            text="Inline text for the test. It has two sentences.",
            encoding="utf-8",
            source_format=SourceFormat.TXT,
            loader_name="inline",
            opts=ReadOptions(),
            title="inline",
        )

        assert document.content_hash == _sha256(document.text)


_FILE_CASES = [
    pytest.param(TextLoader(), "sample.txt", ".txt", ReadOptions(), id="text"),
    pytest.param(
        CsvLoader(),
        "sample.csv",
        ".csv",
        ReadOptions(csv_mode=CsvMode.TABLE),
        id="csv-table",
    ),
    pytest.param(CsvLoader(), "sample.csv", ".csv", ReadOptions(), id="csv-rows"),
    pytest.param(JsonlLoader(), "sample.jsonl", ".jsonl", ReadOptions(), id="jsonl"),
    pytest.param(
        JsonLoader(), "sample_object.json", ".json", ReadOptions(), id="json-object"
    ),
    pytest.param(
        DoclingLoader(),
        "sample.md",
        ".md",
        ReadOptions(),
        id="docling-markdown",
        marks=pytest.mark.skipif(
            not _DOCLING_INSTALLED, reason="docling not installed"
        ),
    ),
]


class TestFileDocumentHashes:
    """Each file document hashes its text and its raw source bytes."""

    @pytest.mark.parametrize(("loader", "name", "extension", "opts"), _FILE_CASES)
    def test_content_hash_is_the_sha256_of_the_text(
        self, loader, name: str, extension: str, opts: ReadOptions
    ) -> None:
        """The content hash of every document equals the hash of its text."""
        documents = _read(loader, name, extension, opts)

        assert documents
        for document in documents:
            assert document.content_hash == _sha256(document.text)

    @pytest.mark.parametrize(("loader", "name", "extension", "opts"), _FILE_CASES)
    def test_source_hash_is_the_sha256_of_the_file_bytes(
        self, loader, name: str, extension: str, opts: ReadOptions
    ) -> None:
        """The source hash of every document equals the hash of the file bytes."""
        raw = (_FIXTURES / name).read_bytes()

        documents = _read(loader, name, extension, opts)

        assert documents
        for document in documents:
            assert document.source_hash == _sha256(raw)
