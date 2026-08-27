"""Tests for the corpus walk, batching, and resume."""

from pathlib import Path

from agrag.loaders.corpus import registry
from agrag.loaders.corpus._walk import _CorpusWalk, _InMemoryWalk
from agrag.loaders.corpus.types import LoaderCursor, ReadOptions


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


class TestInMemoryWalk:
    """The in-memory walk wraps one text string as a single document."""

    async def test_single_inline_document(self) -> None:
        """Single inline document."""
        walk = _InMemoryWalk("hello world", opts=ReadOptions())
        batches = [batch async for batch, _c, _s in walk.iter_batches()]
        assert len(batches) == 1
        assert batches[0][0].text == "hello world"
        assert batches[0][0].uri.startswith("inline://")
