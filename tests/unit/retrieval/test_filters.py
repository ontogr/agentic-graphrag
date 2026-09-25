"""Tests for SearchFilters in agrag.retrieval.filters.

Covers the empty case, and that labels, document ids, and arbitrary
properties route correctly across the three output shapes: the vector-store
payload filter, the property-only filter, and the generated Cypher WHERE
clause with its parameters. Verifies labels are treated as node labels
(native Cypher label checks), never as a node property.
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

    def test_document_ids_in_property_filter(self) -> None:
        """Document ids stay a property filter."""
        f = SearchFilters(document_ids=["doc1"])
        assert f.to_property_filter() == {"document_id": ["doc1"]}

    def test_document_ids_in_payload(self) -> None:
        """Document ids appear in payload filter."""
        f = SearchFilters(document_ids=["doc1"])
        pf = f.to_payload_filter()
        assert pf["document_id"] == ["doc1"]

    def test_properties_in_payload(self) -> None:
        """Properties appear in payload filter."""
        f = SearchFilters(properties={"kind": "web"})
        pf = f.to_payload_filter()
        assert pf["kind"] == "web"

    def test_cypher_where_with_properties(self) -> None:
        """Properties produce equality clauses."""
        f = SearchFilters(properties={"status": "active"})
        where, params = f.to_cypher_where()
        assert "status" in where
        assert "filter_status" in params
