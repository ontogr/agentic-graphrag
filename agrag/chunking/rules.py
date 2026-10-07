"""Chunking rules: which chunker a document gets, as data."""

from fnmatch import fnmatchcase

from pydantic import BaseModel, ConfigDict, SerializeAsAny

from agrag.chunking.base import Chunker, fingerprint_of
from agrag.chunking.docling import DoclingChunker
from agrag.chunking.recursive import RecursiveChunker
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat


class RuleMatch(BaseModel):
    """The documents a rule applies to.

    Every key is optional and a key left as ``None`` matches any value. Keys combine
    with AND. A value in a list key matches if it equals any item of the list.

    Attributes:
        loader_names: Match ``Document.loader_name``.
        source_formats: Match ``Document.source_format``.
        families: Match ``Document.family``.
        uri_glob: Match ``Document.uri`` against this ``fnmatch`` pattern. Case
            sensitive.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    loader_names: tuple[str, ...] | None = None
    source_formats: tuple[SourceFormat, ...] | None = None
    families: tuple[DocumentFamily, ...] | None = None
    uri_glob: str | None = None

    def matches(self, document: Document) -> bool:
        """Return whether every set key matches the document."""
        if self.loader_names is not None and (
            document.loader_name not in self.loader_names
        ):
            return False
        if self.source_formats is not None and (
            document.source_format not in self.source_formats
        ):
            return False
        if self.families is not None and document.family not in self.families:
            return False
        return self.uri_glob is None or fnmatchcase(document.uri, self.uri_glob)


class ChunkingRule(BaseModel):
    """A match and the chunker for the documents it matches.

    Attributes:
        match: The documents this rule applies to.
        chunker: The chunker those documents get.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    match: RuleMatch
    chunker: SerializeAsAny[Chunker]


class Chunking(BaseModel):
    """An ordered list of chunking rules and a fallback chunker.

    The first rule that matches a document picks its chunker. A document that no
    rule matches gets ``fallback``.

    Attributes:
        rules: The rules, most specific first.
        fallback: The chunker for documents that no rule matches.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rules: tuple[ChunkingRule, ...] = ()
    fallback: SerializeAsAny[Chunker]

    def select(self, document: Document) -> tuple[int | None, Chunker]:
        """Pick the chunker for a document.

        Args:
            document: The document to chunk.

        Returns:
            The index of the first matching rule and its chunker, or ``None`` and
            the fallback when no rule matches.
        """
        for index, rule in enumerate(self.rules):
            if rule.match.matches(document):
                return index, rule.chunker
        return None, self.fallback

    def fingerprint(self) -> str:
        """Return a hash of every rule match and every chunker setting."""
        return fingerprint_of(
            {
                "rules": [
                    {
                        "match": rule.match.model_dump(mode="json"),
                        "chunker": rule.chunker.settings(),
                    }
                    for rule in self.rules
                ],
                "fallback": self.fallback.settings(),
            }
        )


DEFAULT_CHUNKING = Chunking(
    rules=(
        ChunkingRule(
            match=RuleMatch(loader_names=["docling"]), chunker=DoclingChunker()
        ),
    ),
    fallback=RecursiveChunker(
        tokenizer="character", chunk_size=1024, min_characters_per_chunk=24
    ),
)
"""The preset that ``Graph`` uses: ``docling`` loads go to ``DoclingChunker``.

All other documents go to a ``RecursiveChunker`` with a 1024-character size.
"""
