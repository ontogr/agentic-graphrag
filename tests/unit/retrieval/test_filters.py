"""Tests for SearchFilters."""

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

    def test_cypher_where_with_labels(self) -> None:
        """Labels produce native Cypher node-label checks."""
        f = SearchFilters(labels=["Person", "Org"])
        where, params = f.to_cypher_where()
        assert "node:Person" in where
        assert "node:Org" in where
        assert params == {}

    def test_cypher_where_with_properties(self) -> None:
        """Properties produce equality clauses."""
        f = SearchFilters(properties={"status": "active"})
        where, params = f.to_cypher_where()
        assert "status" in where
        assert "filter_status" in params
