"""Tests for reading nodes out of GraphStore result rows."""

import pytest

from agrag.common.graph_rows import node_properties, row_node


class TestRowNode:
    """The node a row carries under ``n``, or the row itself."""

    def test_returns_the_node_under_n(self) -> None:
        """A row that names its node under ``n`` yields that node."""
        assert row_node({"n": {"id": "a"}}) == {"id": "a"}


class TestNodeProperties:
    """Properties come out flat whichever shape the node arrives in."""

    @pytest.mark.parametrize(
        "node",
        [{"id": "a", "name": "Ada"}, {"properties": {"id": "a", "name": "Ada"}}],
    )
    def test_flat_and_nested_shapes_give_the_same_properties(self, node: dict) -> None:
        """Both the flat dict and the ``properties`` wrapper give the same keys."""
        assert node_properties(node) == {"id": "a", "name": "Ada"}

    def test_nested_values_win_over_top_level_keys(self) -> None:
        """A key under ``properties`` overrides the top-level key of the same name."""
        node = {"id": "top", "properties": {"id": "nested"}}

        assert node_properties(node)["id"] == "nested"

    def test_unreadable_value_gives_an_empty_dict(self) -> None:
        """A value that cannot be read as a mapping yields no properties."""
        assert node_properties(None) == {}
        assert node_properties(42) == {}
