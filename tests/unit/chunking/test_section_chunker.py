"""Tests for the section chunker: packing, splitting, merging and tables."""

from types import SimpleNamespace

import pytest

from agrag.chunking import chunker as chunker_module
from agrag.chunking.chunker import DEFAULT_TOKENIZER, Chunker, ChunkingError
from agrag.common.data_models.document import (
    DocumentSection,
    Unit,
    UnitKind,
)
from agrag.common.data_models.provenance import (
    BoundingBox,
    PageProvenance,
    PageSpan,
    TextProvenance,
)
from agrag.common.data_models.structure import (
    node_id,
    section_keys,
    unit_keys,
    version_id,
)
from tests.unit.chunking._section_support import (
    page_unit,
    record_document,
    sectioned_document,
    text_document,
)


def _words(count: int, word: str = "w") -> str:
    return " ".join([word] * count)


def _span(page_no: int) -> PageSpan:
    return PageSpan(page_no=page_no, bbox=BoundingBox(x0=0, y0=0, x1=1, y1=1))


def _chunker(size: int = 50, min_size: int = 10) -> Chunker:
    return Chunker(size=size, min_size=min_size)


class TestSettings:
    """The settings are checked once and recorded."""

    def test_rejects_a_min_size_that_is_not_below_the_size(self) -> None:
        """Rejects a min size that is not below the size."""
        with pytest.raises(ValueError, match="min_size must be smaller"):
            Chunker(size=100, min_size=100)

    def test_rejects_a_size_that_is_not_positive(self) -> None:
        """Rejects a size that is not positive."""
        with pytest.raises(ValueError, match="positive"):
            Chunker(size=0)

    def test_default_min_size_is_a_quarter_of_the_size(self) -> None:
        """The default min size is a quarter of the size."""
        assert Chunker(size=100).effective_min_size == 25
        assert Chunker(size=100).settings()["min_size"] == 25

    def test_rejects_a_negative_min_size(self) -> None:
        """A negative min size would flush at every section."""
        with pytest.raises(ValueError, match="must not be negative"):
            Chunker(size=100, min_size=-1)

    def test_an_explicit_zero_min_size_is_kept(self) -> None:
        """An explicit zero min size is kept."""
        assert Chunker(size=100, min_size=0).effective_min_size == 0

    def test_equal_settings_give_equal_fingerprints(self) -> None:
        """Equal settings give equal fingerprints."""
        assert Chunker(size=100).fingerprint == Chunker(size=100).fingerprint
        assert Chunker(size=100).fingerprint != Chunker(size=200).fingerprint


class TestCountTokens:
    """Token counts follow the configured tokenizer."""

    def test_default_tokenizer_is_o200k_base(self) -> None:
        """The chunker counts with o200k_base unless told otherwise."""
        assert Chunker().tokenizer == DEFAULT_TOKENIZER

    @pytest.mark.parametrize(
        ("text", "expected"),
        [("", 0), ("hello", 1), ("hello world", 2), ("   ", 1)],
    )
    def test_counts_tokens(self, text: str, expected: int) -> None:
        """Token counts match the fixtures."""
        assert _chunker().count_tokens(text) == expected


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

        chunks = _chunker().chunk(document).chunks

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

        chunks = _chunker(size=40).chunk(document).chunks

        assert [c.text for c in chunks] == [_words(30), _words(30)]
        assert [c.index for c in chunks] == [0, 1]

    def test_a_unit_over_the_size_is_split_without_losing_text(self) -> None:
        """A unit over the size is split without losing text."""
        body = _words(300, "alpha")
        document = text_document([body])

        chunks = _chunker(size=40).chunk(document).chunks
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
            heading="", depth=0, units=[page_unit("   ", 1), page_unit("real text", 1)]
        )

        chunks = _chunker().chunk(sectioned_document([section])).chunks

        assert [c.text for c in chunks] == ["real text"]

    def test_a_heading_starts_a_text_chunk(self) -> None:
        """A heading starts a text chunk."""
        document = text_document(["hello world"])
        document.sections[0] = document.sections[0].model_copy(update={"heading": "Hi"})

        chunks = _chunker().chunk(document).chunks

        assert [c.text for c in chunks] == ["Hi\n\nhello world"]
        provenance = chunks[0].provenance
        assert isinstance(provenance, TextProvenance)
        assert (provenance.char_start, provenance.char_end) == (0, len("hello world"))

    def test_joined_chunks_hold_to_the_size(self) -> None:
        """Joined chunks hold to the size."""
        section = DocumentSection(
            heading="",
            depth=0,
            units=[page_unit(_words(4), 1) for _ in range(3)],
        )
        chunker = _chunker(size=10, min_size=1)

        chunks = chunker.chunk(sectioned_document([section])).chunks

        assert len(chunks) == 2
        assert all(chunker.count_tokens(c.text) <= 10 for c in chunks)


