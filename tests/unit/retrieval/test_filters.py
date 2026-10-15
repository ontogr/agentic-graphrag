"""Tests for SearchFilters in agrag.retrieval.filters.

Covers the empty case and label routing: labels never appear in the
property-only filter, since they are node labels rather than node properties.
"""

from agrag.retrieval.filters import SearchFilters


class TestSearchFilters:
    """SearchFilters builds property filters and Cypher WHERE."""

    def test_empty_filters(self) -> None:
        """Empty filters produce no property filter or WHERE."""
        f = SearchFilters()
        assert f.to_property_filter() == {}
        where, params = f.to_cypher_where()
        assert where == ""
        assert params == {}

    def test_labels_absent_from_property_filter(self) -> None:
        """Labels are node labels, never a node property."""
        f = SearchFilters(labels=["Person"], properties={"status": "active"})
        assert f.to_property_filter() == {"status": "active"}
