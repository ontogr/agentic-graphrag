"""Tests for the scoped-subquery translation the Neo4j store applies."""

import pytest

from agrag.graphdb.neo4j import scoped_subqueries


class TestScopedSubqueries:
    """Importing subqueries become scoped subqueries and nothing else changes."""

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            (
                "MATCH (a) CALL { WITH a MATCH (a)-->(b) RETURN count(b) AS n } "
                "RETURN n",
                "MATCH (a) CALL (a) { MATCH (a)-->(b) RETURN count(b) AS n } RETURN n",
            ),
            (
                "UNWIND $ids AS id CALL { WITH id, extra UNWIND id AS x RETURN x }",
                "UNWIND $ids AS id CALL (id, extra) { UNWIND id AS x RETURN x }",
            ),
            ("CALL { RETURN 1 AS x }", "CALL { RETURN 1 AS x }"),
            ("CALL { WITH a\nMATCH (a) RETURN a }", "CALL (a) {\nMATCH (a) RETURN a }"),
        ],
    )
    def test_rewrites_only_importing_subqueries(
        self, query: str, expected: str
    ) -> None:
        """A subquery that imports plain variables is scoped; others are kept."""
        assert scoped_subqueries(query) == expected
