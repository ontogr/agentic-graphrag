"""Tests for table chunks: a whole table, or row groups that repeat the header."""

from agrag.chunking._tables import table_texts
from agrag.common.data_models.document import Unit, UnitKind


def _count(text: str) -> int:
    return len(text.split())


def _table(rows: list[list[str]], **fields: object) -> Unit:
    return Unit(kind=UnitKind.TABLE, text="", rows=rows, **fields)


class TestTableTexts:
    """A table becomes Markdown that always carries its header."""

    def test_a_table_that_fits_is_one_chunk(self) -> None:
        """A table that fits is one chunk."""
        unit = _table([["name", "qty"], ["a", "1"], ["b", "2"]])

        texts = table_texts(unit, 100, _count)

        assert texts == ["| name | qty |\n| --- | --- |\n| a | 1 |\n| b | 2 |"]

    def test_the_first_row_is_the_header_when_none_is_marked(self) -> None:
        """The first row is the header when none is marked."""
        unit = _table([["h1", "h2"], ["x", "y"]], header_rows=0)

        assert table_texts(unit, 100, _count)[0].startswith("| h1 | h2 |")

    def test_every_group_repeats_the_header_and_only_the_first_has_the_caption(
        self,
    ) -> None:
        """Every group repeats the header and only the first has the caption."""
        rows = [["name", "qty"], *[[f"item{i}", str(i)] for i in range(12)]]
        unit = _table(rows, caption="Stock")

        texts = table_texts(unit, 20, _count)

        assert len(texts) > 1
        assert texts[0].startswith("Stock\n| name | qty |")
        assert all("| name | qty |\n| --- | --- |" in text for text in texts)
        assert not any(text.startswith("Stock") for text in texts[1:])
        assert all(_count(text) <= 20 for text in texts)

    def test_no_row_is_lost_or_repeated_across_groups(self) -> None:
        """No row is lost or repeated across groups."""
        rows = [["k", "v"], *[[f"row{i}", "x"] for i in range(30)]]

        texts = table_texts(_table(rows), 25, _count)

        found = [line for text in texts for line in text.split("\n") if "row" in line]
        assert found == [f"| row{i} | x |" for i in range(30)]

    def test_a_row_over_the_size_gets_its_own_group(self) -> None:
        """A row over the size gets its own group."""
        big = " ".join(["word"] * 40)
        unit = _table([["a", "b"], ["small", "1"], [big, "2"], ["small2", "3"]])

        texts = table_texts(unit, 15, _count)

        assert any(big in text for text in texts)
        assert sum(big in text for text in texts) == 1

    def test_spanned_header_cells_are_written_once(self) -> None:
        """Spanned header cells are written once."""
        unit = _table(
            [["Total", "Total"], ["a", "b"], ["1", "2"]],
            header_rows=2,
        )

        assert table_texts(unit, 100, _count)[0].startswith("| Total a | Total b |")

    def test_a_pipe_in_a_cell_is_escaped(self) -> None:
        """A pipe in a cell is escaped."""
        unit = _table([["h"], ["a|b"]])

        assert "a\\|b" in table_texts(unit, 100, _count)[0]

    def test_a_table_with_no_rows_gives_no_chunks(self) -> None:
        """A table with no rows gives no chunks."""
        assert table_texts(_table([]), 100, _count) == []
