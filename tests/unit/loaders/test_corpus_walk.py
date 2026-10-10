"""Tests for _CorpusWalk and _InMemoryWalk in agrag.loaders.walk.

Covers resume via LoaderCursor (mid-source and past a record index), and that
batching splits a single record source across multiple batches. Stub Loader subclasses
(_RaisingLoader, _PartiallyRaisingLoader, _OverflowsBatchThenFailsLoader)
simulate decode and malformed-record failures to verify that the RAISE and
SKIP error policies propagate or count errors without leaking partially
yielded documents or double-counting stats.
"""

from collections.abc import Iterator
from contextlib import aclosing
from pathlib import Path
from typing import BinaryIO

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.normalization import Normalization
from agrag.common.data_models.stage_failure import StageFailure
from agrag.loaders import registry
from agrag.loaders.base import Loader
from agrag.loaders.errors import DecodeError, MalformedRecordError
from agrag.loaders.types import ErrorPolicy, LoaderCursor, ReadOptions, SourceRef
from agrag.loaders.walk import _CorpusWalk, _InMemoryWalk


_FIXTURES = Path(__file__).parent / "fixtures"
_CSV = _FIXTURES / "sample.csv"


async def _collect(walk, start: LoaderCursor | None = None):
    docs = []
    async for batch, _cursor, _stats in walk.iter_batches(start=start):
        docs.extend(batch)
    return docs


class TestCorpusWalk:
    """The walk orders sources, then yields batches."""

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


class _OverflowsBatchThenFailsLoader(Loader):
    """A stub record loader that fills a batch, then fails in the next one."""

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
        """Yield three rows (enough to flush a batch_size=2 batch), then raise."""
        for index in range(3):
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

    async def test_document_count_matches_flushed_batches_when_a_source_fails_mid_batch(
        self, tmp_path: Path
    ) -> None:
        """A source that fails after a flush still reports only what was flushed."""
        bad = tmp_path / "bad.txt"
        bad.write_text("x")
        walk = _CorpusWalk(
            [bad],
            registry=registry,
            opts=ReadOptions(),
            error_policy=ErrorPolicy.SKIP,
            loader=_OverflowsBatchThenFailsLoader(),
            batch_size=2,
        )
        docs = []
        final_stats = None
        async for batch, _cursor, stats in walk.iter_batches():
            docs.extend(batch)
            final_stats = stats
        assert len(docs) == 2
        assert final_stats is not None
        assert final_stats.documents == len(docs)
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

    async def test_inline_text_records_the_unicode_form_only(self) -> None:
        """Inline text has no bytes to decode, so only the Unicode form applies."""
        walk = _InMemoryWalk("\ufb01\r\n", opts=ReadOptions())
        (document,) = [d async for batch, _c, _s in walk.iter_batches() for d in batch]

        assert document.text == "fi\r\n"
        assert document.normalization == Normalization(
            bom="keep", newline="keep", unicode_form="NFKC"
        )

    async def test_inline_text_honors_a_none_unicode_form(self) -> None:
        """The none form leaves the text as the caller gave it."""
        opts = ReadOptions(normalization=Normalization(unicode_form="none"))
        walk = _InMemoryWalk("\ufb01", opts=opts)
        (document,) = [d async for batch, _c, _s in walk.iter_batches() for d in batch]

        assert document.text == "\ufb01"


class _FiveDocumentLoader(Loader):
    """A stub record loader yielding five in-memory documents."""

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
        """Yield five record documents from ``start_at`` onward."""
        for index in range(start_at, 5):
            yield Document(
                text=f"row {index}",
                title=str(index),
                uri=source.uri,
                source_format=SourceFormat.TXT,
                family=DocumentFamily.RECORD,
                content_hash=f"five-{index}",
                loader_name="five",
                char_count=5,
                record_index=index,
            )


def _tracing_provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a provider wired to an in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


