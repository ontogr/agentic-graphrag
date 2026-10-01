"""The contract every dataset implements."""

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.graph_schema import GraphSchema
from benchmarks.grading.base import Grader
from benchmarks.models import Corpus, CorpusManifest, Mode


def text_document(text: str, *, uri: str, title: str | None = None) -> Document:
    """Build a prose document around text that is kept exactly as given.

    Adapters use this instead of a loader when chunk offsets must index the
    original text. A loader normalizes the text, which shifts the offsets.
    """
    return Document(
        text=text,
        title=title or uri,
        uri=uri,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        loader_name="benchmarks",
        char_count=len(text),
        line_count=text.count("\n") + 1,
    )


class DatasetAdapter(ABC):
    """Loads one dataset's fixture and builds the documents to ingest."""

    @abstractmethod
    def load(self, mode: Mode) -> CorpusManifest:
        """Return the frozen manifest of one mode. Reads no source text."""

    @abstractmethod
    def documents(self, corpus: Corpus) -> Sequence[Document]:
        """Fetch the corpus text at its pinned revision and build its documents.

        Raises:
            HashMismatchError: A fetched file differs from the fixture hash.
        """

    @abstractmethod
    def schema(self, corpus: Corpus) -> GraphSchema:
        """Return the graph schema of the corpus."""


@dataclass(frozen=True)
class Domain:
    """A dataset adapter and the grader for its questions.

    Attributes:
        adapter: The dataset adapter.
        grader: The grader of every mode, unless ``full_grader`` is set.
        full_grader: The grader of full mode, when it differs from ``grader``.
    """

    adapter: DatasetAdapter
    grader: Grader
    full_grader: Grader | None = None

    def grader_for(self, mode: Mode) -> Grader:
        """Return the grader of one mode.

        Args:
            mode: ``lite`` or ``full``.

        Returns:
            ``full_grader`` for full mode when it is set, otherwise ``grader``.
        """
        if mode == "full" and self.full_grader is not None:
            return self.full_grader
        return self.grader


# Each domain adds its entry here when it is written.
DOMAINS: dict[str, Domain] = {}