class TestMerging:
    """A small chunk goes on into the next section."""

    def _two_sections(self, first: int) -> list[DocumentSection]:
        return [
            DocumentSection(heading="A", depth=1, units=[page_unit(_words(first), 1)]),
            DocumentSection(
                heading="B", depth=1, units=[page_unit(_words(20, "b"), 2)]
            ),
        ]

    def test_a_chunk_under_the_minimum_takes_the_next_section(self) -> None:
        """A chunk under the minimum takes the next section."""
        document = sectioned_document(self._two_sections(3))

        chunks = _chunker(size=50, min_size=10).chunk(document).chunks

        assert len(chunks) == 1
        assert chunks[0].text.startswith("A\n\nw w w\n\nB\n\nb b b")
        assert len(chunks[0].section_ids) == 2

    def test_a_chunk_at_the_minimum_ends_with_its_section(self) -> None:
        """A chunk at the minimum ends with its section."""
        document = sectioned_document(self._two_sections(12))
        chunker = _chunker(size=50, min_size=10)
        first_size = (
            chunker.count_tokens("A")
            + chunker.count_tokens("\n\n")
            + chunker.count_tokens(_words(12))
        )

        chunks = _chunker(size=50, min_size=first_size).chunk(document).chunks

        assert len(chunks) == 2
        assert [len(c.section_ids) for c in chunks] == [1, 1]

    def test_headings_of_sections_in_one_chunk_come_from_the_lowest_container(
        self,
    ) -> None:
        """Headings of sections in one chunk come from the lowest container."""
        sections = [
            DocumentSection(heading="Top", depth=1),
            DocumentSection(
                heading="One", depth=2, parent=0, units=[page_unit("a b", 1)]
            ),
            DocumentSection(
                heading="Two", depth=2, parent=0, units=[page_unit("c d", 2)]
            ),
        ]

        chunks = _chunker().chunk(sectioned_document(sections)).chunks

        assert len(chunks) == 1
        assert chunks[0].heading_path == ["Top"]

    def test_a_chunk_inside_one_section_has_that_section_path(self) -> None:
        """A chunk inside one section has that section path."""
        sections = [
            DocumentSection(heading="Top", depth=1),
            DocumentSection(
                heading="One", depth=2, parent=0, units=[page_unit(_words(40), 1)]
            ),
        ]

        chunks = _chunker().chunk(sectioned_document(sections)).chunks

        assert chunks[0].heading_path == ["Top", "One"]

    def test_a_chunk_carries_the_node_of_the_lowest_section_that_holds_it(
        self,
    ) -> None:
        """The parent section node is the lowest section that holds the chunk."""
        sections = [
            DocumentSection(heading="Top", depth=1),
            DocumentSection(
                heading="One", depth=2, parent=0, units=[page_unit("a b", 1)]
            ),
            DocumentSection(
                heading="Two", depth=2, parent=0, units=[page_unit("c d", 2)]
            ),
        ]
        document = sectioned_document(sections)

        result = _chunker().chunk(document)

        top = node_id(section_keys(document)[0], version_id(document))
        assert len(result.chunks) == 1
        assert result.placements[0].parent_node_id == top

    def test_a_chunk_over_top_level_sections_has_no_parent_section(self) -> None:
        """Top-level sections share no section, so the chunk has no parent section."""
        sections = [
            DocumentSection(heading="One", depth=1, units=[page_unit("a b", 1)]),
            DocumentSection(heading="Two", depth=1, units=[page_unit("c d", 2)]),
        ]

        result = _chunker().chunk(sectioned_document(sections))

        assert len(result.chunks) == 1
        assert result.placements[0].parent_node_id == result.chunks[0].document_id


class TestPageSources:
    """A source with page layout has no text offsets."""

    def test_units_are_joined_with_a_blank_line_and_keep_their_pages(self) -> None:
        """Units are joined with a blank line and keep their pages."""
        section = DocumentSection(
            heading="", depth=0, units=[page_unit("first", 2), page_unit("second", 1)]
        )

        chunks = _chunker().chunk(sectioned_document([section])).chunks

        assert chunks[0].text == "first\n\nsecond"
        provenance = chunks[0].provenance
        assert isinstance(provenance, PageProvenance)
        assert [span.page_no for span in provenance.page_spans] == [1, 2]

    def test_a_heading_is_kept_when_the_previous_section_fills_a_chunk(self) -> None:
        """The heading of each page-layout section starts a chunk after a flush."""
        sections = [
            DocumentSection(heading="Alpha", depth=1, units=[page_unit(_words(30), 1)]),
            DocumentSection(
                heading="Beta", depth=1, units=[page_unit(_words(30, "b"), 2)]
            ),
        ]

        chunks = (
            _chunker(size=50, min_size=10).chunk(sectioned_document(sections)).chunks
        )

        assert [c.text.partition("\n\n")[0] for c in chunks] == ["Alpha", "Beta"]

    def test_a_source_with_no_pages_gets_empty_page_provenance(self) -> None:
        """A source with no pages gets empty page provenance."""
        section = DocumentSection(heading="H", depth=1)

        chunks = _chunker().chunk(sectioned_document([section])).chunks

        assert chunks[0].text == "H"
        assert chunks[0].provenance == PageProvenance(page_spans=[])


