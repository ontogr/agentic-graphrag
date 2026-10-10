"""Tests for reject_write_cypher in agrag.cypher.safety.

Covers rejecting a write keyword anywhere in a query, including inside a
subquery CALL, in any letter case; rejecting a CALL to a procedure outside
the read-only allowlist. A cluster of adversarial-string tests
verifies the pre-filter's string/comment/backtick scanning is not
desynced by an escaped quote, a `//` or `/* */` comment, or a backtick
identifier placed between a keyword and a real write clause, and that a
write keyword used as a property name is still conservatively rejected.
"""

import pytest

from agrag.cypher.safety import (
    MissingPendingGuardError,
    UnsafeCypherError,
    reject_write_cypher,
    require_pending_guard,
)


class TestRejectWriteCypher:
    """reject_write_cypher raises on write keywords."""

    def test_rejects_unknown_procedure_call(self) -> None:
        """A CALL to a procedure outside the read-only allowlist is rejected."""
        with pytest.raises(UnsafeCypherError, match="disallowed procedure"):
            reject_write_cypher(
                "CALL apoc.export.csv.all('out.csv', {}) YIELD file RETURN file"
            )

    def test_rejects_call_in_subquery(self) -> None:
        """CALL inside a subquery is rejected."""
        with pytest.raises(UnsafeCypherError, match="CALL"):
            reject_write_cypher("MATCH (n) CALL { WITH n RETURN n } RETURN n")

    def test_rejects_lowercase_write_keyword(self) -> None:
        """Lowercase write keywords are not a bypass.

        Cypher keywords are case-insensitive; the pre-filter must
        catch ``delete`` written in any case so a model cannot
        sneak a write past it by lowering one letter.
        """
        with pytest.raises(UnsafeCypherError, match="DELETE"):
            reject_write_cypher("match (n) delete n")

    def test_escaped_quote_inside_literal_does_not_desync(self) -> None:
        r"""An escaped quote inside a literal does not leak a real DELETE.

        A literal like ``"b\" c "`` must not open a span that
        swallows the rest of the query, hiding a real write after it.
        """
        with pytest.raises(UnsafeCypherError, match="DELETE"):
            reject_write_cypher('RETURN "b\\" c " MATCH (n) DELETE n AND x = "y"')

    def test_keyword_inside_line_comment_does_not_trigger(self) -> None:
        """A write keyword in a ``//`` comment is correctly inert."""
        reject_write_cypher("MATCH (n) RETURN n // keep DELETE out")

    def test_keyword_inside_block_comment_does_not_trigger(self) -> None:
        """A write keyword in a ``/* */`` comment is correctly inert."""
        reject_write_cypher("MATCH (n) /* intent: DELETE */ RETURN n")

    def test_rejects_backtick_identifier_does_not_hide_write(self) -> None:
        """A backtick identifier between the keyword and the write is stripped.

        A backtick-delimited identifier in Cypher can contain quotes
        and other characters, so a naive quote-strip can desync. The
        scanner blanks backtick content first, so the write that
        follows is still caught.
        """
        with pytest.raises(UnsafeCypherError, match="DELETE"):
            reject_write_cypher("MATCH (n) RETURN n.`weird` DELETE n")

    def test_keyword_used_as_property_name_is_rejected(self) -> None:
        """Conservative: a write keyword as a property name is still rejected.

        The pre-filter is intentionally conservative because a model
        could have meant either a property access or a clause
        keyword; rejecting is the safe side for a pre-filter that
        guards model-generated text.
        """
        with pytest.raises(UnsafeCypherError, match="SET"):
            reject_write_cypher("MATCH (n) RETURN n.set")

    def test_call_keyword_is_case_insensitive(self) -> None:
        """Lowercase ``call`` is treated as a procedure call too."""
        reject_write_cypher(
            "call db.index.vector.queryNodes('idx', 10, $v) YIELD node RETURN node"
        )


_NODE = "n._pending_job_id IS NULL"


class TestRequirePendingGuard:
    """require_pending_guard demands a pending filter on every bound variable."""

    @pytest.mark.parametrize(
        "query",
        [
            f"MATCH (n:Person) WHERE {_NODE} RETURN count(n)",
            "MATCH (a:Person)-[r:KNOWS]->(b:Person) "
            "WHERE a._pending_job_id IS NULL AND b._pending_job_id IS NULL "
            "AND r._pending_job_id IS NULL RETURN a.name",
            "MATCH p = (a:Person)-[r:KNOWS*1..3]-(b) "
            "WHERE a._pending_job_id IS NULL AND b._pending_job_id IS NULL "
            "AND ALL(x IN nodes(p) WHERE x._pending_job_id IS NULL) "
            "AND ALL(y IN r WHERE y._pending_job_id IS NULL) RETURN b",
            "CALL db.index.vector.queryNodes('idx', 3, $v) YIELD node, score "
            "WHERE node._pending_job_id IS NULL RETURN node",
            "MATCH (n:Person) WHERE n._pending_job_id is null RETURN n",
            f"MATCH (n:Person) WHERE {_NODE} AND (n.a = 1 OR n.b = 2) RETURN n",
            f"MATCH (n:Person) WHERE (n.a = 1 OR n.b = 2) AND {_NODE} RETURN n",
            f"MATCH (n:Person) WHERE n.a = 1 OR n.b = 2 WITH n WHERE {_NODE} RETURN n",
            f"MATCH (n:Person) WHERE {_NODE} RETURN n ORDER BY n.name",
        ],
    )
    def test_accepts_guarded_queries(self, query: str) -> None:
        """A query that filters every variable passes."""
        require_pending_guard(query)

    @pytest.mark.parametrize(
        "query",
        [
            "MATCH (n:Person) RETURN n",
            f"MATCH (n:Person)-[:KNOWS]->(m) WHERE {_NODE} RETURN m",
            "MATCH ()-[r]->(m) WHERE m._pending_job_id IS NULL RETURN m",
            "MATCH (a)-->(b) WHERE a._pending_job_id IS NULL "
            "AND b._pending_job_id IS NULL RETURN b",
            "MATCH (a)-[r*1..2]-(b) WHERE a._pending_job_id IS NULL "
            "AND b._pending_job_id IS NULL RETURN b",
            "CALL db.index.vector.queryNodes('idx', 3, $v) YIELD node, score "
            "RETURN node",
            "MATCH (n:Person) WHERE n.note = 'n._pending_job_id IS NULL' RETURN n",
            f"MATCH (n:Person) WHERE {_NODE} OR true RETURN n",
            f"MATCH (n:Person) WHERE true OR {_NODE} RETURN n",
            f"MATCH (n:Person) WHERE n.a = 1 OR n.b = 2 AND {_NODE} RETURN n",
            f"MATCH (n:Person) WHERE ({_NODE}) OR n.a = 1 RETURN n",
            f"MATCH (n:Person) WHERE ({_NODE} AND n.a = 1) OR n.b = 2 RETURN n",
            f"MATCH (n:Person) WHERE {_NODE} RETURN n UNION MATCH (m:Person) RETURN m",
        ],
    )
    def test_rejects_queries_that_can_return_pending_rows(self, query: str) -> None:
        """A missing, unnamed or only-quoted guard is rejected."""
        with pytest.raises(MissingPendingGuardError):
            require_pending_guard(query)
