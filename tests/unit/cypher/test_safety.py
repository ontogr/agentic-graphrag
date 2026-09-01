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

    def test_rejects_lowercase_write_keyword(self) -> None:
        """Lowercase write keywords are not a bypass.

        Cypher keywords are case-insensitive; the pre-filter must
        catch ``delete`` written in any case so a model cannot
        sneak a write past it by lowering one letter.
        """
        with pytest.raises(UnsafeCypherError, match="DELETE"):
            reject_write_cypher("match (n) delete n")

    def test_rejects_mixed_case_write_keyword(self) -> None:
        """Mixed-case write keywords are not a bypass."""
        with pytest.raises(UnsafeCypherError, match="DELETE"):
            reject_write_cypher("MATCH (n) DeLeTe n")

    @pytest.mark.parametrize(
        "query",
        [
            "merge (n:Person {name: $x})",
            "create (n:Person {name: $x})",
            "match (n) set n.x = 1",
            "match (n) remove n.embedding",
            "drop index my_index",
        ],
    )
    def test_rejects_lowercase_keywords_foreach(self, query: str) -> None:
        """Every write keyword rejects in lowercase."""
        with pytest.raises(UnsafeCypherError):
            reject_write_cypher(query)

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