class TestLayout:
    """A document uses text offsets or page layout, never both."""

    def test_mixed_offsets_and_pages_raise(self) -> None:
        """Mixed offsets and pages raise."""
        document = text_document(["hello"])
        document.sections.append(
            DocumentSection(heading="P", depth=1, units=[page_unit("x", 1)])
        )

        with pytest.raises(ChunkingError, match="mixes"):
            _chunker().chunk(document)


class TestTables:
    """A table is never mixed with text."""

    def test_a_trailing_heading_with_no_text_makes_no_chunk(self) -> None:
        """A heading after the last text has no offsets and adds no chunk."""
        document = text_document([_words(20)])
        document.sections.append(DocumentSection(heading="End", depth=1, units=[]))

        chunks = _chunker().chunk(document).chunks

        assert [c.text for c in chunks] == [_words(20)]

    def test_a_table_is_its_own_chunk_and_flushes_the_text_before_it(self) -> None:
        """A table is its own chunk and flushes the text before it."""
        table = Unit(
            kind=UnitKind.TABLE,
            text="",
            rows=[["name", "qty"], ["a", "1"]],
            pages=[_span(1)],
        )
        section = DocumentSection(
            heading="S",
            depth=1,
            units=[page_unit("before", 1), table, page_unit("after", 2)],
        )

        chunks = _chunker().chunk(sectioned_document([section])).chunks

        assert [c.content_kind for c in chunks] == ["text", "table", "text"]
        assert chunks[1].text.startswith("| name | qty |")
        assert [c.index for c in chunks] == [0, 1, 2]
        assert [c.text for c in chunks if c.content_kind == "text"] == [
            "S\n\nbefore",
            "after",
        ]

    def test_a_table_chunk_points_at_its_table(self) -> None:
        """A table chunk points at its table."""
        table = Unit(
            kind=UnitKind.TABLE,
            text="",
            rows=[["name", "qty"], ["a", "1"]],
            pages=[_span(1)],
        )
        section = DocumentSection(heading="S", depth=1, units=[table])
        document = sectioned_document([section])

        result = _chunker().chunk(document)

        key = unit_keys(document, section_keys(document))[(0, 0)]
        table_id = node_id(key, version_id(document))
        assert [c.content_kind for c in result.chunks] == ["text", "table"]
        assert result.chunks[0].text == "S"
        assert result.placements[1].parent_node_id == table_id
        assert result.placements[1].order == result.placements[1].chunk_index == 1

    def test_a_whole_table_keeps_its_pages(self) -> None:
        """A whole table keeps its pages."""
        span = PageSpan(page_no=2, bbox=BoundingBox(x0=0, y0=0, x1=1, y1=1))
        table = Unit(
            kind=UnitKind.TABLE,
            text="",
            rows=[["h"], ["a"]],
            pages=[span],
        )
        section = DocumentSection(heading="", depth=0, units=[table])

        chunks = _chunker().chunk(sectioned_document([section])).chunks

        provenance = chunks[0].provenance
        assert isinstance(provenance, PageProvenance)
        assert provenance.page_spans == [span]

    def test_split_table_groups_claim_no_pages(self) -> None:
        """Split table groups claim no pages."""
        span = PageSpan(page_no=2, bbox=BoundingBox(x0=0, y0=0, x1=1, y1=1))
        rows = [["k", "v"], *[[f"row{i}", "x"] for i in range(30)]]
        table = Unit(kind=UnitKind.TABLE, text="", rows=rows, pages=[span])
        section = DocumentSection(heading="", depth=0, units=[table])

        result = _chunker(size=30).chunk(sectioned_document([section]))

        assert len(result.chunks) > 1
        for chunk in result.chunks:
            assert isinstance(chunk.provenance, PageProvenance)
            assert chunk.provenance.page_spans == []


class TestRecords:
    """A document with no sections is one unit of text."""

    def test_a_record_row_is_one_chunk_with_no_sections(self) -> None:
        """A record row is one chunk with no sections."""
        chunks = _chunker().chunk(record_document("name: ada | role: engineer")).chunks

        assert len(chunks) == 1
        assert chunks[0].text == "name: ada | role: engineer"
        assert chunks[0].section_ids == []
        assert chunks[0].heading_path == []

    def test_an_empty_record_gives_no_chunks(self) -> None:
        """An empty record gives no chunks."""
        assert _chunker().chunk(record_document("  ")).chunks == []


class TestIds:
    """Chunk ids are stable for one input and change with the version."""

    def test_same_input_gives_same_ids(self) -> None:
        """Same input gives same ids."""
        document = text_document([_words(20)])

        first = [c.id for c in _chunker().chunk(document).chunks]
        second = [c.id for c in _chunker().chunk(document).chunks]

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
            for c in chunker.chunk(
                text_document([_words(20)], content_hash=hash_)
            ).chunks
        }

        assert len(ids) == 3
