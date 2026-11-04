"""Corpus walk, batching, and resumable streaming.

This module is internal. ``Graph.add`` uses it to turn a set of sources into batches of
Documents. Only ``normalize_inline_text`` is for use outside the loaders package, by
``Graph.add``. Nothing else here is a supported interface.
"""

import asyncio
import contextvars
import hashlib
import os
import unicodedata
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Generator, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any, BinaryIO, TypeVar

from opentelemetry import context as otel_context
from opentelemetry.trace import Tracer

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.normalization import Normalization
from agrag.common.data_models.stage_failure import StageFailure
from agrag.loaders.base import Loader
from agrag.loaders.common import build_prose_document, text_sections
from agrag.loaders.errors import IngestionError, UnsupportedFormatError
from agrag.loaders.loader_registry import LoaderRegistry
from agrag.loaders.types import (
    ErrorPolicy,
    LoaderCursor,
    LoadStats,
    ReadOptions,
    SourceRef,
)
from agrag.observability import get_tracer, stage_failure_context


def _source_ref_for(path: Path) -> SourceRef:
    """Build a ``SourceRef`` for a local file.

    Args:
        path: The file to describe.

    Returns:
        The source reference with its extension and size.
    """
    stat = path.stat()
    return SourceRef(
        uri=str(path),
        extension=path.suffix.lower(),
        byte_size=stat.st_size,
        modified_at=None,
    )


_T = TypeVar("_T")


class _LoaderWorker:
    """Own the one thread that runs loader calls in a process.

    One thread for all walks keeps document conversions from overlapping. Before
    loaders ran off the event loop, conversions never overlapped either, so this
    keeps that guarantee. After a fork, the child creates its own thread, because a
    thread that exists only in the parent cannot run work in the child.
    """

    def __init__(self) -> None:
        """Start without a worker. The first call creates one."""
        self._executor: ThreadPoolExecutor | None = None
        self._process_id: int | None = None

    def executor(self) -> ThreadPoolExecutor:
        """Return the executor for the current process, creating it if needed.

        Returns:
            An executor with a single worker thread.
        """
        process_id = os.getpid()
        if self._executor is None or self._process_id != process_id:
            self._executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="agrag-loader"
            )
            self._process_id = process_id
        return self._executor


_LOADER_WORKER = _LoaderWorker()


def _call_in_trace_context(
    trace_context: otel_context.Context, call: Callable[..., Any], *args: object
) -> Any:
    """Call ``call`` with ``trace_context`` attached as the current context.

    The attach and the detach run in the same context object, so the detach can
    reset the token even when the call left context variables set.

    Args:
        trace_context: The OpenTelemetry context to attach for the call.
        call: The callable to run.
        *args: Positional arguments for ``call``.

    Returns:
        The value ``call`` returns.
    """
    token = otel_context.attach(trace_context)
    try:
        return call(*args)
    finally:
        otel_context.detach(token)


async def _run_loader_call(
    loader_context: contextvars.Context, call: Callable[..., _T], *args: object
) -> _T:
    """Run one loader call on the shared worker and return its result.

    Every call for one source runs in ``loader_context``, so context variables a
    loader sets before a yield are still set when it resumes. The caller's
    OpenTelemetry context is attached for the call, so spans the loader creates
    have the current span as their parent.

    If the caller is cancelled while the call is still queued, the call is
    cancelled and never runs. A call that is already running cannot be stopped, so
    the caller waits for it to finish. The source stream is closed only after the
    loader stops reading it.

    Args:
        loader_context: The context shared by every call for one source.
        call: The loader callable to run.
        *args: Positional arguments for ``call``.

    Returns:
        The value ``call`` returns.
    """
    trace_context = otel_context.get_current()
    future: Future[Any] = _LOADER_WORKER.executor().submit(
        loader_context.run, _call_in_trace_context, trace_context, call, *args
    )
    awaited = asyncio.wrap_future(future)
    try:
        return await asyncio.shield(awaited)
    except asyncio.CancelledError:
        if not future.cancel():
            await asyncio.wait([awaited])
            if not awaited.cancelled():
                awaited.exception()
        raise


