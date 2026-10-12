"""Identity guard checks for generated Cypher shapes the text check must handle.

Pure text checks with no database. Each rejected query names the construct
the guard must catch, and each accepted query shows the label test that
keeps candidates out.
"""

import pytest

from agrag.cypher.safety import (
    MissingIdentityGuardError,
    find_candidate_exposure,
    require_identity_guard,
)


@pytest.mark.parametrize(
    ("query", "reason"),
    [
        (
            "MATCH (n) WHERE NOT (n:Person AND (n.age > 1)) RETURN n",
            "n has no label, so it can match a Candidate",
        ),
        (
            "MATCH ()-[r:KNOWS]->(m:Person) RETURN m",
            "a node has neither a variable nor a label",
        ),
        (
            "MATCH p = (a:Person), (b:Person)-[*1..2]-(c:Person) RETURN p",
            "a variable-length path has no path variable to guard",
        ),
        (
            "CALL db.index.vector.queryNodes('idx', 3, $v) YIELD node, score "
            "RETURN node",
            "node has no label, so it can match a Candidate",
        ),
    ],
)
def test_rejects_query_shapes_that_can_expose_a_candidate(
    query: str, reason: str
) -> None:
    """Each unguarded construct is named in the rejection."""
    assert find_candidate_exposure(query) == reason
    with pytest.raises(MissingIdentityGuardError) as excinfo:
        require_identity_guard(query)
    assert str(excinfo.value) == f"Generated Cypher is not safe: {reason}"


@pytest.mark.parametrize(
    "query",
    [
        "MATCH (n) WHERE (n:Person AND (n.age > 1)) RETURN n",
        "CALL db.index.vector.queryNodes('idx', 3, $v) YIELD node, score "
        "WHERE node:Person RETURN node",
    ],
)
def test_accepts_positive_label_tests_in_a_where_clause(query: str) -> None:
    """A positive label test on the bound variable keeps candidates out."""
    assert find_candidate_exposure(query) is None
    require_identity_guard(query)
