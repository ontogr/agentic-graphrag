"""Tests for the section chunker: packing, splitting, merging and tables."""

from types import SimpleNamespace

import pytest

from agrag.chunking import chunker as chunker_module
from agrag.chunking.chunker import Chunker, ChunkingError
from agrag.common.data_models.document import (
    DocumentSection,
    Unit,
    UnitKind,
)
from agrag.common.data_models.provenance import PageProvenance, TextProvenance
from agrag.common.data_models.structure import node_id, section_keys, version_id
from tests.unit.chunking._section_support import (
    page_unit,
    paragraph,
    record_document,
    sectioned_document,
    text_document,
)


def _words(count: int, word: str = "w") -> str:
    return " ".join([word] * count)


def _chunker(size: int = 50, min_size: int = 10) -> Chunker:
    return Chunker(size=size, min_size=min_size)


class TestSettings:
    """The settings are checked once and recorded."""

    def test_rejects_a_min_size_that_is_not_below_the_size(self) -> None:
        """Rejects a min size that is not below the size."""
        with pytest.raises(ValueError, match="min_size must be smaller"):
            Chunker(size=100, min_size=100)

    def test_equal_settings_give_equal_fingerprints(self) -> None:
        """Equal settings give equal fingerprints."""
        assert Chunker(size=100).fingerprint() == Chunker(size=100).fingerprint()
        assert Chunker(size=100).fingerprint() != Chunker(size=200).fingerprint()


class _SplitterThatReturns:
    """A stand-in for the chonkie splitter that returns fixed pieces."""

    def __init__(self, pieces: list[SimpleNamespace]) -> None:
        self._pieces = pieces

    def __call__(self, text: str) -> list[SimpleNamespace]:
        return self._pieces