class TestCorpusWalkTracing:
    """Load spans close per document and never leak across a yield."""

    async def test_five_documents_produce_six_spans_with_attributes(
        self, tmp_path: Path
    ) -> None:
        """Five documents emit five spans plus one exhausted span."""
        path = tmp_path / "five.txt"
        path.write_text("x")
        provider, exporter = _tracing_provider()
        walk = _CorpusWalk(
            [path],
            registry=registry,
            opts=ReadOptions(),
            loader=_FiveDocumentLoader(),
            batch_size=2,
            tracer=provider.get_tracer("test"),
        )
        docs: list[Document] = []
        async for batch, _cursor, _stats in walk.iter_batches():
            docs.extend(batch)
        assert len(docs) == 5

        spans = [
            span
            for span in exporter.get_finished_spans()
            if span.name == "agrag.ingestion.load_document"
        ]
        assert len(spans) == 6
        document_spans = [
            span
            for span in spans
            if span.attributes
            and span.attributes.get("agrag.loader_exhausted") is not True
        ]
        exhausted = [
            span
            for span in spans
            if span.attributes and span.attributes.get("agrag.loader_exhausted") is True
        ]
        assert len(document_spans) == 5
        assert len(exhausted) == 1
        for span, document in zip(document_spans, docs, strict=True):
            assert span.attributes is not None
            assert span.attributes["agrag.source_uri"] == str(path.resolve())
            assert span.attributes["agrag.loader_name"] == "_FiveDocumentLoader"
            assert (
                span.attributes["agrag.document_key"] == document.resolved_document_key
            )
        assert [
            (span.attributes or {})["agrag.resume_cursor"] for span in document_spans
        ] == [
            1,
            2,
            3,
            4,
            5,
        ]

    async def test_resume_offsets_the_resume_cursor(self, tmp_path: Path) -> None:
        """Resuming at record 2 makes the first span carry cursor 3."""
        path = tmp_path / "five.txt"
        path.write_text("x")
        provider, exporter = _tracing_provider()
        start = LoaderCursor(uri=str(path.resolve()), record_index=2)
        walk = _CorpusWalk(
            [path],
            registry=registry,
            opts=ReadOptions(),
            loader=_FiveDocumentLoader(),
            batch_size=2,
            tracer=provider.get_tracer("test"),
        )
        docs: list[Document] = []
        async for batch, _cursor, _stats in walk.iter_batches(start=start):
            docs.extend(batch)
        assert len(docs) == 3
        spans = [
            span
            for span in exporter.get_finished_spans()
            if span.name == "agrag.ingestion.load_document"
        ]
        document_spans = [
            span
            for span in spans
            if not (span.attributes or {}).get("agrag.loader_exhausted")
        ]
        assert document_spans[0].attributes is not None
        assert document_spans[0].attributes["agrag.resume_cursor"] == 3

    async def test_no_span_is_current_after_a_batch_yield(self, tmp_path: Path) -> None:
        """The loader span never stays current across iter_batches' yield."""
        path = tmp_path / "five.txt"
        path.write_text("x")
        provider, _exporter = _tracing_provider()
        walk = _CorpusWalk(
            [path],
            registry=registry,
            opts=ReadOptions(),
            loader=_FiveDocumentLoader(),
            batch_size=2,
            tracer=provider.get_tracer("test"),
        )
        seen_batches = 0
        async for _batch, _cursor, _stats in walk.iter_batches():
            assert trace.get_current_span() is trace.INVALID_SPAN
            seen_batches += 1
        assert seen_batches > 1

    async def test_loader_error_records_on_span_without_exhausted(
        self, tmp_path: Path
    ) -> None:
        """A mid-source failure errors its span and emits no exhausted span."""
        path = tmp_path / "bad.txt"
        path.write_text("x")
        provider, exporter = _tracing_provider()
        walk = _CorpusWalk(
            [path],
            registry=registry,
            opts=ReadOptions(),
            error_policy=ErrorPolicy.SKIP,
            loader=_PartiallyRaisingLoader(),
            tracer=provider.get_tracer("test"),
        )
        docs: list[Document] = []
        final_stats = None
        async for batch, _cursor, stats in walk.iter_batches():
            docs.extend(batch)
            final_stats = stats
        assert docs == []
        assert final_stats is not None
        assert final_stats.skipped == 1
        spans = [
            span
            for span in exporter.get_finished_spans()
            if span.name == "agrag.ingestion.load_document"
        ]
        assert spans
        assert not any(
            (span.attributes or {}).get("agrag.loader_exhausted") is True
            for span in spans
        )
        assert any(span.status.status_code == StatusCode.ERROR for span in spans)

    async def test_early_close_leaves_no_error_span(self, tmp_path: Path) -> None:
        """Closing the walk early ends cleanly with no spurious error."""
        path = tmp_path / "five.txt"
        path.write_text("x")
        provider, exporter = _tracing_provider()
        walk = _CorpusWalk(
            [path],
            registry=registry,
            opts=ReadOptions(),
            loader=_FiveDocumentLoader(),
            batch_size=2,
            tracer=provider.get_tracer("test"),
        )
        async with aclosing(walk.iter_batches()) as batches:
            async for _batch, _cursor, _stats in batches:
                break
        assert not any(
            span.status.status_code == StatusCode.ERROR
            for span in exporter.get_finished_spans()
        )


class TestCorpusWalkQuarantineCorrelation:
    """Quarantined sources carry the failing load span's ids, when one exists."""

    async def test_mid_source_failure_carries_its_span_ids(
        self, tmp_path: Path
    ) -> None:
        """A source failing mid-iteration quarantines with its span's ids."""
        path = tmp_path / "bad.txt"
        path.write_text("x")
        provider, exporter = _tracing_provider()
        walk = _CorpusWalk(
            [path],
            registry=registry,
            opts=ReadOptions(),
            error_policy=ErrorPolicy.QUARANTINE,
            loader=_PartiallyRaisingLoader(),
            tracer=provider.get_tracer("test"),
        )
        final_stats = None
        async for _batch, _cursor, stats in walk.iter_batches():
            final_stats = stats
        assert final_stats is not None
        assert final_stats.quarantined == 1
        (failure,) = final_stats.quarantined_items
        assert isinstance(failure, StageFailure)
        assert failure.trace_id is not None
        assert failure.span_id is not None
        error_spans = [
            span
            for span in exporter.get_finished_spans()
            if span.status.status_code == StatusCode.ERROR
        ]
        assert len(error_spans) == 1
        assert failure.trace_id == format(error_spans[0].context.trace_id, "032x")
        assert failure.span_id == format(error_spans[0].context.span_id, "016x")

    async def test_registry_lookup_failure_carries_no_ids(self, tmp_path: Path) -> None:
        """A source with no loader quarantines with (None, None) ids."""
        path = tmp_path / "file.unknown"
        path.write_text("x")
        provider, exporter = _tracing_provider()
        walk = _CorpusWalk(
            [path],
            registry=registry,
            opts=ReadOptions(),
            error_policy=ErrorPolicy.QUARANTINE,
            tracer=provider.get_tracer("test"),
        )
        final_stats = None
        async for _batch, _cursor, stats in walk.iter_batches():
            final_stats = stats
        assert final_stats is not None
        assert final_stats.quarantined == 1
        (failure,) = final_stats.quarantined_items
        assert isinstance(failure, StageFailure)
        assert failure.trace_id is None
        assert failure.span_id is None
        assert list(exporter.get_finished_spans()) == []
