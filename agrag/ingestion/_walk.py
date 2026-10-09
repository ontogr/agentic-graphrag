"""Read documents from a source and chunk them for ingestion."""

import glob
import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Union

from opentelemetry.trace import Tracer

from agrag.chunking import Chunker
from agrag.chunking.chunker import ChunkedDocument
from agrag.common.data_models.document import Document
from agrag.loaders.corpus.base import Loader
from agrag.loaders.corpus.registry import LoaderRegistry
from agrag.loaders.corpus.types import ErrorPolicy, LoadStats, ReadOptions
from agrag.loaders.corpus.walk import _CorpusWalk, _InMemoryWalk


SourceType = Union[str, Path]
SourcesType = Union[SourceType, Sequence[SourceType]]


def resolve_paths(source: SourcesType) -> tuple[list[Path], bool]:
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


async def iter_document_batches(
    *,
    source: SourcesType | None = None,
    text: str | None = None,
    documents: Sequence[Document] | None = None,
    registry: LoaderRegistry,
    opts: ReadOptions,
    error_policy: ErrorPolicy,
    loader: Loader | None = None,
    tracer: Tracer,
) -> AsyncIterator[tuple[list[Document], LoadStats]]:
    """Yield batches of documents from exactly one input, with running stats.

    Args:
        source: A file path, a directory, a glob, or a list of these.
        text: Raw text to read as one document.
        documents: Already-built documents, yielded as one batch.
        registry: The loaders to pick from for each file.
        opts: How loaders read sources.
        error_policy: The action to take on a per-source error.
        loader: A loader to use instead of the registry default. Requires a
            single-file ``source``.
        tracer: A tracer to record spans for the walk.

    Yields:
        One tuple per batch: its documents and the stats of the walk so far.
        Built documents count as documents and no sources.

    Raises:
        ValueError: ``loader`` is set and ``source`` is not a single file.
    """
    if documents is not None:
        built = list(documents)
        yield built, LoadStats(documents=len(built), sources=0)
        return
    if text is not None:
        walk: _CorpusWalk | _InMemoryWalk = _InMemoryWalk(text, opts=opts)
    else:
        if source is None:
            raise ValueError("Provide one of 'source', 'text', or 'documents'.")
        paths, single_file = resolve_paths(source)
        if loader is not None and not single_file:
            raise ValueError(
                "A loader override requires a single-file source, not a "
                "directory, glob, or list of sources."
            )
        walk = _CorpusWalk(
            paths,
            registry=registry,
            opts=opts,
            error_policy=error_policy,
            loader=loader,
            tracer=tracer,
        )
    async for batch, _cursor, stats in walk.iter_batches():
        yield batch, stats


def chunk_documents(
    documents: list[Document], *, chunker: Chunker, tracer: Tracer
) -> list[ChunkedDocument]:
    """Chunk a batch of documents.

    Args:
        documents: The documents to chunk.
        chunker: The chunker to use for every document.
        tracer: A tracer to record one span for each document.

    Returns:
        One chunked document per input document, in the same order, each with
        its chunks and their placements.
    """
    chunked: list[ChunkedDocument] = []
    for document in documents:
        with tracer.start_as_current_span(
            "agrag.ingestion.chunk_document",
            attributes={
                "agrag.document_key": document.resolved_document_key,
                "agrag.chunker.hash": chunker.fingerprint,
                "agrag.chunker.settings": json.dumps(chunker.settings()),
            },
        ) as span:
            document_chunks = chunker.chunk(document)
            span.set_attribute("agrag.chunks_produced", len(document_chunks.chunks))
        chunked.append(document_chunks)
    return chunked
