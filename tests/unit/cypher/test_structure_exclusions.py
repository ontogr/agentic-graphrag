"""Tests that graph-reading queries leave the document structure out.

Communities and neighbor search read the entity graph. The Section tree, the
``PART_OF`` edges and the record sources are not part of it.
"""

import pytest

from agrag.cypher.relations import (
    bfs_expand_query,
    fetch_all_relations_query,
    fetch_all_relations_query_cursor,
    relationship_types_from_query,
)


STRUCTURE_TYPES = ("PART_OF", "HAS_CHILD", "HAS_DOCUMENT", "MENTIONED_IN", "MEMBER_OF")


class TestRelationListings:
    """The relation listings skip edges that are not between entities."""

    @pytest.mark.parametrize(
        "query",
        [
            fetch_all_relations_query(),
            fetch_all_relations_query_cursor(),
            relationship_types_from_query(),
        ],
    )
    def test_structure_edge_types_are_excluded(self, query: str) -> None:
        """Each listing names every structure edge type in its exclusion list."""
        for relation_type in STRUCTURE_TYPES:
            assert f"'{relation_type}'" in query


class TestBfsExpansion:
    """A traversal never returns a structure node as a neighbor."""

    @pytest.mark.parametrize("label", ["Chunk", "Section", "Table", "Figure", "Source"])
    def test_structure_labels_are_excluded(self, label: str) -> None:
        """A path may pass through a chunk, but the result is never one."""
        query, _ = bfs_expand_query()

        assert f"NOT neighbor:{label}" in query
