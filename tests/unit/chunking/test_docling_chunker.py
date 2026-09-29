"""Tests for DoclingChunker on in-memory DoclingDocuments.

The documents are built with docling's own builder API, so no model, PDF or network
is needed. Page provenance conversion is covered in the docling loader tests.
"""

import sys

import pytest


pytest.importorskip("docling_core")

from agrag.chunking import ChunkingError, DoclingChunker  # noqa: E402
from agrag.common.data_models.chunk import Chunk  # noqa: E402
from agrag.common.data_models.document import (  # noqa: E402
    Document,
    DocumentFamily,
    SourceFormat,
)
from tests.unit.chunking._docling_support import docling_document  # noqa: E402


_LONG = " ".join(f"word{i}" for i in range(400))
_TABLE = [["Item", "Value"], ["alpha", "1"], ["beta", "2"], ["gamma", "3"]]


def _token_count(chunker: DoclingChunker, chunk: Chunk, document: Document) -> int:
    """Count tokens of a chunk with its headings, as docling budgets them."""
    from agrag.chunking.docling import _build_tokenizer  # noqa: PLC0415

    tokenizer = _build_tokenizer(chunker.tokenizer, chunker.max_tokens)
    return tokenizer.count_tokens("\n".join([*chunk.heading_path, chunk.text]))


class TestSplit:
    """Chunks stay in budget and carry headings."""

    def test_every_chunk_is_within_the_token_budget(self) -> None:
        """Contextualized chunk length never passes max_tokens."""
        document = docling_document(sections=[("Risk Factors", [_LONG, _LONG])])
        chunker = DoclingChunker(max_tokens=64)

        chunks = chunker.chunk(document)

        assert len(chunks) > 2
        assert all(_token_count(chunker, c, document) <= 64 for c in chunks)

    def test_heading_path_names_the_section(self) -> None:
        """Body chunks carry the heading above them, and text stays the body."""
        document = docling_document(
            sections=[("Risk Factors", ["Short body."]), ("Outlook", ["Other body."])]
        )

        chunks = DoclingChunker().chunk(document)

        assert [c.heading_path for c in chunks] == [["Risk Factors"], ["Outlook"]]
        assert all("Risk Factors" not in c.text for c in chunks)

    def test_document_without_headings_has_empty_paths(self) -> None:
        """A table with no heading above it gives an empty heading path."""
        document = docling_document(table=_TABLE)

        assert [c.heading_path for c in DoclingChunker().chunk(document)] == [[]]

    def test_heading_with_no_body_makes_no_chunk(self) -> None:
        """A heading alone has no text to chunk."""
        document = docling_document(sections=[("Empty", [])])

        assert DoclingChunker().chunk(document) == []

    def test_one_oversized_paragraph_is_split(self) -> None:
        """A paragraph above the budget is cut into several chunks."""
        document = docling_document(sections=[("Big", [_LONG])])

        assert len(DoclingChunker(max_tokens=50).chunk(document)) > 1

    def test_missing_parsed_document_raises(self) -> None:
        """No parsed docling document means no text fallback."""
        document = Document(
            text="plain",
            title="t",
            uri="u",
            source_format=SourceFormat.PDF,
            family=DocumentFamily.PROSE,
            content_hash="h",
            loader_name="docling",
            char_count=5,
        )

        with pytest.raises(ChunkingError, match="docling chunker"):
            DoclingChunker().chunk(document)


class TestMissingExtra:
    """A missing docling package gives the usual missing extra error."""

    def test_raises_a_clear_error_naming_the_extra(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """chunk() names the docling extra instead of raising a raw ImportError."""
        from agrag.chunking import ChunkerMissingExtraError  # noqa: PLC0415

        document = docling_document(sections=[("A", ["Body."])])
        monkeypatch.setitem(sys.modules, "docling", None)
        monkeypatch.setitem(sys.modules, "docling.chunking", None)

        with pytest.raises(ChunkerMissingExtraError, match="docling") as raised:
            DoclingChunker().chunk(document)

        assert raised.value.extra == "docling"


class TestTables:
    """Table chunks are marked and follow the table settings."""

    def test_table_only_chunk_is_marked_table_row(self) -> None:
        """A chunk made only of table items has content kind table_row."""
        chunks = DoclingChunker().chunk(docling_document(table=_TABLE))

        assert {c.content_kind for c in chunks} == {"table_row"}

    def test_mixed_chunk_stays_text(self) -> None:
        """A chunk with text and a table is not marked as a table."""
        document = docling_document(
            sections=[("Notes", ["Intro sentence."])],
            table=_TABLE,
            table_heading="Notes",
        )

        kinds = {c.content_kind for c in DoclingChunker().chunk(document)}

        assert "text" in kinds

    def test_markdown_format_changes_the_chunk_text(self) -> None:
        """table_format markdown writes a pipe table instead of triplets."""
        document = docling_document(table=_TABLE)

        triplet = DoclingChunker().chunk(document)[0].text
        markdown = DoclingChunker(table_format="markdown").chunk(document)[0].text

        assert "|" in markdown
        assert "|" not in triplet

    def test_header_repeats_on_each_table_chunk_when_asked(self) -> None:
        """With repeat_table_header, every split chunk of a table names the columns."""
        rows = [["Item", "Value"], *[[f"row{i}", str(i)] for i in range(30)]]
        document = docling_document(table=rows)

        with_header = DoclingChunker(
            max_tokens=40, table_format="markdown", repeat_table_header=True
        ).chunk(document)
        without = DoclingChunker(
            max_tokens=40, table_format="markdown", repeat_table_header=False
        ).chunk(document)

        assert len(with_header) > 1
        assert all("Item" in c.text for c in with_header)
        assert not all("Item" in c.text for c in without)


class TestSettings:
    """Settings are validated and part of the fingerprint."""

    def test_rejects_non_positive_budget(self) -> None:
        """max_tokens must be above zero."""
        with pytest.raises(ValueError, match="max_tokens"):
            DoclingChunker(max_tokens=0)

    @pytest.mark.parametrize(
        "change",
        [
            {"max_tokens": 512},
            {"tokenizer": "cl100k_base"},
            {"merge_peers": False},
            {"repeat_table_header": False},
            {"omit_header_on_overflow": True},
            {"table_format": "markdown"},
        ],
    )
    def test_each_setting_changes_the_fingerprint(self, change: dict) -> None:
        """No setting is left out of the hash."""
        assert DoclingChunker().fingerprint() != DoclingChunker(**change).fingerprint()

    def test_defaults_use_the_shared_tokenizer_and_1024_tokens(self) -> None:
        """The default matches the text strategies' tokenizer."""
        chunker = DoclingChunker()

        assert (chunker.tokenizer, chunker.max_tokens) == ("o200k_base", 1024)


class TestChunkIds:
    """Chunk ids follow the chunker settings."""

    def test_same_settings_give_same_ids(self) -> None:
        """Ids repeat for the same document and settings."""
        document = docling_document(sections=[("A", ["Body one."])])

        first = [c.id for c in DoclingChunker().chunk(document)]
        second = [c.id for c in DoclingChunker().chunk(document)]

        assert first == second

    def test_different_settings_give_different_ids(self) -> None:
        """A re-chunk with new settings does not overwrite chunk N."""
        document = docling_document(sections=[("A", ["Body one."])])

        old = {c.id for c in DoclingChunker(max_tokens=512).chunk(document)}
        new = {c.id for c in DoclingChunker(max_tokens=256).chunk(document)}

        assert not old & new
