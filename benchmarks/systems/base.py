"""The contract between the runner and a system under test."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from benchmarks.models import BenchmarkQuestion


class AgentFailureError(Exception):
    """The system gave no usable answer, for example at its step limit.

    The runner scores such a question 0 and flags it. An error from the
    infrastructure is any other exception, and it aborts the run.
    """


@dataclass(frozen=True)
class CitedChunk:
    """A chunk the answer cites.

    Attributes:
        uri: The uri of the chunk's document.
        char_start: The chunk's start offset in the document text, or None when the
            source has no character offsets, as for a PDF.
        char_end: The chunk's end offset, or None.
    """

    uri: str
    char_start: int | None
    char_end: int | None


@dataclass
class SystemAnswer:
    """What a system answered.

    Attributes:
        text: The answer text.
        cited_chunks: The chunks the answer cites.
        non_chunk_citations: The number of citations that are not chunks.
        source_chunks: The chunks that cited entities and relations were extracted
            from.
        raw: The system's own result, for graders that need more than the text.
    """

    text: str
    cited_chunks: list[CitedChunk] = field(default_factory=list)
    non_chunk_citations: int = 0
    source_chunks: list[CitedChunk] = field(default_factory=list)
    raw: Any = None


class SystemAdapter(Protocol):
    """A system that ingests a corpus and answers questions about it."""

    name: str

    async def ingest(self) -> None:
        """Ingest the corpus documents into the system's own store."""
        ...

    async def answer(self, question: BenchmarkQuestion) -> SystemAnswer:
        """Answer one question from the ingested corpus.

        Raises:
            AgentFailureError: The system gave no usable answer.
        """
        ...

    async def teardown(self) -> None:
        """Release the system's connections."""
        ...
