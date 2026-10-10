"""Tests for SearchFilters in agrag.retrieval.filters.

Covers the empty case and label routing: labels appear in the vector-store
payload filter and never in the property-only filter. Labels are node labels,
never a node property.
"""

from agrag.retrieval.filters import SearchFilters


class TestSearchFilters:
    """SearchFilters builds payload filters and Cypher WHERE."""

    def test_empty_filters(self) -> None:
        """Empty filters produce no payload or WHERE."""
        f = SearchFilters()
        assert f.to_payload_filter() == {}
        where, params = f.to_cypher_where()
        assert where == ""
        assert params == {}

    def test_labels_in_payload(self) -> None:
        """Labels appear in payload filter."""
        f = SearchFilters(labels=["Person"])
        pf = f.to_payload_filter()
        assert pf["label"] == ["Person"]

    def test_labels_absent_from_property_filter(self) -> None:
        """Labels are node labels, never a node property."""
        f = SearchFilters(labels=["Person"], properties={"status": "active"})
        assert f.to_property_filter() == {"status": "active"}
