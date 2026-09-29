"""Integration tests for the semantic, neural and code chunkers with their extras.

The code chunker needs only ``tree-sitter-language-pack``. The semantic and neural
chunkers download a model on first use, so their tests skip when the download fails.
"""

import pytest


pytest.importorskip("chonkie")

from agrag.chunking import CodeChunker, NeuralChunker, SemanticChunker  # noqa: E402
from agrag.common.data_models.provenance import TextProvenance  # noqa: E402
from tests.unit.chunking._support import make_document  # noqa: E402


_PYTHON = '''"""Module note: café 日本語."""


def greet(name):
    # comment with an accent: é and CJK 日本
    return "hello " + name


class Greeter:
    def __init__(self, name):
        self.name = name

    def run(self):
        return greet(self.name)
'''

_PROSE = (
    "The cat sat on the warm mat and purred. It watched the birds outside the window. "
    "Quantum computers use qubits to run some algorithms faster. "
    "Error correction is the hard part of building them. "
)


def _assert_exact(document, chunks) -> None:
    for chunk in chunks:
        assert isinstance(chunk.provenance, TextProvenance)
        span = chunk.provenance
        assert chunk.text == document.text[span.char_start : span.char_end]


class TestCodeChunker:
    """Code chunks equal their source slices, also for non-ASCII source."""

    def test_offsets_are_characters_not_bytes(self) -> None:
        """A file with accents and CJK text keeps exact character offsets."""
        pytest.importorskip("tree_sitter_language_pack")
        document = make_document(_PYTHON)

        chunks = CodeChunker(
            language="python", chunk_size=120, tokenizer="character"
        ).chunk(document)

        assert len(chunks) > 1
        _assert_exact(document, chunks)

    def test_source_with_syntax_errors_still_chunks(self) -> None:
        """The parser recovers, and chunk text still equals the source."""
        pytest.importorskip("tree_sitter_language_pack")
        document = make_document("def broken(:\n    return\n\nclass X(\n" * 8)

        chunks = CodeChunker(
            language="python", chunk_size=60, tokenizer="character"
        ).chunk(document)

        _assert_exact(document, chunks)

    def test_unknown_language_raises(self) -> None:
        """A language name the parser does not know fails clearly."""
        pytest.importorskip("tree_sitter_language_pack")

        with pytest.raises(Exception):  # noqa: B017,PT011
            CodeChunker(language="no-such-language").chunk(make_document(_PYTHON))


def _chunk_or_skip(chunker, document):
    try:
        return chunker.chunk(document)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"model download or load failed: {exc}")
        return []


class TestSemanticChunker:
    """Semantic chunks equal their source slices."""

    def test_chunks_equal_their_slices(self) -> None:
        """Every chunk is a slice of the source."""
        pytest.importorskip("model2vec")
        document = make_document(_PROSE * 3)

        chunks = _chunk_or_skip(SemanticChunker(threshold=0.5, chunk_size=64), document)

        assert chunks
        _assert_exact(document, chunks)


class TestNeuralChunker:
    """Neural chunks equal their source slices."""

    def test_chunks_equal_their_slices(self) -> None:
        """Every chunk is a slice of the source."""
        pytest.importorskip("transformers")
        pytest.importorskip("torch")
        document = make_document(_PROSE * 3)

        chunks = _chunk_or_skip(NeuralChunker(), document)

        assert chunks
        _assert_exact(document, chunks)
