"""Tests for the Cypher node builders and identifier validation."""

import pytest

from agrag.cypher.entities import (
    filter_clause,
    upsert_node_query,
    validate_identifier,
)


class TestValidateIdentifier:
    """validate_identifier accepts safe identifiers and rejects the rest."""

    def test_accepts_plain_label(self) -> None:
        """A plain PascalCase label passes through unchanged."""
        assert validate_identifier("Person") == "Person"

    def test_accepts_snake_and_underscore(self) -> None:
        """Underscores and mixed case are allowed."""
        assert validate_identifier("Chunk_Node") == "Chunk_Node"

    @pytest.mark.parametrize(
        "bad",
        ["", " ", "Person Node", "Person`x", "Person;DROP", "1Node", "Person.Node"],
    )
    def test_rejects_injection(self, bad: str) -> None:
        """A space, backtick, semicolon, leading digit, or dot is rejected."""
        with pytest.raises(ValueError):
            validate_identifier(bad)


class TestUpsertNodeQuery:
    """upsert_node_query builds a validated, UNWIND-batched merge."""

    def test_builds_unwind_merge(self) -> None:
        """The query merges on id and sets the properties map."""
        q = upsert_node_query("Chunk")
        assert "UNWIND $records" in q
        assert "MERGE (n:Chunk {id: record.id})" in q
        assert "SET n += record.properties" in q

    def test_validates_label(self) -> None:
        """An unsafe label raises before the query is built."""
        with pytest.raises(ValueError):
            upsert_node_query("Bad Label")


class TestFilterClause:
    """filter_clause turns a flat-dict filter into a WHERE clause."""

    def test_empty_returns_blank(self) -> None:
        """No filters yields no clause and no parameters."""
        where, params = filter_clause({})
        assert where == ""
        assert params == {}

    def test_scalar_equals(self) -> None:
        """A scalar filter becomes an equality clause."""
        where, params = filter_clause({"kind": "doc"})
        assert where == "WHERE node.kind = $filter_kind"
        assert params == {"filter_kind": "doc"}

    def test_list_in(self) -> None:
        """A list filter becomes an IN clause."""
        where, params = filter_clause({"kind": ["doc", "web"]})
        assert where == "WHERE node.kind IN $filter_kind"
        assert params == {"filter_kind": ["doc", "web"]}

    def test_multiple_keys_anded(self) -> None:
        """Multiple keys are AND-ed together."""
        where, params = filter_clause({"a": 1, "b": "x"})
        assert where == "WHERE node.a = $filter_a AND node.b = $filter_b"

    def test_rejects_bad_field(self) -> None:
        """A non-identifier field name raises."""
        with pytest.raises(ValueError):
            filter_clause({"bad field": 1})
