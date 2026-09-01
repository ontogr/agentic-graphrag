"""Tests for the Cypher write-clause safety gate."""

import pytest

from agrag.cypher.safety import UnsafeCypherError, reject_write_cypher


class TestRejectWriteCypher:
    """reject_write_cypher raises on write keywords."""

    def test_rejects_delete(self) -> None:
        """A query containing DELETE is rejected."""
        with pytest.raises(UnsafeCypherError, match="DELETE"):
            reject_write_cypher("MATCH (n) WHERE n.id = $id DELETE n")

    def test_rejects_create(self) -> None:
        """A query containing CREATE is rejected."""
        with pytest.raises(UnsafeCypherError, match="CREATE"):
            reject_write_cypher("CREATE (n:Person {name: 'test'})")

    def test_rejects_merge(self) -> None:
        """A query containing MERGE is rejected."""
        with pytest.raises(UnsafeCypherError, match="MERGE"):
            reject_write_cypher("MERGE (n:Person {name: 'test'})")

    def test_rejects_set(self) -> None:
        """A query containing SET is rejected."""
        with pytest.raises(UnsafeCypherError, match="SET"):
            reject_write_cypher("MATCH (n) SET n.name = 'updated'")

    def test_rejects_remove(self) -> None:
        """A query containing REMOVE is rejected."""
        with pytest.raises(UnsafeCypherError, match="REMOVE"):
            reject_write_cypher("MATCH (n) REMOVE n.embedding")

    def test_rejects_drop(self) -> None:
        """A query containing DROP is rejected."""
        with pytest.raises(UnsafeCypherError, match="DROP"):
            reject_write_cypher("DROP INDEX my_index")

    def test_rejects_write_inside_read_shape(self) -> None:
        """A DELETE inside a valid-looking read query is rejected."""
        with pytest.raises(UnsafeCypherError):
            reject_write_cypher(
                "MATCH (n:Person) WHERE n.name = $name DELETE n RETURN n"
            )

    def test_accepts_pure_match_return(self) -> None:
        """A pure MATCH...RETURN query is accepted."""
        reject_write_cypher("MATCH (n:Person) WHERE n.name = $name RETURN n")

    def test_accepts_read_only_vector_call(self) -> None:
        """CALL db.index.vector.queryNodes is accepted (read Cypher)."""
        reject_write_cypher(
            "CALL db.index.vector.queryNodes("
            "'my_index', 10, $vector) "
            "YIELD node, score "
            "RETURN node, score"
        )

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

    def test_ignores_keywords_inside_string_literals(self) -> None:
        """DELETE inside a string literal does not trigger rejection."""
        reject_write_cypher("RETURN 'This query will DELETE nothing'")

    def test_ignores_keywords_inside_single_quoted_strings(self) -> None:
        """CREATE inside a single-quoted string is safe."""
        reject_write_cypher("RETURN 'Do not CREATE duplicates'")
