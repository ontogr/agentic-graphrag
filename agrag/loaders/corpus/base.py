"""The Loader interface: reads one source and yields Document objects."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import BinaryIO, ClassVar

from agrag.common.data_models.document import Document, DocumentFamily
from agrag.loaders.corpus.types import ReadOptions, SourceRef


class Loader(ABC):
    """Reads one source and yields Document objects.

    A Loader keeps no state between calls, so a worker process can reuse one instance
    across many sources.

    Attributes:
        extensions: The file extensions this loader claims, each with a leading dot.
        mime_types: The MIME types this loader claims. Empty when the loader relies on
        the
            extension alone.
        family: The document family this loader produces.
        extra: The optional package extra required to use this loader. ``None`` for core
            loaders. The registry raises ``MissingExtraError`` when this extra is not
            installed.
    """

    extensions: ClassVar[frozenset[str]]
    mime_types: ClassVar[frozenset[str]] = frozenset()
    family: ClassVar[DocumentFamily]
    extra: ClassVar[str | None] = None

    @abstractmethod
    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator[Document]:
        """Yield documents read from one source.

        Args:
            source: The source to read.
            stream: The open binary stream for the source, positioned at the start.
            opts: The read options for this call.
            start_at: The record index to resume from. Prose loaders ignore this
            argument.

        Yields:
            One Document per unit the source contains, in a fixed order.
        """


class ProseLoader(Loader):
    """A loader that makes one Document per source.

    Concrete readers reject a source larger than the configured byte limit when the
    source's byte size is known upfront (``SourceRef.byte_size`` is not ``None``).
    """

    family = DocumentFamily.PROSE


class RecordLoader(Loader):
    """A loader that makes one Document per record in a source.

    Concrete readers read and decode the whole source into memory up front, up
    to ``opts.max_document_bytes``; that byte limit is what bounds memory use,
    not incremental reads from disk. Whether records are parsed incrementally
    from there is format-dependent: the CSV and JSONL readers parse and yield
    one record at a time, so a malformed record later in the source surfaces
    only after earlier records have already been yielded. The JSON reader
    parses the whole source up front, so a malformed source fails before any
    record is yielded.
    """

    family = DocumentFamily.RECORD