class _CorpusWalk:
    """Walk local files in deterministic order and yield batched documents.

    This class expands directories and globs up front, sorts the resulting paths, and
    then
    streams them through the registry. A ``LoaderCursor`` tags each batch so a caller
    can
    resume a walk after a crash without gaps or duplicates.
    """

    def __init__(
        self,
        sources: list[Path],
        *,
        registry: LoaderRegistry,
        opts: ReadOptions,
        error_policy: ErrorPolicy = ErrorPolicy.RAISE,
        loader: Loader | None = None,
        batch_size: int = 100,
        tracer: Tracer | None = None,
    ) -> None:
        self._paths = sorted({p.resolve() for p in sources}, key=str)
        self._registry = registry
        self._opts = opts
        self._error_policy = error_policy
        self._loader = loader
        self._batch_size = batch_size
        self._tracer = tracer

    async def iter_batches(  # noqa: PLR0912,PLR0915
        self, *, start: LoaderCursor | None = None
    ) -> AsyncIterator[tuple[list[Document], LoaderCursor, LoadStats]]:
        """Yield (documents, cursor, stats) batches in deterministic order.

        Args:
            start: A cursor to resume from. The walk skips every source before it and
            resumes
                inside the matching source at ``start.record_index``.

        Yields:
            One tuple per batch: the batch documents, the cursor after the batch, and
            the
            running stats.

        Raises:
            UnsupportedFormatError: A source has no loader and the error policy is
            RAISE.
            IngestionError: A source fails to load and the error policy is RAISE.
        """
        stats = LoadStats()
        batch: list[Document] = []
        cursor = start if start is not None else LoaderCursor()
        started = start is None

        for path in self._paths:
            uri = str(path)
            if not started:
                if start is not None and start.uri is not None and uri < start.uri:
                    continue
                started = True

            source = _source_ref_for(path)
            if self._loader is None:
                try:
                    loader = self._registry.for_source(source)
                except UnsupportedFormatError as exc:
                    self._handle_error(uri, exc, stats)
                    continue
            else:
                loader = self._loader

            resume_index = self._resume_index(uri, loader, start)
            if resume_index is None:
                continue

            # SKIP and QUARANTINE apply to a whole source. Keep its documents
            # until the loader finishes so a late failure cannot leak rows.
            source_batch: list[Document] = []
            source_bytes = path.stat().st_size
            resume_position = resume_index
            source_cursor = cursor
            failed_trace_id: str | None = None
            failed_span_id: str | None = None
            try:
                loader_context = contextvars.copy_context()
                async with self._open_loader_iter(
                    path, loader, source, resume_index, loader_context
                ) as loader_iter:
                    tracer = get_tracer(self._tracer)
                    while True:
                        with tracer.start_as_current_span(
                            "agrag.ingestion.load_document",
                            attributes={
                                "agrag.source_uri": uri,
                                "agrag.loader_name": type(loader).__name__,
                                "agrag.normalization": (
                                    self._opts.normalization.model_dump_json()
                                ),
                            },
                        ) as span:
                            # None, not a sentinel object(), so `doc` stays
                            # typed as Document | None and `if doc is None:`
                            # narrows cleanly -- Iterator[Document] never
                            # yields None itself.
                            try:
                                doc = await _run_loader_call(
                                    loader_context, next, loader_iter, None
                                )
                            except IngestionError:
                                failed_trace_id, failed_span_id = (
                                    stage_failure_context()
                                )
                                raise
                            record_index = None
                            if doc is None:
                                span.set_attribute("agrag.loader_exhausted", True)
                            else:
                                attributes: dict[str, str | int] = {
                                    "agrag.document_key": doc.resolved_document_key
                                }
                                if loader.family == DocumentFamily.RECORD:
                                    resume_position += 1
                                    record_index = resume_position
                                    # This is the LoaderCursor resume value
                                    # (1-based count of records consumed so far
                                    # for this source), not the document's own
                                    # 0-based position -- named for what it
                                    # actually is to avoid implying a 0-based
                                    # index.
                                    attributes["agrag.resume_cursor"] = record_index
                                span.set_attributes(attributes)
                        if doc is None:
                            break
                        source_batch.append(doc)
                        source_cursor = LoaderCursor(uri=uri, record_index=record_index)
                        if (
                            self._error_policy == ErrorPolicy.RAISE
                            and len(batch) + len(source_batch) >= self._batch_size
                        ):
                            # Only count documents once they are actually
                            # flushed into a batch. A document counted here but
                            # never flushed (the source later raises, and this
                            # source_batch's *next* run is discarded below)
                            # would make stats.documents overstate what the
                            # caller ever received.
                            stats.documents += len(source_batch)
                            batch.extend(source_batch)
                            source_batch = []
                            cursor = source_cursor
                            yield batch, cursor, stats
                            batch = []
            except IngestionError as exc:
                self._handle_error(
                    uri, exc, stats, trace_id=failed_trace_id, span_id=failed_span_id
                )
                continue

            stats.sources += 1
            stats.bytes_read += source_bytes
            for index, doc in enumerate(
                source_batch, start=resume_position - len(source_batch) + 1
            ):
                stats.documents += 1
                batch.append(doc)
                cursor = LoaderCursor(
                    uri=uri,
                    record_index=index
                    if loader.family == DocumentFamily.RECORD
                    else None,
                )
                if len(batch) >= self._batch_size:
                    yield batch, cursor, stats
                    batch = []

        yield batch, cursor, stats

    @asynccontextmanager
    async def _open_loader_iter(
        self,
        path: Path,
        loader: Loader,
        source: SourceRef,
        start_at: int,
        loader_context: contextvars.Context,
    ) -> AsyncGenerator[Iterator[Document], None]:
        """Open a source and yield an iterator over its documents.

        The loader is created and advanced on the shared worker. On exit, a loader
        generator that is still open is closed in the same context, before the
        source file is closed.

        Args:
            path: The file to open.
            loader: The loader that reads the file.
            source: The source reference passed to the loader.
            start_at: The record index to resume from.
            loader_context: The context shared by every loader call for this source.

        Yields:
            The iterator of documents the loader produces.
        """
        with self._open(path) as stream:
            loader_iter = iter(
                await _run_loader_call(
                    loader_context,
                    partial(loader.load, start_at=start_at),
                    source,
                    stream,
                    self._opts,
                )
            )
            try:
                yield loader_iter
            finally:
                if isinstance(loader_iter, Generator):
                    await _run_loader_call(loader_context, loader_iter.close)

    @staticmethod
    def _open(path: Path) -> BinaryIO:
        """Open a path for binary reading.

        Args:
            path: The file to open.

        Returns:
            The open binary stream.
        """
        return path.open("rb")

    def _handle_error(
        self,
        uri: str,
        exc: IngestionError,
        stats: LoadStats,
        *,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> None:
        """Apply the error policy to one source failure.

        Args:
            uri: The failing source.
            exc: The loader lookup or load error.
            stats: The running stats to update in place.
            trace_id: The failing span's trace id, when the caller already
                captured one from the ``load_document`` span before it closed.
                ``None`` when no such span was open for this source -- an
                ``UnsupportedFormatError`` from the registry lookup, before
                ``self._open(path)`` runs. This method never reads the current
                span itself; the caller always decides what to pass.
            span_id: The failing span's id, paired with ``trace_id``.

        Raises:
            IngestionError: The error policy is RAISE.
        """
        if self._error_policy == ErrorPolicy.RAISE:
            raise exc
        reason = str(exc)
        if self._error_policy == ErrorPolicy.QUARANTINE:
            stats.quarantined += 1
            stats.quarantined_items.append(
                StageFailure(
                    item_id=uri,
                    error_type="Quarantined",
                    error_message=reason,
                    trace_id=trace_id,
                    span_id=span_id,
                )
            )
        else:
            stats.skipped += 1

    def _resume_index(
        self, uri: str, loader: Loader, start: LoaderCursor | None
    ) -> int | None:
        """Return the resume point for one source, or ``None`` to skip it.

        Args:
            uri: The source being walked.
            loader: The loader that will read the source.
            start: The cursor to resume from, when the caller passed one.

        Returns:
            The record index to resume at, or ``None`` when the source is atomic and was
            already processed at the cursor.
        """
        if start is None or uri != start.uri:
            return 0
        if loader.family == DocumentFamily.PROSE:
            return None
        return start.record_index or 0


def normalize_inline_text(text: str, opts: ReadOptions) -> tuple[str, Normalization]:
    """Normalize text that a caller passed in memory.

    Inline text has no bytes to decode, so only the Unicode form applies.

    Args:
        text: The text as the caller gave it.
        opts: The read options. Only ``opts.normalization.unicode_form`` is used.

    Returns:
        The normalized text and the normalization to record on its document.
    """
    form = opts.normalization.unicode_form
    normalized = text if form == "none" else unicodedata.normalize(form, text)
    return normalized, Normalization(bom="keep", newline="keep", unicode_form=form)


class _InMemoryWalk:
    """Walk a single in-memory text string as one source.

    This class backs ``Graph.add(text=...)``. It produces one prose Document whose uri
    is derived from the text hash.
    """

    def __init__(self, text: str, *, opts: ReadOptions) -> None:
        self._text, self._normalization = normalize_inline_text(text, opts)
        self._opts = opts

    async def iter_batches(
        self, *, start: LoaderCursor | None = None
    ) -> AsyncIterator[tuple[list[Document], LoaderCursor, LoadStats]]:
        """Yield the single in-memory document as one batch.

        Args:
            start: Ignored; an in-memory source never resumes.

        Yields:
            One tuple with the single Document, its cursor, and stats.
        """
        content_hash = hashlib.sha256(self._text.encode("utf-8")).hexdigest()
        source = SourceRef(
            uri=f"inline://{content_hash[:16]}",
            extension=".txt",
            byte_size=len(self._text.encode("utf-8")),
        )
        document = build_prose_document(
            source=source,
            text=self._text,
            encoding="utf-8",
            source_format=SourceFormat.TXT,
            loader_name="inline",
            opts=replace(self._opts, normalization=self._normalization),
            title="inline",
            sections=text_sections(self._text) if self._opts.store_text else [],
        )
        stats = LoadStats(
            documents=1, sources=1, bytes_read=len(self._text.encode("utf-8"))
        )
        yield [document], LoaderCursor(uri=document.uri), stats
