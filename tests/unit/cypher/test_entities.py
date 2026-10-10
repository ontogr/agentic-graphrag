"""Tests for the node-focused Cypher query builders in agrag.cypher.entities.

Covers identifier validation, parametrized over injection-shaped inputs
(spaces, backticks, semicolons, leading digits, dots, hyphens). Verifies that
upsert_node_query and upsert_survivor_query reject unsafe or empty labels, and
that filter_clause rejects an unsafe field name.
"""

import pytest

from agrag.cypher.entities import (
    filter_clause,
    upsert_node_query,
    upsert_survivor_query,
    validate_identifier,
)


class TestValidateIdentifier:
    """validate_identifier rejects unsafe identifiers."""

    @pytest.mark.parametrize(
        "bad",
        ["", " ", "Person Node", "Person`x", "Person;DROP", "1Node", "Person.Node"],
    )
    def test_rejects_injection(self, bad: str) -> None:
        """A space, backtick, semicolon, leading digit, or dot is rejected."""
        with pytest.raises(ValueError):
            validate_identifier(bad)


class TestUpsertNodeQuery:
    """upsert_node_query validates its labels."""

    def test_validates_label(self) -> None:
        """An unsafe label raises before the query is built."""
        with pytest.raises(ValueError):
            upsert_node_query(["Bad Label"])

    def test_validates_every_label_in_a_compound_set(self) -> None:
        """An unsafe label anywhere in the set raises."""
        with pytest.raises(ValueError):
            upsert_node_query(["Chunk", "Bad Label"])

    def test_rejects_empty_labels(self) -> None:
        """An empty label set raises rather than building a labelless MERGE."""
        with pytest.raises(ValueError):
            upsert_node_query([])


class TestUpsertSurvivorQuery:
    """upsert_survivor_query validates its label."""

    def test_validates_label(self) -> None:
        """An unsafe label raises before the query is built."""
        with pytest.raises(ValueError):
            upsert_survivor_query("Bad Label")


class TestFilterClause:
    """filter_clause turns a flat-dict filter into a WHERE clause."""

    def test_rejects_bad_field(self) -> None:
        """A non-identifier field name raises."""
        with pytest.raises(ValueError):
            filter_clause({"bad field": 1})
