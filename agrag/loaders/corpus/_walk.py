"""Corpus walk, batching, and resumable streaming.

This module is internal. ``Graph.add`` uses it to turn a set of sources into batches of
Documents. It never exports a public concept; ADR 0001 forbids a second public loader
idea.
"""

import hashlib
import unicodedata
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO

from opentelemetry.trace import Tracer

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.loaders.corpus.base import Loader
from agrag.loaders.corpus.errors import IngestionError, UnsupportedFormatError
from agrag.loaders.corpus.registry import LoaderRegistry
from agrag.loaders.corpus.types import (
    ErrorPolicy,
    LoaderCursor,
    LoadStats,
    ReadOptions,
    SourceRef,
)
from agrag.observability import traced


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

    async def iter_batches(
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

            # A source is staged in its own buffer and only merged into the
            # yielded batch once its loader finishes without raising, so a
            # source that fails partway through never leaks the documents it
            # already produced into the batch stream.
            source_batch: list[Document] = []
            source_bytes = path.stat().st_size
            resume_position = resume_index
            source_cursor = cursor
            try:
                with self._open(path) as stream:
                    for doc in traced(self._tracer)(loader.load)(
                        source, stream, self._opts, start_at=resume_index
                    ):
                        stats.documents += 1
                        source_batch.append(doc)
                        record_index = None
                        if loader.family == DocumentFamily.RECORD:
                            resume_position += 1
                            record_index = resume_position
                        source_cursor = LoaderCursor(uri=uri, record_index=record_index)
                        if len(batch) + len(source_batch) >= self._batch_size:
                            batch.extend(source_batch)
                            source_batch = []
                            cursor = source_cursor
                            yield batch, cursor, stats
                            batch = []
            except IngestionError as exc:
                self._handle_error(uri, exc, stats)
                continue

            stats.sources += 1
            stats.bytes_read += source_bytes
            batch.extend(source_batch)
            cursor = source_cursor

        yield batch, cursor, stats

    @staticmethod
    def _open(path: Path) -> BinaryIO:
        """Open a path for binary reading.

        Args:
            path: The file to open.

        Returns:
            The open binary stream.
        """
        return path.open("rb")

    def _handle_error(self, uri: str, exc: IngestionError, stats: LoadStats) -> None:
        """Apply the error policy to one source failure.

        Args:
            uri: The failing source.
            exc: The loader lookup or load error.
            stats: The running stats to update in place.

        Raises:
            IngestionError: The error policy is RAISE.
        """
        if self._error_policy == ErrorPolicy.RAISE:
            raise exc
        reason = str(exc)
        if self._error_policy == ErrorPolicy.QUARANTINE:
            stats.quarantined += 1
            stats.quarantined_items.append((uri, reason))
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


class _InMemoryWalk:
    """Walk a single in-memory text string as one source.

    This class backs ``Graph.add(text=...)``. It produces one prose Document whose uri
    is
    derived from the text hash.
    """

    def __init__(self, text: str, *, opts: ReadOptions) -> None:
        self._text = unicodedata.normalize("NFKC", text)
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
        document = Document(
            text=self._text if self._opts.store_text else "",
            title="inline",
            uri=f"inline://{content_hash[:16]}",
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash=content_hash,
            loader_name="inline",
            encoding="utf-8",
            char_count=len(self._text),
            line_count=self._text.count("\n") + 1,
        )
        stats = LoadStats(
            documents=1, sources=1, bytes_read=len(self._text.encode("utf-8"))
        )
        yield [document], LoaderCursor(uri=document.uri), stats
