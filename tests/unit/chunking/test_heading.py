"""Tests for HeadingChunker: sections packed to a budget, never across a split heading.

The tests count with the ``character`` tokenizer so a budget is a number of
characters. Documents are built with a hand-made outline whose offsets point at the
heading lines of the text.
"""

import pytest

from agrag.chunking import HeadingChunker, RecursiveChunker
from agrag.common.data_models.document import Document, HeadingRef
from tests.unit.chunking._support import make_document


def _chunker(size: int, split_level: int = 2) -> HeadingChunker:
    return HeadingChunker(
        chunk_size=size,
        split_level=split_level,
        tokenizer="character",
        fallback=RecursiveChunker(chunk_size=size, tokenizer="character"),
    )


def _markdown(sections: list[tuple[int, str, str]], preamble: str = "") -> Document:
    """Build a document from ``(level, title, body)`` and a matching outline."""
    text = preamble
    outline = []
    for level, title, body in sections:
        outline.append(HeadingRef(text=title, level=level, char_start=len(text)))
        text += f"{'#' * level} {title}\n\n{body}\n\n"
    return make_document(text, outline=outline)


class TestSections:
    """Chunks follow the sections at the split level."""

    def test_each_split_level_section_is_a_chunk_when_it_fits(self) -> None:
        """Small sibling sections stay separate."""
        document = _markdown(
            [
                (1, "Guide", "intro"),
                (2, "A", "alpha"),
                (2, "B", "beta"),
                (2, "C", "gamma"),
            ]
        )

        chunks = _chunker(500).chunk(document)

        assert [c.text.split("\n")[0] for c in chunks] == [
            "# Guide",
            "## A",
            "## B",
            "## C",
        ]
        assert {c.chunker for c in chunks} == {"heading"}

    def test_no_chunk_holds_a_split_level_heading_after_its_start(self) -> None:
        """A level-1 or level-2 heading appears only as the first line of a chunk."""
        document = _markdown(
            [
                (1, "T", "x " * 40),
                (2, "A", "y " * 40),
                (3, "A1", "z " * 40),
                (2, "B", "w " * 40),
            ]
        )

        for chunk in _chunker(120).chunk(document):
            later = chunk.text.split("\n", 1)[-1] if "\n" in chunk.text else ""
            assert "\n# " not in "\n" + later and "\n## " not in "\n" + later

    def test_preamble_before_the_first_heading_is_a_chunk(self) -> None:
        """Text above the first heading is kept and has no heading path."""
        document = _markdown([(1, "T", "body")], preamble="Front matter line.\n\n")

        chunks = _chunker(500).chunk(document)

        assert chunks[0].text.startswith("Front matter")
        assert chunks[0].heading_path == []
        assert chunks[1].heading_path == ["T"]

    def test_whitespace_only_preamble_makes_no_chunk(self) -> None:
        """Blank text above the first heading is dropped."""
        document = _markdown([(1, "T", "body")], preamble="\n\n")

        assert len(_chunker(500).chunk(document)) == 1

    def test_heading_paths_follow_the_outline(self) -> None:
        """Each chunk names the headings above its start."""
        document = _markdown([(1, "Top", "a"), (2, "Sub", "b")])

        assert [c.heading_path for c in _chunker(500).chunk(document)] == [
            ["Top"],
            ["Top", "Sub"],
        ]


class TestLargeSections:
    """A section above the budget is cut at deeper headings, then by the fallback."""

    def test_large_section_is_cut_at_deeper_headings_and_packed(self) -> None:
        """Sub-sections of one big section pack greedily up to the budget."""
        document = _markdown(
            [
                (2, "Big", "intro"),
                (3, "s1", "a" * 40),
                (3, "s2", "b" * 40),
                (3, "s3", "c" * 40),
                (3, "s4", "d" * 40),
            ]
        )

        chunks = _chunker(120).chunk(document)

        assert len(chunks) > 1
        assert all(len(c.text) <= 120 for c in chunks)
        assert {c.chunker for c in chunks} == {"heading"}
        starts = [c.text.split("\n")[0] for c in chunks]
        assert starts[0] == "## Big"

    def test_piece_over_the_budget_goes_to_the_fallback_and_is_flagged(self) -> None:
        """A section with no deeper heading and too long is split and labelled."""
        document = _markdown(
            [(2, "Small", "tiny"), (2, "Long", " ".join(f"w{i}" for i in range(120)))]
        )

        chunks = _chunker(100).chunk(document)

        flagged = [c for c in chunks if c.chunker == "heading:recursive"]
        assert len(flagged) > 1
        assert chunks[0].chunker == "heading"
        assert all(c.heading_path == ["Long"] for c in flagged)

    def test_empty_outline_runs_the_fallback_on_the_whole_text(self) -> None:
        """No headings means the fallback strategy, and the label says so."""
        document = make_document("plain words " * 40)

        chunks = _chunker(100).chunk(document)

        assert len(chunks) > 1
        assert {c.chunker for c in chunks} == {"heading:recursive"}


