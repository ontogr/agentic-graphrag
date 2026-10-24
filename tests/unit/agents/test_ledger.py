"""Tests for Ledger in agrag.agents.ledger.

Covers markdown rendering via render() for chunk text.
Key assignment and resolve() are covered by the integration
tests in tests/integration/agents.
"""

import hashlib
from uuid import uuid4

from agrag.agents.ledger import Ledger
from agrag.common.data_models.chunk import Chunk, TextProvenance
from agrag.common.data_models.search_result import SearchResult


def _chunk_result(text: str) -> SearchResult:
    """Build a chunk search result holding ``text``."""
    chunk = Chunk(
        id=uuid4(),
        document_id=uuid4(),
        text=text,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )
    return SearchResult(item=chunk, score=1.0, method="chunk")


class TestChunkRendering:
    """The agent sees the whole chunk."""

    def test_render_chunk_keeps_text_past_200_characters(self) -> None:
        """A figure late in a chunk stays visible to the agent."""
        text = "x" * 500 + " euro 26.4"

        assert Ledger().render(_chunk_result(text)) == f"[C1] Chunk: {text}"
