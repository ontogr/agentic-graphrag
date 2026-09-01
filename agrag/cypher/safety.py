"""Safety gate for generated Cypher queries."""

import re


_WRITE_KEYWORDS = frozenset({"CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP"})
# CALL is allowed only for these read-only procedures. Anything else,
# including a CALL subquery, is rejected because an arbitrary procedure
# call can perform writes (the vector queryNodes procedure is the one the
# project's own native vector search generates and uses).
_READ_ONLY_CALL_PROCEDURES = frozenset({"db.index.vector.queryNodes"})


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

    # CALL is permitted for allowlisted read-only procedures only. A
    # non-matching procedure or a bare CALL subquery is rejected: arbitrary
    # procedure calls can perform writes, and the LLM has no need of
    # subqueries.
    for match in re.finditer(r"\bCALL\b", stripped):
        remainder = stripped[match.end() :]
        proc_match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_.]*)", remainder)
        procedure = proc_match.group(1) if proc_match else ""
        if not procedure:
            raise UnsafeCypherError(
                f"Generated Cypher uses a CALL subquery: {query[:200]}"
            )
        if procedure not in _READ_ONLY_CALL_PROCEDURES:
            raise UnsafeCypherError(
                f"Generated Cypher calls disallowed procedure "
                f"'{procedure}': {query[:200]}"
            )