class TestOutlineEdgeCases:
    """Odd outlines do not break the contract."""

    def test_only_deeper_headings_give_one_section(self) -> None:
        """With split_level 1 and only level 3 headings, the text is one section."""
        document = _markdown([(3, "a", "x"), (3, "b", "y")])

        chunks = _chunker(500, split_level=1).chunk(document)

        assert len(chunks) == 1
        assert chunks[0].text == document.text.rstrip()

    def test_duplicate_and_out_of_range_offsets_are_ignored(self) -> None:
        """Repeated offsets and offsets past the end add no empty chunk."""
        document = _markdown([(2, "A", "alpha"), (2, "B", "beta")])
        outline = [
            *document.heading_outline,
            document.heading_outline[0],
            HeadingRef(text="ghost", level=2, char_start=len(document.text) + 50),
        ]
        document = document.model_copy(update={"heading_outline": outline})

        chunks = _chunker(500).chunk(document)

        assert [c.text.split("\n")[0] for c in chunks] == ["## A", "## B"]

    @pytest.mark.parametrize("level", [1, 6])
    def test_split_level_bounds(self, level: int) -> None:
        """The lowest and highest split levels work."""
        document = _markdown([(1, "T", "a"), (6, "deep", "b")])

        assert _chunker(500, split_level=level).chunk(document)

    @pytest.mark.parametrize("level", [0, 7])
    def test_rejects_split_level_out_of_range(self, level: int) -> None:
        """The split level must be from 1 to 6."""
        with pytest.raises(ValueError, match="split_level"):
            HeadingChunker(split_level=level)

    def test_non_ascii_headings_keep_exact_offsets(self) -> None:
        """Unicode headings and bodies slice back to the source."""
        document = _markdown([(1, "日本語", "\U0001f600 body"), (2, "Café", "é")])

        for chunk in _chunker(500).chunk(document):
            start = chunk.provenance.char_start
            end = chunk.provenance.char_end
            assert chunk.text == document.text[start:end]

    def test_empty_document_gives_no_chunks(self) -> None:
        """No text, no chunks."""
        assert _chunker(100).chunk(make_document("")) == []

    def test_same_input_gives_the_same_chunks(self) -> None:
        """Chunking is deterministic."""
        document = _markdown([(2, "A", "x " * 80), (3, "B", "y " * 80)])
        chunker = _chunker(90)

        def key(chunks):
            return [(c.id, c.text, c.chunker) for c in chunks]

        assert key(chunker.chunk(document)) == key(chunker.chunk(document))


class TestProperties:
    """Random outlines keep the contract."""

    def test_chunks_cover_the_text_and_respect_split_headings(self) -> None:
        """Slices match, non-blank text is covered, split headings only start chunks."""
        import random  # noqa: PLC0415

        rng = random.Random(3)
        for seed in range(100):
            rng.seed(seed)
            sections = [
                (
                    rng.randint(1, 4),
                    f"Title {i}",
                    " ".join(
                        rng.choice(["a", "bb", "日本", "\U0001f600"])
                        for _ in range(rng.randint(0, 60))
                    ),
                )
                for i in range(rng.randint(1, 10))
            ]
            document = _markdown(sections)
            split_level = rng.randint(1, 4)

            chunks = _chunker(rng.choice([30, 90, 300]), split_level).chunk(document)

            covered = [False] * len(document.text)
            starts = {
                h.char_start for h in document.heading_outline if h.level <= split_level
            }
            for chunk in chunks:
                start = chunk.provenance.char_start
                end = chunk.provenance.char_end
                assert chunk.text == document.text[start:end]
                for i in range(start, end):
                    covered[i] = True
                inside = [o for o in starts if start < o < end]
                assert not inside
            assert all(c or document.text[i].isspace() for i, c in enumerate(covered))
