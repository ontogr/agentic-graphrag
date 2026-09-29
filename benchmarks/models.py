"""Input models: questions, corpora and the manifest that lists them."""

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


Mode = Literal["lite", "full"]


def canonical_sha256(value: Any) -> str:
    """Return the SHA-256 of a value's canonical JSON (sorted keys, no spaces)."""
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BenchmarkQuestion(BaseModel):
    """One question and the reference data its grader needs.

    Attributes:
        id: A question id that is unique within its manifest.
        corpus_id: The corpus this question is answered against.
        messages: The whole conversation. The last item is the user turn.
        group: The name that scores group by, such as a question type or a source.
        reference: The reference fields the domain grader reads.
    """

    id: str
    corpus_id: str
    messages: list[dict[str, str]] = Field(min_length=1)
    group: str
    reference: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _last_turn_is_user(self) -> "BenchmarkQuestion":
        """Require the last message to be a user turn."""
        if self.messages[-1].get("role") != "user":
            raise ValueError("the last message must have the role 'user'")
        return self

    @property
    def query(self) -> str:
        """The last user turn."""
        return self.messages[-1]["content"]


class CorpusDocument(BaseModel):
    """A source document, identified by hash instead of text.

    Attributes:
        id: The document id within the corpus.
        uri: The document uri that agrag stores on the document node.
        sha256: The hash of the fetched bytes, checked on every fetch.
        source: Where the fetch step gets the bytes, such as a pinned URL or a
            Hugging Face path and revision.
    """

    id: str
    uri: str
    sha256: str
    source: str


class Corpus(BaseModel):
    """A set of documents that must share one graph and no other graph.

    Attributes:
        id: The corpus id.
        service: The compose service that holds this corpus's graph.
        schema_name: The name of the graph schema the corpus uses.
        documents: The corpus documents.
        n_tokens: The corpus size in tokens, when the fixture states it.
    """

    id: str
    service: str
    schema_name: str
    documents: list[CorpusDocument]
    n_tokens: int | None = None


class CorpusManifest(BaseModel):
    """The corpora and questions of one dataset in one mode.

    Attributes:
        name: The dataset name.
        domain: The domain the dataset belongs to.
        mode: ``lite`` or ``full``.
        upstream: The pinned upstream revisions and file hashes.
        corpora: The corpora, ingested one at a time.
        questions: The questions, each tied to one corpus.
    """

    name: str
    domain: str
    mode: Mode
    upstream: dict[str, Any] = Field(default_factory=dict)
    corpora: list[Corpus]
    questions: list[BenchmarkQuestion]

    @model_validator(mode="after")
    def _questions_name_a_corpus(self) -> "CorpusManifest":
        """Require unique question ids and a known corpus for every question."""
        corpus_ids = {corpus.id for corpus in self.corpora}
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("question ids must be unique")
        unknown = {q.corpus_id for q in self.questions} - corpus_ids
        if unknown:
            raise ValueError(f"questions name unknown corpora: {sorted(unknown)}")
        return self

    def manifest_sha256(self) -> str:
        """Return the hash of the whole manifest."""
        return canonical_sha256(self.model_dump(mode="json"))

    def question_ids_sha256(self) -> str:
        """Return the hash of the question ids, in order."""
        return canonical_sha256([question.id for question in self.questions])
