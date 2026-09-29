"""The parent-child strategy: large parents to extract, small children to search."""

from pydantic import Field, SerializeAsAny

from agrag.chunking._text import build_text_chunks, shifted_spans
from agrag.chunking.base import Chunker, SpanChunker
from agrag.chunking.recursive import RecursiveChunker
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document


def _default_parent() -> RecursiveChunker:
    return RecursiveChunker(chunk_size=1024)


def _default_child() -> RecursiveChunker:
    return RecursiveChunker(chunk_size=256)


class ParentChildChunker(Chunker):
    """Cuts a document into parent chunks and cuts each parent into child chunks.

    Extraction runs on the parents, which have ``level=1``. The children have
    ``level=0`` and a ``parent_id``, and only the children are embedded and searched.
    A search hit returns the child with its parent attached.

    A child never crosses a parent boundary, because the child strategy cuts each
    parent alone. A parent that the child strategy leaves without a piece gets one
    child with the span of the parent. The chunker returns all parents, then all
    children. Indexes count from 0 at each level.

    Attributes:
        parent: The strategy that cuts the document into parents.
        child: The strategy that cuts each parent into children.
    """

    parent: SerializeAsAny[SpanChunker] = Field(default_factory=_default_parent)
    child: SerializeAsAny[SpanChunker] = Field(default_factory=_default_child)

    @property
    def strategy(self) -> str:
        """The strategy name, ``"parent-child"``."""
        return "parent-child"

    def _split(self, document: Document) -> list[Chunk]:
        text = document.text
        parent_spans = self.parent.spans(text)
        if not parent_spans and text.strip():
            raise self._error(document, 0, "no parents for non-empty text")
        parents = build_text_chunks(document, parent_spans, level=1)
        child_spans: list[tuple[int, int]] = []
        child_parents = []
        for parent, (start, end) in zip(parents, parent_spans, strict=True):
            spans = shifted_spans(self.child.spans, text, start, end) or [(start, end)]
            child_spans.extend(spans)
            child_parents.extend([parent.id] * len(spans))
        children = build_text_chunks(document, child_spans, parent_ids=child_parents)
        return [*parents, *children]
