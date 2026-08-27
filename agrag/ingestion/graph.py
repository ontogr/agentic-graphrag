"""The public Graph API for ingestion."""

import asyncio
import glob
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Union

from opentelemetry.trace import Tracer

import agrag.loaders.docling  # noqa: F401  (registers the docling loaders)
from agrag.chunking import default_chunker
from agrag.chunking.text import Chunk, chunk_document
from agrag.common.data_models.document import Document
from agrag.loaders.corpus import registry as _corpus_registry
from agrag.loaders.corpus._walk import _CorpusWalk, _InMemoryWalk
from agrag.loaders.corpus.base import Loader
from agrag.loaders.corpus.types import (
    ErrorPolicy,
    IngestResult,
    LoadStats,
    ReadOptions,
)
from agrag.loaders.docling.chunking import chunk_docling_document
from agrag.observability import get_tracer, traced


SourceType = Union[str, Path]
SourcesType = Union[SourceType, Sequence[SourceType]]


def _resolve_paths(source: SourcesType) -> tuple[list[Path], bool]:
    """Expand a source argument into concrete file paths.

    Args:
        source: A file path, a directory, a glob, or a list of these.

    Returns:
        The resolved file paths in sorted order and whether the input was a single plain
        file (not a directory or glob).
    """
    items = source if isinstance(source, (list, tuple)) else [source]
    paths: list[Path] = []
    single_file = len(items) == 1
    for item in items:
        text = str(item)
        path = Path(text)
        if path.is_dir():
            single_file = False
            paths.extend(sorted(p for p in path.rglob("*") if p.is_file()))
        elif any(ch in text for ch in "*?["):
            single_file = False
            paths.extend(
                sorted(
                    Path(m)
                    for m in glob.glob(text, recursive=True)
                    if Path(m).is_file()
                )
            )
        else:
            paths.append(path)
    return paths, single_file


class Graph:
    """A knowledge graph that a caller can open and add content to."""

    def __init__(self, *, tracer: Tracer | None = None) -> None:
        """Create a graph with an optional tracer.

        Args:
            tracer: A tracer to record spans for every ingest step. Pass ``None`` to run
                with no tracing.
        """
        self._tracer = get_tracer(tracer)
        self._registry = _corpus_registry
        self._chunker = default_chunker()

    @classmethod
    async def open(cls, *, tracer: Tracer | None = None) -> "Graph":
        """Open a graph with no setup.

        Args:
            tracer: A tracer to record spans for every ingest step. Pass ``None`` to
                run with no tracing.

        Returns:
            A ready-to-use graph. This call needs no external service.
        """
        return cls(tracer=tracer)

    async def add(
        self,
        source: SourcesType | None = None,
        *,
        text: str | None = None,
        documents: Sequence[Document] | None = None,
        loader: Loader | None = None,
        error_policy: ErrorPolicy = ErrorPolicy.RAISE,
        on_progress: Callable[[LoadStats], None] | None = None,
    ) -> IngestResult:
        """Add content to the graph.

        Give exactly one of ``source``, ``text``, and ``documents``.

        Args:
            source: A file path, a directory, a glob, or a list of these.
            text: Raw text to add as one document.
            documents: Already-built documents to add directly.
            loader: A loader to use instead of the registry default. Requires a
                single-file ``source``; a directory, glob, or list of sources raises an
                error.
            error_policy: The action to take on a per-source error.
            on_progress: A callback the call runs after each batch.

        Returns:
            A summary of what the call added, skipped, and quarantined, plus the
            chunks it produced.

        Raises:
            ValueError: The call got zero, or more than one, of ``source``, ``text``,
                and ``documents``. Also raised when ``loader`` is set without
                ``source``, or with a source that can match more than one file.
            UnsupportedFormatError: No loader is registered for a source's format.
            MissingExtraError: A loader is registered for a source's format, but its
                package extra is not installed. This error follows ``error_policy``
                instead of always stopping the call.
        """
        given = sum(x is not None for x in (source, text, documents))
        if given != 1:
            raise ValueError(
                f"Provide exactly one of 'source', 'text', or 'documents'; got {given}."
            )
        if loader is not None and source is None:
            raise ValueError(
                "A loader override requires 'source'; it has no effect on 'text' or "
                "'documents'."
            )

        chunks: list[Chunk] = []

        if text is not None:
            walk = _InMemoryWalk(text, opts=ReadOptions())
            batches = walk.iter_batches()
        elif documents is not None:
            stats = LoadStats(documents=len(documents), sources=0)
            chunks.extend(
                await asyncio.to_thread(self._chunk_documents, list(documents))
            )
            if on_progress is not None:
                on_progress(stats)
            return IngestResult(
                documents=stats.documents,
                sources=stats.sources,
                skipped=stats.skipped,
                quarantined=stats.quarantined,
                quarantined_items=list(stats.quarantined_items),
                chunks=chunks,
            )
        else:
            assert source is not None
            paths, single_file = _resolve_paths(source)
            if loader is not None and not single_file:
                raise ValueError(
                    "A loader override requires a single-file source, not a directory, "
                    "glob, or list of sources."
                )
            walk = _CorpusWalk(
                paths,
                registry=self._registry,
                opts=ReadOptions(),
                error_policy=error_policy,
                loader=loader,
                tracer=self._tracer,
            )
            batches = walk.iter_batches()

        final_stats = LoadStats()
        async for batch, _cursor, stats in batches:
            chunks.extend(await asyncio.to_thread(self._chunk_documents, batch))
            final_stats.documents = stats.documents
            final_stats.sources = stats.sources
            final_stats.skipped = stats.skipped
            final_stats.quarantined = stats.quarantined
            final_stats.quarantined_items = list(stats.quarantined_items)
            if on_progress is not None:
                on_progress(stats)

        return IngestResult(
            documents=final_stats.documents,
            sources=final_stats.sources,
            skipped=final_stats.skipped,
            quarantined=final_stats.quarantined,
            quarantined_items=list(final_stats.quarantined_items),
            chunks=chunks,
        )

    def _chunk_documents(self, documents: list[Document]) -> list[Chunk]:
        """Chunk a batch of documents with the right chunker each.

        Args:
            documents: The documents to chunk.

        Returns:
            The chunks, in document then chunk order.
        """
        chunks: list[Chunk] = []
        for document in documents:
            if document.loader_name == "docling":
                docling_doc = document.metadata.get("_docling_document")
                if docling_doc is not None:
                    chunks.extend(
                        traced(self._tracer)(chunk_docling_document)(
                            docling_doc, document.resolved_id
                        )
                    )
                    continue
            chunks.extend(traced(self._tracer)(chunk_document)(document, self._chunker))
        return chunks
