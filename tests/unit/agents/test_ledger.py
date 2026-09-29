"""Tests for Ledger in agrag.agents.ledger.

Covers markdown rendering via render() for resolved entities, query values,
and communities. Key assignment and resolve() are covered by the integration
tests in tests/integration/agents.
"""

from uuid import uuid4

import pytest

from agrag.agents.ledger import Ledger
from agrag.common.data_models.chunk import Chunk, TextProvenance
from agrag.common.data_models.community import Community
from agrag.common.data_models.query_value import QueryValue
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.search_result import SearchResult


class TestLedger:
    """Ledger assigns and tracks stable citation keys."""

    def test_render_resolved_entity(self) -> None:
        """Resolved entities use entity citation keys and details."""
        item = ResolvedEntity(id=uuid4(), label="Person", name="Alice")
        text = Ledger().render(SearchResult(item=item, score=1.0, method="entity"))

        assert text == "[E1] Entity: Alice (Person)"

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(3, "[V1] Value: 3"), ({"count": 3}, "[V1] Value: {'count': 3}")],
    )
    def test_render_query_value(self, value: object, expected: str) -> None:
        """Query values use value citation keys and render their complete row."""
        result = SearchResult(item=QueryValue(value=value), score=1.0, method="cypher")

        assert Ledger().render(result) == expected

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

    def test_render_chunk_keeps_a_5000_character_chunk_whole(self) -> None:
        """A large chunk from a custom chunker is not cut."""
        text = "y" * 5000 + " last words"

        assert Ledger().render(_chunk_result(text)) == f"[C1] Chunk: {text}"


def _child_result(text: str, parent: Chunk) -> SearchResult:
    child = Chunk(
        id=uuid4(),
        document_id=parent.document_id,
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
        parent_id=parent.id,
    )
    return SearchResult(item=child, score=1.0, method="chunk", parent=parent)


class TestParentRendering:
    """A child hit shows its parent once and later children show their own text."""

    def _parent(self) -> Chunk:
        text = "the full parent passage, longer than any child"
        return Chunk(
            document_id=uuid4(),
            text=text,
            provenance=TextProvenance(char_start=0, char_end=len(text)),
            level=1,
        )

    def test_first_child_renders_the_parent_text_under_the_children_key(self) -> None:
        """The agent reads the parent and cites the child."""
        parent = self._parent()
        ledger = Ledger()
        result = _child_result("child one", parent)

        assert ledger.render(result) == f"[C1] Chunk: {parent.text}"
        assert ledger.resolve("C1") is result

    def test_second_child_of_the_same_parent_renders_its_own_text(self) -> None:
        """A later child is marked as part of the first key and adds no parent text."""
        parent = self._parent()
        ledger = Ledger()
        ledger.render(_child_result("child one", parent))

        rendered = ledger.render(_child_result("child two", parent))

        assert rendered == "[C2] Chunk (part of [C1]): child two"

    def test_rendering_the_same_child_again_repeats_its_first_text(self) -> None:
        """Rendering one result twice gives the same block, not a part-of note."""
        parent = self._parent()
        ledger = Ledger()
        result = _child_result("child one", parent)

        first = ledger.render(result)

        assert ledger.render(result) == first

    def test_children_of_different_parents_each_show_their_parent(self) -> None:
        """Each parent is shown once."""
        ledger = Ledger()
        one, two = self._parent(), self._parent()

        assert ledger.render(_child_result("a", one)).endswith(one.text)
        assert ledger.render(_child_result("b", two)).endswith(two.text)

    def test_result_without_a_parent_renders_as_before(self) -> None:
        """Standalone chunks are unchanged."""
        assert Ledger().render(_chunk_result("plain")) == "[C1] Chunk: plain"
