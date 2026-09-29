"""Tests for the Chunker contract in agrag.chunking.base.

A stub chunker returns whatever chunks a test hands it, so each way a strategy can
break the contract is checked against ``chunk()`` without a real splitter.
"""

from uuid import uuid4

import pytest

from agrag.chunking import Chunker, ChunkingError, RecursiveChunker, TokenChunker
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.provenance import TextProvenance
from tests.unit.chunking._support import make_document


class _Stub(Chunker):
    """Returns preset chunks."""

    label: str = "stub"
    made_by: str | None = None

    @property
    def strategy(self) -> str:
        return "stub"

    def _split(self, document: Document) -> list[Chunk]:
        return self._chunks

    _chunks: list[Chunk] = []


def _chunk(document: Document, start: int, end: int, index: int = 0) -> Chunk:
    return Chunk(
        document_id=Document.node_id_for(document_key=document.resolved_document_key),
        index=index,
        text=document.text[start:end],
        provenance=TextProvenance(char_start=start, char_end=end),
    )


def _run(document: Document, chunks: list[Chunk]) -> list[Chunk]:
    stub = _Stub()
    stub._chunks = chunks
    return stub.chunk(document)


class TestChunk:
    """chunk() accepts valid output and rejects each contract violation."""

    def test_stamps_strategy_and_fingerprint_on_every_chunk(self) -> None:
        """Each chunk names its chunker and carries the settings hash."""
        document = make_document("hello world")

        chunks = _run(document, [_chunk(document, 0, 5), _chunk(document, 6, 11, 1)])

        assert {c.chunker for c in chunks} == {"stub"}
        assert {c.chunker_hash for c in chunks} == {_Stub().fingerprint()}

    def test_keeps_a_chunker_name_the_strategy_set(self) -> None:
        """A strategy may record a finer name, such as a fallback."""
        document = make_document("hello")
        chunk = _chunk(document, 0, 5).model_copy(update={"chunker": "stub:inner"})

        assert _run(document, [chunk])[0].chunker == "stub:inner"

    @pytest.mark.parametrize(
        ("start", "end"), [(-1, 3), (0, 99), (4, 4)], ids=["before", "after", "empty"]
    )
    def test_rejects_span_outside_text(self, start: int, end: int) -> None:
        """A span outside the text raises, and the message names the chunk."""
        document = make_document("hello")
        chunk = _chunk(document, 0, 3).model_copy(
            update={"provenance": TextProvenance(char_start=start, char_end=end)}
        )

        with pytest.raises(ChunkingError, match="stub chunker.*chunk 0"):
            _run(document, [chunk])

    def test_rejects_chunks_out_of_order(self) -> None:
        """A later chunk that starts before an earlier one raises."""
        document = make_document("hello world")

        with pytest.raises(ChunkingError, match="out of order"):
            _run(document, [_chunk(document, 6, 11), _chunk(document, 0, 5, 1)])

    def test_rejects_empty_chunk_text(self) -> None:
        """A chunk with no text raises."""
        document = make_document("hello")
        chunk = _chunk(document, 0, 5).model_copy(update={"text": ""})

        with pytest.raises(ChunkingError, match="text is empty"):
            _run(document, [chunk])

    def test_rejects_text_that_differs_from_the_source(self) -> None:
        """Text that is not the slice at its span raises."""
        document = make_document("hello")
        chunk = _chunk(document, 0, 5).model_copy(update={"text": "HELLO"})

        with pytest.raises(ChunkingError, match="differs from the source"):
            _run(document, [chunk])

    def test_rejects_index_gap(self) -> None:
        """Indexes must run from zero without gaps."""
        document = make_document("hello world")

        with pytest.raises(ChunkingError, match="index is 2"):
            _run(document, [_chunk(document, 0, 5), _chunk(document, 6, 11, 2)])

    def test_accepts_overlapping_spans(self) -> None:
        """Neighbouring spans may overlap."""
        document = make_document("hello world")

        chunks = _run(document, [_chunk(document, 0, 8), _chunk(document, 4, 11, 1)])

        assert [c.text for c in chunks] == ["hello wo", "o world"]


class TestLevels:
    """chunk() checks indexes per level and that children lie inside parents."""

    def _pair(self, document: Document, child_span: tuple[int, int]) -> list[Chunk]:
        parent = _chunk(document, 0, 5).model_copy(update={"level": 1})
        child = _chunk(document, *child_span).model_copy(
            update={"parent_id": parent.id}
        )
        return [parent, child]

    def test_accepts_indexes_that_restart_for_each_level(self) -> None:
        """A parent 0 and a child 0 are both valid."""
        document = make_document("hello world")

        chunks = _run(document, self._pair(document, (0, 3)))

        assert [(c.level, c.index) for c in chunks] == [(1, 0), (0, 0)]

    def test_rejects_a_child_outside_its_parent(self) -> None:
        """A child span that leaves the parent span breaks the contract."""
        document = make_document("hello world")

        with pytest.raises(ChunkingError, match="outside its parent"):
            _run(document, self._pair(document, (6, 11)))

    def test_rejects_a_child_whose_parent_is_missing(self) -> None:
        """A parent id that names no chunk breaks the contract."""
        document = make_document("hello world")
        child = _chunk(document, 0, 3).model_copy(update={"parent_id": uuid4()})

        with pytest.raises(ChunkingError, match="parent"):
            _run(document, [child])


class TestFingerprint:
    """The fingerprint names the settings and nothing else."""

    def test_equal_settings_give_equal_fingerprints(self) -> None:
        """Two chunkers built the same way match."""
        assert RecursiveChunker(chunk_size=99).fingerprint() == (
            RecursiveChunker(chunk_size=99).fingerprint()
        )

    @pytest.mark.parametrize(
        "other",
        [
            RecursiveChunker(chunk_size=100),
            RecursiveChunker(tokenizer="character"),
            RecursiveChunker(min_characters_per_chunk=30),
            TokenChunker(chunk_size=99),
        ],
    )
    def test_any_changed_setting_or_strategy_changes_it(self, other: Chunker) -> None:
        """Each setting, and the strategy, is part of the fingerprint."""
        assert RecursiveChunker(chunk_size=99).fingerprint() != other.fingerprint()

    def test_copy_with_changes_rebuilds_the_fingerprint_and_the_splitter(self) -> None:
        """A changed copy behaves like a chunker built with the new settings."""
        original = RecursiveChunker(chunk_size=8, tokenizer="character")
        changed = original.model_copy(update={"chunk_size": 64})
        document = make_document("word " * 40)

        assert changed.fingerprint() == (
            RecursiveChunker(chunk_size=64, tokenizer="character").fingerprint()
        )
        assert changed.fingerprint() != original.fingerprint()
        assert len(changed.chunk(document)) < len(original.chunk(document))

    def test_copy_rejects_an_invalid_change(self) -> None:
        """A changed copy is validated like a new chunker."""
        with pytest.raises(ValueError, match="chunk_size"):
            RecursiveChunker().model_copy(update={"chunk_size": 0})

    def test_settings_are_json_data_that_name_the_strategy(self) -> None:
        """settings() lists the strategy and every field."""
        assert RecursiveChunker(chunk_size=5, tokenizer="character").settings() == {
            "strategy": "recursive",
            "chunk_size": 5,
            "tokenizer": "character",
            "min_characters_per_chunk": 24,
            "levels": None,
        }

    def test_fingerprint_is_stable_across_processes(self) -> None:
        """The hash of fixed settings is a fixed value, not tied to a process."""
        assert RecursiveChunker(chunk_size=99, tokenizer="character").fingerprint() == (
            "3a7895fba8458c65"
        )
