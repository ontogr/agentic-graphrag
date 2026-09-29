"""Tests for ParentChildChunker: parents for extraction, children for search.

Sizes use the ``character`` tokenizer so a budget is a number of characters.
"""

from agrag.chunking import (
    ParentChildChunker,
    RecursiveChunker,
    SentenceChunker,
    TokenChunker,
)
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import HeadingRef
from agrag.common.data_models.provenance import TextProvenance
from tests.unit.chunking._support import make_document


def _chunker(parent: int = 200, child: int = 60) -> ParentChildChunker:
    return ParentChildChunker(
        parent=RecursiveChunker(chunk_size=parent, tokenizer="character"),
        child=RecursiveChunker(chunk_size=child, tokenizer="character"),
    )


def _span(chunk: Chunk) -> tuple[int, int]:
    assert isinstance(chunk.provenance, TextProvenance)
    return chunk.provenance.char_start, chunk.provenance.char_end


def _split(chunks: list[Chunk]) -> tuple[list[Chunk], list[Chunk]]:
    return (
        [c for c in chunks if c.level == 1],
        [c for c in chunks if c.level == 0],
    )


_TEXT = " ".join(f"Sentence number {i} is here." for i in range(60))


class TestStructure:
    """Parents come first, children point at their parent."""

    def test_returns_parents_then_children_with_per_level_indexes(self) -> None:
        """Indexes restart at zero for each level."""
        chunks = _chunker().chunk(make_document(_TEXT))
        parents, children = _split(chunks)

        assert chunks == [*parents, *children]
        assert [c.index for c in parents] == list(range(len(parents)))
        assert [c.index for c in children] == list(range(len(children)))
        assert len(children) > len(parents) > 1

    def test_every_child_lies_inside_exactly_its_parent(self) -> None:
        """A child span is within the span of the parent it names, and only that one."""
        parents, children = _split(_chunker().chunk(make_document(_TEXT)))
        by_id = {p.id: _span(p) for p in parents}

        for child in children:
            start, end = _span(child)
            assert child.parent_id in by_id
            p_start, p_end = by_id[child.parent_id]
            assert p_start <= start < end <= p_end
            containing = [
                pid for pid, (a, b) in by_id.items() if a <= start and end <= b
            ]
            assert containing == [child.parent_id]

    def test_children_cover_their_parent(self) -> None:
        """Non-blank text of a parent is in some child of that parent."""
        document = make_document(_TEXT)
        parents, children = _split(_chunker().chunk(document))

        for parent in parents:
            start, end = _span(parent)
            covered = [False] * (end - start)
            for child in (c for c in children if c.parent_id == parent.id):
                a, b = _span(child)
                for i in range(a, b):
                    covered[i - start] = True
            assert all(
                c or document.text[start + i].isspace() for i, c in enumerate(covered)
            )

    def test_chunks_name_the_chunker_at_both_levels(self) -> None:
        """Parents and children carry the parent-child name."""
        chunks = _chunker().chunk(make_document(_TEXT))

        assert {c.chunker for c in chunks} == {"parent-child"}

    def test_ids_are_unique_even_when_a_parent_and_child_share_a_span(self) -> None:
        """A short parent with one equal child still gets two ids."""
        chunks = _chunker(parent=500, child=500).chunk(make_document("short text here"))

        parents, children = _split(chunks)
        assert _span(parents[0]) == _span(children[0])
        assert parents[0].id != children[0].id
        assert children[0].parent_id == parents[0].id

    def test_document_shorter_than_a_child_gives_one_of_each(self) -> None:
        """A tiny document has a parent and a child."""
        parents, children = _split(_chunker().chunk(make_document("tiny")))

        assert len(parents) == len(children) == 1

    def test_empty_document_gives_no_chunks(self) -> None:
        """No text, no chunks."""
        assert _chunker().chunk(make_document("")) == []

    def test_overlapping_children_stay_inside_their_parent(self) -> None:
        """Child overlap never crosses a parent boundary."""
        chunker = ParentChildChunker(
            parent=RecursiveChunker(chunk_size=200, tokenizer="character"),
            child=TokenChunker(chunk_size=50, chunk_overlap=20, tokenizer="character"),
        )
        parents, children = _split(chunker.chunk(make_document(_TEXT)))
        by_id = {p.id: _span(p) for p in parents}

        for child in children:
            a, b = _span(child)
            p_start, p_end = by_id[child.parent_id]
            assert p_start <= a and b <= p_end

    def test_heading_path_is_set_on_both_levels(self) -> None:
        """Parents and children take the heading above their start."""
        text = "# Title\n\n" + _TEXT
        document = make_document(
            text, outline=[HeadingRef(text="Title", level=1, char_start=0)]
        )

        chunks = _chunker().chunk(document)

        assert {tuple(c.heading_path) for c in chunks} == {("Title",)}

    def test_output_is_deterministic(self) -> None:
        """The same document gives the same ids and texts."""
        chunker = _chunker()
        document = make_document(_TEXT)

        def key(chunks: list[Chunk]) -> list[object]:
            return [(c.id, c.text, c.level, c.parent_id) for c in chunks]

        assert key(chunker.chunk(document)) == key(chunker.chunk(document))


class TestSettings:
    """Nested settings are part of the fingerprint."""

    def test_child_settings_change_the_fingerprint(self) -> None:
        """Changing only the child size changes the hash."""
        assert _chunker(child=60).fingerprint() != _chunker(child=61).fingerprint()

    def test_settings_show_both_nested_chunkers(self) -> None:
        """settings() lists the parent and child strategies and sizes."""
        settings = ParentChildChunker(
            parent=RecursiveChunker(chunk_size=1024),
            child=SentenceChunker(chunk_size=64),
        ).settings()

        assert settings["parent"]["strategy"] == "recursive"
        assert settings["child"] == {
            **settings["child"],
            "strategy": "sentence",
            "chunk_size": 64,
        }

    def test_defaults_are_recursive_at_1024_and_256_tokens(self) -> None:
        """The default budgets are 1024 tokens for parents and 256 for children."""
        chunker = ParentChildChunker()

        assert chunker.parent.settings()["chunk_size"] == 1024
        assert chunker.child.settings()["chunk_size"] == 256
