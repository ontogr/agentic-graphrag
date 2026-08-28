"""Tests for the corpus walk, batching, and resume."""

from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

import pytest

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.loaders.corpus import registry
from agrag.loaders.corpus._walk import _CorpusWalk, _InMemoryWalk
from agrag.loaders.corpus.base import Loader
from agrag.loaders.corpus.errors import DecodeError, MalformedRecordError
from agrag.loaders.corpus.types import ErrorPolicy, LoaderCursor, ReadOptions, SourceRef


_FIXTURES = Path(__file__).parent / "fixtures"
_CSV = _FIXTURES / "sample.csv"
_FILES = sorted(p for p in _FIXTURES.rglob("*") if p.is_file())
_SINGLE_DOC_FILES = [
    _FIXTURES / "sample.txt",
    _FIXTURES / "sample.md",
    _FIXTURES / "sample.log",
]


async def _collect(walk, start: LoaderCursor | None = None):
    docs = []
    async for batch, _cursor, _stats in walk.iter_batches(start=start):
        docs.extend(batch)
    return docs


class TestCorpusWalk:
    """The walk orders sources, then yields batches."""

    async def test_walks_files_and_counts(self) -> None:
        """Walks files and counts."""
        walk = _CorpusWalk(_FILES, registry=registry, opts=ReadOptions())
        docs = await _collect(walk)
        assert len(docs) > 0

    async def test_batching_respects_batch_size(self) -> None:
        """Batching respects batch size."""
        walk = _CorpusWalk(
            _SINGLE_DOC_FILES, registry=registry, opts=ReadOptions(), batch_size=1
        )
        batches = [batch async for batch, _c, _s in walk.iter_batches()]
        assert batches
        assert all(len(batch) <= 1 for batch in batches)

    async def test_resume_record_source_skips_processed_rows(self) -> None:
        """Resume record source skips processed rows."""
        walk = _CorpusWalk([_CSV], registry=registry, opts=ReadOptions())
        full = await _collect(walk)
        assert len(full) == 3
        cursor = LoaderCursor(uri=str(_CSV), record_index=len(full))
        resumed = await _collect(
            _CorpusWalk([_CSV], registry=registry, opts=ReadOptions()), start=cursor
        )
        assert len(resumed) == 0

    async def test_resume_past_record_index_continues(self) -> None:
        """Resume past record index continues."""
        cursor = LoaderCursor(uri=str(_CSV), record_index=1)
        resumed = await _collect(
            _CorpusWalk([_CSV], registry=registry, opts=ReadOptions()), start=cursor
        )
        assert [d.record_index for d in resumed] == [1, 2]

    async def test_batching_splits_one_record_source_across_batches(self) -> None:
        """A batch size smaller than one source's row count still flushes per row."""
        walk = _CorpusWalk([_CSV], registry=registry, opts=ReadOptions(), batch_size=1)
        batches = [batch async for batch, _c, _s in walk.iter_batches()]
        non_empty = [batch for batch in batches if batch]
        assert len(non_empty) == 3
        assert all(len(batch) <= 1 for batch in batches)

    async def test_resume_cursor_from_partial_batch_does_not_duplicate(self) -> None:
        """A cursor taken mid-source resumes after the last emitted record."""
        walk = _CorpusWalk([_CSV], registry=registry, opts=ReadOptions(), batch_size=1)
        cursors = [cursor async for _b, cursor, _s in walk.iter_batches()]
        resumed = await _collect(
            _CorpusWalk([_CSV], registry=registry, opts=ReadOptions()),
            start=cursors[0],
        )
        assert [d.record_index for d in resumed] == [1, 2]

    async def test_final_cursor_preserves_last_record_index(self) -> None:
        """The final yield's cursor keeps the last source's record position."""
        walk = _CorpusWalk([_CSV], registry=registry, opts=ReadOptions())
        final_cursor = None
        async for _batch, cursor, _stats in walk.iter_batches():
            final_cursor = cursor
        assert final_cursor is not None
        assert final_cursor.record_index == 3


class _RaisingLoader(Loader):
    """A stub loader that always fails, to exercise non-format ingestion errors."""

    extensions = frozenset({".txt"})
    family = DocumentFamily.PROSE

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator[Document]:
        """Always raise a decode error before yielding anything."""
        raise DecodeError("stub decode failure")


class TestCorpusWalkErrorPolicy:
    """Non-format ingestion errors from a loader also honor the error policy."""

    async def test_raise_policy_propagates_decode_errors(self, tmp_path: Path) -> None:
        """The default RAISE policy propagates a loader's IngestionError."""
        bad = tmp_path / "bad.txt"
        bad.write_text("x")
        walk = _CorpusWalk(
            [bad], registry=registry, opts=ReadOptions(), loader=_RaisingLoader()
        )
        with pytest.raises(DecodeError):
            await _collect(walk)

    async def test_skip_policy_counts_a_loader_decode_error(
        self, tmp_path: Path
    ) -> None:
        """The SKIP policy counts a loader's IngestionError instead of raising."""
        bad = tmp_path / "bad.txt"
        bad.write_text("x")
        walk = _CorpusWalk(
            [bad],
            registry=registry,
            opts=ReadOptions(),
            error_policy=ErrorPolicy.SKIP,
            loader=_RaisingLoader(),
        )
        docs = []
        skipped = 0
        async for batch, _cursor, stats in walk.iter_batches():
            docs.extend(batch)
            skipped = stats.skipped
        assert docs == []
        assert skipped == 1


class _PartiallyRaisingLoader(Loader):
    """A stub record loader that yields two rows, then fails."""

    extensions = frozenset({".txt"})
    family = DocumentFamily.RECORD

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator[Document]:
        """Yield two rows, then raise a malformed-record error."""
        for index in range(2):
            yield Document(
                text=f"row {index}",
                title=str(index),
                uri=source.uri,
                source_format=SourceFormat.TXT,
                family=DocumentFamily.RECORD,
                content_hash=f"stub-{index}",
                loader_name="stub",
                char_count=5,
                record_index=index,
            )
        raise MalformedRecordError("stub malformed row")


class TestCorpusWalkPartialSourceFailure:
    """A source that fails partway through leaks neither documents nor counts."""

    async def test_skip_policy_discards_documents_from_a_failed_source(
        self, tmp_path: Path
    ) -> None:
        """Rows already yielded by a failing source never reach a batch."""
        bad = tmp_path / "bad.txt"
        bad.write_text("x")
        walk = _CorpusWalk(
            [bad],
            registry=registry,
            opts=ReadOptions(),
            error_policy=ErrorPolicy.SKIP,
            loader=_PartiallyRaisingLoader(),
        )
        docs = []
        final_stats = None
        async for batch, _cursor, stats in walk.iter_batches():
            docs.extend(batch)
            final_stats = stats
        assert docs == []
        assert final_stats is not None
        assert final_stats.skipped == 1
        assert final_stats.sources == 0


class TestInMemoryWalk:
    """The in-memory walk wraps one text string as a single document."""

    async def test_single_inline_document(self) -> None:
        """Single inline document."""
        walk = _InMemoryWalk("hello world", opts=ReadOptions())
        batches = [batch async for batch, _c, _s in walk.iter_batches()]
        assert len(batches) == 1
        assert batches[0][0].text == "hello world"
        assert batches[0][0].uri.startswith("inline://")
