"""Safety gate for generated Cypher queries."""

import re


_WRITE_KEYWORDS = frozenset({"CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP"})
_CALL_KEYWORDS = frozenset({"CALL"})


class UnsafeCypherError(Exception):
    """Raised when a generated Cypher query contains a write clause."""


def reject_write_cypher(query: str) -> None:
    """Raise fast on an obvious write clause, ahead of EXPLAIN.

    This is a cheap pre-filter, not the safety boundary:
    execute_read's read transaction is what actually prevents a
    write from running, since Neo4j itself rejects one there. This
    check exists so a write-shaped generated query fails immediately
    instead of spending an EXPLAIN round trip first.

    Args:
        query: The Cypher text a BAML call produced.

    Raises:
        UnsafeCypherError: The query contains a write keyword
            outside a string literal.
    """
    # Strip string literals to avoid false positives on keywords
    # inside quoted text.
    stripped = re.sub(r"'[^']*'", "", query)
    stripped = re.sub(r'"[^"]*"', "", stripped)

    tokens = re.findall(r"\b[A-Z]+\b", stripped)
    for token in tokens:
        if token in _WRITE_KEYWORDS:
            raise UnsafeCypherError(
                f"Generated Cypher contains write keyword '{token}': {query[:200]}"
            )
        if token in _CALL_KEYWORDS:
            raise UnsafeCypherError(
                f"Generated Cypher contains CALL keyword: {query[:200]}"
            )
