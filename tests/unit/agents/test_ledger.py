"""Tests for Ledger in agrag.agents.ledger.

Covers markdown rendering via render() for communities and chunk text.
Key assignment and resolve() are covered by the integration
tests in tests/integration/agents.
"""

from uuid import uuid4

from agrag.agents.ledger import Ledger
from agrag.common.data_models.chunk import Chunk, TextProvenance
from agrag.common.data_models.community import Community
from agrag.common.data_models.search_result import SearchResult


class TestLedger:
    """Ledger assigns and tracks stable citation keys."""

    def test_render_community(self) -> None:
        """render() returns markdown with title and summary for a community."""
        comm = Community(
            id=uuid4(),
            title="Aspirin research",
            summary="A community about headache treatments and dosage.",
            rating=7.0,
            rating_explanation="e",
        )
        ledger = Ledger()
        r = SearchResult(item=comm, score=0.9, method="community")
        text = ledger.render(r)
        assert text.startswith("[")
        assert "Aspirin research" in text
        assert "headache treatments" in text


def _chunk_result(text: str) -> SearchResult:
    """Build a chunk search result holding ``text``."""
    chunk = Chunk(
        id=uuid4(),
        document_id=uuid4(),
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )
    return SearchResult(item=chunk, score=1.0, method="chunk")


class TestChunkRendering:
    """The agent sees the whole chunk."""

    def test_render_chunk_keeps_text_past_200_characters(self) -> None:
        """A figure late in a chunk stays visible to the agent."""
        text = "x" * 500 + " euro 26.4"

        assert Ledger().render(_chunk_result(text)) == f"[C1] Chunk: {text}"