class TestSplit:
    """Each piece is the slice of the text that it names."""

    def test_each_piece_is_the_slice_of_the_text_at_its_offsets(self) -> None:
        """Each piece equals the slice of the text between its offsets."""
        text = _words(300, "alpha")

        pieces = _chunker(size=40).split(text)

        assert len(pieces) > 1
        for piece in pieces:
            assert piece.text == text[piece.start_index : piece.end_index]

    def test_raises_when_a_piece_does_not_match_its_offsets(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A piece whose text differs from its slice raises, even if the pieces join."""
        wrong = SimpleNamespace(text="ab", start_index=0, end_index=0, token_count=1)
        monkeypatch.setattr(
            chunker_module,
            "RecursiveChunker",
            lambda **_: _SplitterThatReturns([wrong]),
        )
        chunker = Chunker(size=40, min_size=10)

        with pytest.raises(ChunkingError, match="offsets"):
            chunker.split("ab")


class TestPacking:
    """Units of one section pack up to the size."""

    def test_paragraphs_that_fit_make_one_chunk_that_is_a_slice_of_the_text(
        self,
    ) -> None:
        """Paragraphs that fit make one chunk that is a slice of the text."""
        document = text_document([_words(10), _words(10)])

        chunks = _chunker().chunk(document)

        assert len(chunks) == 1
        provenance = chunks[0].provenance
        assert isinstance(provenance, TextProvenance)
        assert (
            chunks[0].text == document.text[provenance.char_start : provenance.char_end]
        )
        assert chunks[0].text == document.text

    def test_a_unit_that_would_pass_the_size_starts_a_new_chunk(self) -> None:
        """A unit that would pass the size starts a new chunk."""
        document = text_document([_words(30), _words(30)])

        chunks = _chunker(size=40).chunk(document)

        assert [c.text for c in chunks] == [_words(30), _words(30)]
        assert [c.index for c in chunks] == [0, 1]

    def test_a_unit_over_the_size_is_split_without_losing_text(self) -> None:
        """A unit over the size is split without losing text."""
        body = _words(300, "alpha")
        document = text_document([body])

        chunks = _chunker(size=40).chunk(document)
        counter = _chunker(size=40).count_tokens

        assert len(chunks) > 1
        assert all(counter(c.text) <= 40 for c in chunks)
        assert "".join(c.text for c in chunks) == body
        for chunk in chunks:
            assert isinstance(chunk.provenance, TextProvenance)
            assert (
                document.text[chunk.provenance.char_start : chunk.provenance.char_end]
                == chunk.text
            )

    def test_blank_units_are_skipped(self) -> None:
        """Blank units are skipped."""
        section = DocumentSection(
            heading="", depth=0, units=[paragraph("   "), paragraph("real text")]
        )

        chunks = _chunker().chunk(sectioned_document([section]))

        assert [c.text for c in chunks] == ["real text"]


class TestMerging:
    """A small chunk goes on into the next section."""

    def _two_sections(self, first: int) -> list[DocumentSection]:
        return [
            DocumentSection(heading="A", depth=1, units=[paragraph(_words(first))]),
            DocumentSection(heading="B", depth=1, units=[paragraph(_words(20, "b"))]),
        ]

    def test_a_chunk_under_the_minimum_takes_the_next_section(self) -> None:
        """A chunk under the minimum takes the next section."""
        document = sectioned_document(self._two_sections(3))

        chunks = _chunker(size=50, min_size=10).chunk(document)

        assert len(chunks) == 1
        assert chunks[0].text.startswith("A\n\nw w w\n\nB\n\nb b b")
        assert len(chunks[0].section_ids) == 2

    def test_a_chunk_at_the_minimum_ends_with_its_section(self) -> None:
        """A chunk at the minimum ends with its section."""
        document = sectioned_document(self._two_sections(12))

        chunks = _chunker(size=50, min_size=10).chunk(document)

        assert len(chunks) == 2
        assert [len(c.section_ids) for c in chunks] == [1, 1]

    def test_headings_of_sections_in_one_chunk_come_from_the_lowest_container(
        self,
    ) -> None:
        """Headings of sections in one chunk come from the lowest container."""
        sections = [
            DocumentSection(heading="Top", depth=1),
            DocumentSection(heading="One", depth=2, parent=0, units=[paragraph("a b")]),
            DocumentSection(heading="Two", depth=2, parent=0, units=[paragraph("c d")]),
        ]

        chunks = _chunker().chunk(sectioned_document(sections))

        assert len(chunks) == 1
        assert chunks[0].heading_path == ["Top"]

    def test_a_chunk_inside_one_section_has_that_section_path(self) -> None:
        """A chunk inside one section has that section path."""
        sections = [
            DocumentSection(heading="Top", depth=1),
            DocumentSection(
                heading="One", depth=2, parent=0, units=[paragraph(_words(40))]
            ),
        ]

        chunks = _chunker().chunk(sectioned_document(sections))

        assert chunks[0].heading_path == ["Top", "One"]

    def test_a_chunk_carries_the_node_of_the_lowest_section_that_holds_it(
        self,
    ) -> None:
        """The parent section node is the lowest section that holds the chunk."""
        sections = [
            DocumentSection(heading="Top", depth=1),
            DocumentSection(heading="One", depth=2, parent=0, units=[paragraph("a b")]),
            DocumentSection(heading="Two", depth=2, parent=0, units=[paragraph("c d")]),
        ]
        document = sectioned_document(sections)

        chunks = _chunker().chunk(document)

        top = node_id(section_keys(document)[0], version_id(document))
        assert len(chunks) == 1
        assert chunks[0].parent_section_id == top

    def test_a_chunk_over_top_level_sections_has_no_parent_section(self) -> None:
        """Top-level sections share no section, so the chunk has no parent section."""
        sections = [
            DocumentSection(heading="One", depth=1, units=[paragraph("a b")]),
            DocumentSection(heading="Two", depth=1, units=[paragraph("c d")]),
        ]

        chunks = _chunker().chunk(sectioned_document(sections))

        assert len(chunks) == 1
        assert chunks[0].parent_section_id is None


class TestPageSources:
    """A source with page layout has no text offsets."""

    def test_units_are_joined_with_a_blank_line_and_keep_their_pages(self) -> None:
        """Units are joined with a blank line and keep their pages."""
        section = DocumentSection(
            heading="", depth=0, units=[page_unit("first", 2), page_unit("second", 1)]
        )

        chunks = _chunker().chunk(sectioned_document([section]))

        assert chunks[0].text == "first\n\nsecond"
        provenance = chunks[0].provenance
        assert isinstance(provenance, PageProvenance)
        assert [span.page_no for span in provenance.page_spans] == [1, 2]

    def test_a_heading_is_kept_when_the_previous_section_fills_a_chunk(self) -> None:
        """The heading of each page-layout section starts a chunk after a flush."""
        sections = [
            DocumentSection(heading="Alpha", depth=1, units=[paragraph(_words(30))]),
            DocumentSection(
                heading="Beta", depth=1, units=[paragraph(_words(30, "b"))]
            ),
        ]

        chunks = _chunker(size=50, min_size=10).chunk(sectioned_document(sections))

        assert [c.text.partition("\n\n")[0] for c in chunks] == ["Alpha", "Beta"]

    def test_a_source_with_no_pages_gets_empty_page_provenance(self) -> None:
        """A source with no pages gets empty page provenance."""
        section = DocumentSection(heading="", depth=0, units=[paragraph("text")])

        chunks = _chunker().chunk(sectioned_document([section]))

        assert chunks[0].provenance == PageProvenance(page_spans=[])


class TestTables:
    """A table is never mixed with text."""

    def test_a_table_is_its_own_chunk_and_flushes_the_text_before_it(self) -> None:
        """A table is its own chunk and flushes the text before it."""
        table = Unit(
            kind=UnitKind.TABLE,
            text="",
            rows=[["name", "qty"], ["a", "1"]],
        )
        section = DocumentSection(
            heading="S", depth=1, units=[paragraph("before"), table, paragraph("after")]
        )

        chunks = _chunker().chunk(sectioned_document([section]))

        assert [c.content_kind for c in chunks] == ["text", "table", "text"]
        assert chunks[1].text.startswith("| name | qty |")
        assert [c.index for c in chunks] == [0, 1, 2]
        assert [c.text for c in chunks if c.content_kind == "text"] == [
            "S\n\nbefore",
            "after",
        ]


class TestRecords:
    """A document with no sections is one unit of text."""

    def test_a_record_row_is_one_chunk_with_no_sections(self) -> None:
        """A record row is one chunk with no sections."""
        chunks = _chunker().chunk(record_document("name: ada | role: engineer"))

        assert len(chunks) == 1
        assert chunks[0].text == "name: ada | role: engineer"
        assert chunks[0].section_ids == []
        assert chunks[0].heading_path == []

    def test_an_empty_record_gives_no_chunks(self) -> None:
        """An empty record gives no chunks."""
        assert _chunker().chunk(record_document("  ")) == []


class TestIds:
    """Chunk ids are stable for one input and change with the version."""

    def test_same_input_gives_same_ids(self) -> None:
        """Same input gives same ids."""
        document = text_document([_words(20)])

        first = [c.id for c in _chunker().chunk(document)]
        second = [c.id for c in _chunker().chunk(document)]

        assert first == second

    def test_a_new_version_or_new_settings_give_new_ids(self) -> None:
        """A new version or new settings give new ids."""
        ids = {
            c.id
            for chunker, hash_ in [
                (_chunker(), "v1"),
                (_chunker(), "v2"),
                (_chunker(size=60), "v1"),
            ]
            for c in chunker.chunk(text_document([_words(20)], content_hash=hash_))
        }

        assert len(ids) == 3
