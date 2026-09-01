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


def strip_cypher_syntax(query: str) -> str:
    """Blank string literals, comments, and backtick identifiers.

    Replaces the contents of string literals, ``//`` and ``/* */``
    comments, and backtick-quoted identifiers with spaces, keeping every
    other character intact so token boundaries survive. Scans char by
    char and honors backslash and doubled-quote escapes, so an escaped
    quote inside a literal cannot close the scan early and let a real
    keyword after it hide inside a bogus "string".

    Args:
        query: The Cypher text to scrub.

    Returns:
        The query with literal, comment, and identifier content blanked,
        layout otherwise unchanged.
    """
    out: list[str] = []
    i = 0
    while i < len(query):
        ch = query[i]
        if ch == "/" and i + 1 < len(query) and query[i + 1] == "/":
            while i < len(query) and query[i] != "\n":
                out.append(" ")
                i += 1
        elif ch == "/" and i + 1 < len(query) and query[i + 1] == "*":
            out.append(" ")
            out.append(" ")
            i += 2
            while i < len(query):
                if query[i] == "*" and i + 1 < len(query) and query[i + 1] == "/":
                    out.append(" ")
                    out.append(" ")
                    i += 2
                    break
                out.append(" ")
                i += 1
        elif ch in ("'", '"', "`"):
            i = _blank_quoted(out, query, i)
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _blank_quoted(out: list[str], query: str, start: int) -> int:
    """Blank the quoted region starting at ``start``; return the next index.

    Treats a backslash-escaped or doubled quote as content rather than
    the terminator, so the scanner cannot desync on escaped quotes.
    """
    out.append(" ")
    i = start + 1
    while i < len(query):
        if query[i] == "\\":
            out.append(" ")
            if i + 1 < len(query):
                out.append(" ")
                i += 1
            i += 1
        elif query[i] == query[start]:
            if i + 1 < len(query) and query[i + 1] == query[start]:
                out.append(" ")
                out.append(" ")
                i += 2
            else:
                out.append(" ")
                return i + 1
        else:
            out.append(" ")
            i += 1
    return i


def reject_write_cypher(query: str) -> None:
    """Raise fast on an obvious write clause, ahead of EXPLAIN.

    This is a cheap pre-filter, not the safety boundary:
    execute_read's read transaction is what actually prevents a
    write from running, since Neo4j itself rejects one there. This
    check exists so a write-shaped generated query fails immediately
    instead of spending an EXPLAIN round trip first.

    Keywords are matched case-insensitively, and only outside string
    literals, comments, and backtick identifiers, so a lowercase
    ``delete`` or a quote inside a comment cannot desync the scan.
    The check is conservative: a write keyword used as a property
    name (e.g. ``RETURN n.set``) is also rejected, acceptable for a
    pre-filter that guards model-generated text.

    Args:
        query: The Cypher text a BAML call produced.

    Raises:
        UnsafeCypherError: The query contains a write keyword outside
            a string literal, comment, or backtick identifier.
    """
    stripped = strip_cypher_syntax(query)

    tokens = re.findall(r"\b[A-Za-z]+\b", stripped)
    for token in tokens:
        if token.upper() in _WRITE_KEYWORDS:
            raise UnsafeCypherError(
                f"Generated Cypher contains write keyword "
                f"'{token.upper()}': {query[:200]}"
            )

    # CALL is permitted for allowlisted read-only procedures only. A
    # non-matching procedure or a bare CALL subquery is rejected: arbitrary
    # procedure calls can perform writes, and the LLM has no need of
    # subqueries. CALL is matched case-insensitively, like Cypher keywords.
    for match in re.finditer(r"\bCALL\b", stripped, flags=re.IGNORECASE):
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
