"""Safety gate for generated Cypher queries."""

import re

from agrag.common.data_models.candidate import CANDIDATE_EDGE_TYPES, CANDIDATE_LABEL
from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY


_WRITE_KEYWORDS = frozenset({"CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP"})
# These clauses read from, or switch to, somewhere the read transaction does
# not protect: LOAD CSV sends graph text to a URL under the store's
# credentials, USE targets another database, SHOW lists schema and users.
# Matching is by token, like the write keywords, so a property named ``use``
# is also rejected.
_DENIED_KEYWORDS = frozenset({"LOAD", "USE", "SHOW"})
# CALL is allowed only for these read-only procedures. Anything else,
# including a CALL subquery, is rejected because an arbitrary procedure
# call can perform writes (the vector queryNodes procedure is the one the
# project's own native vector search generates and uses).
_READ_ONLY_CALL_PROCEDURES = frozenset({"db.index.vector.queryNodes"})


class UnsafeCypherError(Exception):
    """Raised when a generated Cypher query contains a write clause."""


class MissingPendingGuardError(ValueError):
    """Raised when generated Cypher can return rows an in-flight job wrote."""


class MissingIdentityGuardError(ValueError):
    """Raised when generated Cypher can return a node outside the entity graph."""


# A node pattern such as ``(n:Person {name: ""})``. The lookbehind skips a
# function call like ``count(n)``. Group 1 is the variable; group 2 is labels.
_NODE_PATTERN = re.compile(
    r"(?<![\w)\]])\(\s*([A-Za-z_]\w*)?\s*((?::[^(){}\[\]]*)?)"
    r"(?:\{[^{}]*\})?\s*\)"
)
_RELATION_PATTERN = re.compile(r"-\s*\[([^\]]*)\]\s*-")
_ANONYMOUS_ARROW = re.compile(r"--")
_YIELD_PATTERN = re.compile(r"\bYIELD\s+([A-Za-z_]\w*)(?:\s*,\s*([A-Za-z_]\w*))?")
_PATH_NODE_GUARD = re.compile(
    rf"\bALL\s*\(\s*(\w+)\s+IN\s+nodes\s*\([^)]*\)\s+WHERE\s+\1\."
    rf"{PENDING_JOB_ID_PROPERTY}\s+IS\s+NULL",
    flags=re.IGNORECASE,
)
_PATH_RELATION_GUARD = re.compile(
    rf"\bALL\s*\(\s*(\w+)\s+IN\s+(?:relationships\s*\([^)]*\)|\w+)\s+WHERE\s+\1\."
    rf"{PENDING_JOB_ID_PROPERTY}\s+IS\s+NULL",
    flags=re.IGNORECASE,
)
_UNION = re.compile(r"\bUNION\b", flags=re.IGNORECASE)
_CLAUSE_TOKEN = re.compile(
    r"\b(OR|MATCH|WHERE|WITH|RETURN|UNWIND|ORDER|SKIP|LIMIT|CALL|YIELD)\b",
    flags=re.IGNORECASE,
)
_LABEL_NAME = r"[A-Za-z_]\w*"
_PLAIN_LABELS = re.compile(rf"(?:\s*:\s*{_LABEL_NAME})+\s*")
_LABEL_NAMES = re.compile(rf":\s*({_LABEL_NAME})")
_CANDIDATE_LABEL_WORD = re.compile(rf"\b{CANDIDATE_LABEL}\b")
# ``ALL(x IN nodes(path) WHERE x:Label)``. Group 2 is the path variable the
# guard covers, group 3 the required label.
_PATH_LABEL_GUARD = re.compile(
    rf"\bALL\s*\(\s*(\w+)\s+IN\s+nodes\s*\(\s*(\w+)\s*\)\s+WHERE\s+\1\s*:\s*"
    rf"({_LABEL_NAME})\b",
    flags=re.IGNORECASE,
)
# ``p = (`` or ``p = shortestPath(`` before a pattern, naming the path ``p``.
_PATH_VARIABLE = re.compile(
    rf"(?<![\w.])({_LABEL_NAME})\s*=\s*(?:(?:all)?shortestpath\s*)?\(",
    flags=re.IGNORECASE,
)
# A quantifier on a relationship or a parenthesised pattern, such as
# ``-[r]-{1,2}``, ``->{2}``, ``((a)-->(b)){1,3}`` or ``(a)-->(b)+``. The
# quantified form can repeat through nodes the other checks never see.
_QUANTIFIED_PATTERN = re.compile(r"[\])]\s*(?:[*+]|\{\s*\d)|[->]\s*\{\s*\d")
_WITH_CLAUSE = re.compile(r"\bWITH\b", flags=re.IGNORECASE)
_TYPED_PATH = re.compile(
    rf"\s*(?:\w+)?\s*:\s*({_LABEL_NAME}(?:\s*\|\s*:?\s*{_LABEL_NAME})*)\s*\*"
)
_SUBQUERY_SCOPE = re.compile(r"\bCALL\s*\([^()]*\)\s*\{", flags=re.IGNORECASE)
_NEGATION_BEFORE = re.compile(r"\bNOT\s*\(*\s*$", flags=re.IGNORECASE)
_PROJECTION_CLAUSE = re.compile(
    r"\b(MATCH|WHERE|WITH|RETURN|ORDER|UNWIND|CALL|YIELD)\b", flags=re.IGNORECASE
)


def _enclosing_span(text: str, position: int) -> tuple[int, int]:
    """Return the bounds of the parenthesis group around position.

    The start is -1 and the end is the text length when no group encloses it.
    """
    depth = 0
    start = position - 1
    while start >= 0:
        if text[start] == ")":
            depth += 1
        elif text[start] == "(":
            if depth == 0:
                break
            depth -= 1
        start -= 1
    depth = 0
    end = position
    while end < len(text):
        if text[end] == "(":
            depth += 1
        elif text[end] == ")":
            if depth == 0:
                break
            depth -= 1
        end += 1
    return start, end


def _level_has_or(text: str, start: int, end: int, position: int) -> bool:
    """Report whether an OR at this level shares a clause with position."""
    or_before = or_after = False
    depth = 0
    cursor = start + 1
    for token in _CLAUSE_TOKEN.finditer(text, start + 1, end):
        depth += text.count("(", cursor, token.start())
        depth -= text.count(")", cursor, token.start())
        cursor = token.start()
        if depth != 0:
            continue
        is_or = token.group(1).upper() == "OR"
        if token.start() < position:
            or_before = is_or
        elif is_or:
            or_after = True
        else:
            break
    return or_before or or_after


def _or_beside_guard(text: str, position: int) -> bool:
    """Report whether an OR in the same clause can bypass the guard at position.

    Checks the guard's own parenthesis level and each level around it. At each
    level, an OR between the nearest clause keywords before and after the guard
    means the guard is not combined with AND.
    """
    while True:
        start, end = _enclosing_span(text, position)
        if _level_has_or(text, start, end, position):
            return True
        if start < 0:
            return False
        position = start


def _guard_filters_rows(text: str, position: int) -> bool:
    """Report whether the guard at position can remove rows.

    A negated guard (``NOT n._pending_job_id IS NULL``) selects only pending
    rows. A guard in a ``RETURN`` or ``ORDER BY`` projection computes a value
    or sorts and removes nothing. Neither counts.
    """
    before = text[:position]
    if _NEGATION_BEFORE.search(before):
        return False
    clauses = list(_PROJECTION_CLAUSE.finditer(before))
    if not clauses:
        return True
    return clauses[-1].group(1).upper() not in {"RETURN", "ORDER"}


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

    LOAD, USE and SHOW are rejected too: they read from a URL, switch
    database or list schema, which a read transaction does not stop.

    Args:
        query: The Cypher text a BAML call produced.

    Raises:
        UnsafeCypherError: The query contains a write keyword, a LOAD,
            USE or SHOW clause, or a disallowed CALL, outside a string
            literal, comment, or backtick identifier.
    """
    stripped = strip_cypher_syntax(query)

    tokens = re.findall(r"\b[A-Za-z]+\b", stripped)
    for token in tokens:
        if token.upper() in _WRITE_KEYWORDS:
            raise UnsafeCypherError(
                f"Generated Cypher contains write keyword "
                f"'{token.upper()}': {query[:200]}"
            )
        if token.upper() in _DENIED_KEYWORDS:
            raise UnsafeCypherError(
                f"Generated Cypher contains disallowed keyword "
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


def require_pending_guard(query: str) -> None:
    """Raise unless every bound node and relationship excludes pending rows.

    A Cutover Job tags its uncommitted writes with ``_pending_job_id``.
    Generated Cypher reads the graph directly, so it must filter on that
    property itself: every named node and relationship variable needs
    ``alias._pending_job_id IS NULL``, and a variable-length path needs the
    same test over ``nodes(path)`` and ``relationships(path)``.

    This is a conservative text check, not a proof. It does not track which
    clause a guard sits in, so a guard in one WHERE clause satisfies a
    variable bound in another. It rejects a guard that shares a WHERE
    clause with an OR, because the OR can let pending rows through. It
    ignores a guard that is negated or sits in a RETURN projection,
    because neither removes pending rows. It rejects ``UNION``, because
    it cannot check each branch. It rejects unnamed variables, because
    they have no name to guard. A query that fails the check can be
    regenerated.

    Args:
        query: The Cypher text a BAML call produced.

    Raises:
        MissingPendingGuardError: A bound variable has no guard, or a
            node or relationship has no variable.
    """
    stripped = strip_cypher_syntax(query)
    if _UNION.search(stripped):
        raise MissingPendingGuardError(
            "Generated Cypher uses UNION, so each branch cannot be checked"
        )
    if _ANONYMOUS_ARROW.search(stripped):
        raise MissingPendingGuardError(
            "Generated Cypher has a relationship with no variable to filter"
        )
    aliases: set[str] = set()
    for match in _NODE_PATTERN.finditer(stripped):
        if match.group(1) is None:
            raise MissingPendingGuardError(
                "Generated Cypher has a node with no variable to filter"
            )
        aliases.add(match.group(1))
    variable_length = False
    for match in _RELATION_PATTERN.finditer(stripped):
        body = match.group(1)
        alias = re.match(r"\s*([A-Za-z_]\w*)", body)
        if alias is None:
            raise MissingPendingGuardError(
                "Generated Cypher has a relationship with no variable to filter"
            )
        if "*" in body:
            variable_length = True
        else:
            aliases.add(alias.group(1))
    for match in _YIELD_PATTERN.finditer(stripped):
        aliases.update(name for name in match.groups() if name and name != "score")
    for alias in sorted(aliases):
        guard = rf"\b{alias}\.{PENDING_JOB_ID_PROPERTY}\s+IS\s+NULL\b"
        if not any(
            _guard_filters_rows(stripped, match.start())
            and not _or_beside_guard(stripped, match.start())
            for match in re.finditer(guard, stripped, flags=re.IGNORECASE)
        ):
            raise MissingPendingGuardError(
                f"Generated Cypher does not require "
                f"{alias}.{PENDING_JOB_ID_PROPERTY} IS NULL"
            )
    if variable_length and not (
        _PATH_NODE_GUARD.search(stripped) and _PATH_RELATION_GUARD.search(stripped)
    ):
        raise MissingPendingGuardError(
            "Generated Cypher has a variable-length path without a pending guard "
            "on its nodes and relationships"
        )


def _names_other_label(labels: str) -> bool:
    """Report whether a node pattern requires a non-candidate label."""
    if not _PLAIN_LABELS.fullmatch(labels):
        return False
    return any(name != CANDIDATE_LABEL for name in _LABEL_NAMES.findall(labels))


def _has_label_test(text: str, alias: str) -> bool:
    """Report whether text positively requires ``alias`` to carry a label."""
    for match in re.finditer(
        rf"(NOT\s+)?\b{alias}\s*:\s*({_LABEL_NAME})\b", text, flags=re.IGNORECASE
    ):
        if match.group(1) or match.group(2) == CANDIDATE_LABEL:
            continue
        if _is_positive_where_filter(text, match.start()):
            return True
    return False


def _is_positive_where_filter(text: str, position: int) -> bool:
    """Exclude projections, negated predicates and optional OR branches."""
    clauses = list(_CLAUSE_TOKEN.finditer(text[:position]))
    if not clauses or clauses[-1].group(1).upper() != "WHERE":
        return False
    current = position
    while current >= 0:
        if re.search(r"\bNOT\s*\(*\s*$", text[:current], flags=re.IGNORECASE):
            return False
        current, _ = _enclosing_span(text, current)
    return not _or_beside_guard(text, position)


def _path_is_typed_away_from_candidates(relation_body: str) -> bool:
    """Report whether a variable-length relationship excludes candidate edges."""
    match = _TYPED_PATH.match(relation_body)
    if match is None:
        return False
    return not set(re.findall(_LABEL_NAME, match.group(1))) & CANDIDATE_EDGE_TYPES


def find_candidate_exposure(query: str) -> str | None:
    """Explain how a query could return a candidate, or return None.

    The check fails closed. A query is safe only when every node pattern has
    a non-candidate label or a positive label test on its own variable, and
    every variable-length path is typed away from candidate edges or guarded
    through its own path variable. A UNION, a quantified pattern, or a WITH
    that precedes a variable-length path is rejected because this text check
    cannot follow it.

    Args:
        query: The Cypher text to inspect.

    Returns:
        A short explanation when the query can expose a candidate.
    """
    stripped = strip_cypher_syntax(query)
    if _CANDIDATE_LABEL_WORD.search(stripped):
        return f"the query names the {CANDIDATE_LABEL} label"
    if _UNION.search(stripped):
        return "a UNION branch cannot be checked on its own"
    if _QUANTIFIED_PATTERN.search(stripped):
        return "a quantified pattern can repeat through unlabelled nodes"
    text = _SUBQUERY_SCOPE.sub("CALL {", stripped)
    patterns = [
        (match.group(1), match.group(2) or "") for match in _NODE_PATTERN.finditer(text)
    ]
    outside = _blank_node_patterns(text)
    # WITH can rebind a name, so a label test elsewhere in the query may
    # describe a different node. Without WITH, tests are trusted.
    has_with = _WITH_CLAUSE.search(text) is not None
    if has_with:
        outside = ""
    labelled = {
        alias for alias, labels in patterns if alias and _names_other_label(labels)
    }
    reason = _node_exposure_reason(patterns, outside)
    if reason is not None:
        return reason
    return _exposed_yield_reason(text, outside, labelled) or _exposed_path_reason(
        text, has_with=has_with
    )


def _blank_node_patterns(text: str) -> str:
    """Return the text with every node pattern blanked, keeping its layout."""
    outside = text
    for match in reversed(list(_NODE_PATTERN.finditer(text))):
        outside = (
            outside[: match.start()] + " " * len(match.group()) + outside[match.end() :]
        )
    return outside


def _exposed_yield_reason(text: str, outside: str, labelled: set[str]) -> str | None:
    """Return the reason a YIELD variable can bind a candidate, if one can."""
    for match in _YIELD_PATTERN.finditer(text):
        for alias in match.groups():
            if not alias or alias == "score" or alias in labelled:
                continue
            if not _has_label_test(outside, alias):
                return f"{alias} has no label, so it can match a {CANDIDATE_LABEL}"
    return None


def _path_variable_before(text: str, position: int) -> str | None:
    """Return the path variable of the pattern that contains ``position``.

    The variable must be the nearest ``name =`` before the relationship, with
    no clause keyword or comma between them. Otherwise the relationship could
    belong to a different pattern than the one the name refers to.
    """
    found = None
    for match in _PATH_VARIABLE.finditer(text, 0, position):
        found = match
    if found is None:
        return None
    between = text[found.end() : position]
    if _CLAUSE_TOKEN.search(between) or "," in between:
        return None
    return found.group(1)


def _exposed_path_reason(text: str, *, has_with: bool) -> str | None:
    """Return the reason a variable-length path can cross a candidate."""
    for match in _RELATION_PATTERN.finditer(text):
        body = match.group(1)
        if "*" not in body or _path_is_typed_away_from_candidates(body):
            continue
        if has_with:
            return "a variable-length path follows WITH, so its guard is not trusted"
        path = _path_variable_before(text, match.start())
        if path is None:
            return "a variable-length path has no path variable to guard"
        if not any(
            guard.group(3) != CANDIDATE_LABEL
            and guard.group(2) == path
            and _is_positive_where_filter(text, guard.start())
            for guard in _PATH_LABEL_GUARD.finditer(text)
        ):
            return "a variable-length path can pass through a node with no label"
    return None


def _node_exposure_reason(
    patterns: list[tuple[str | None, str]], outside: str
) -> str | None:
    """Return the reason a node pattern can bind a candidate, if one can.

    Each pattern is checked on its own. A label on another pattern that uses
    the same variable does not protect this one, because a later pattern can
    rebind the name.
    """
    for alias, labels in patterns:
        if _names_other_label(labels):
            continue
        if alias is None:
            return "a node has neither a variable nor a label"
        if not _has_label_test(outside, alias):
            return f"{alias} has no label, so it can match a {CANDIDATE_LABEL}"
    return None


def require_identity_guard(query: str) -> None:
    """Raise unless no node in the query can be a candidate.

    Args:
        query: The Cypher text to inspect.

    Raises:
        MissingIdentityGuardError: A node or variable-length path can expose
            a candidate.
    """
    reason = find_candidate_exposure(query)
    if reason is not None:
        raise MissingIdentityGuardError(f"Generated Cypher is not safe: {reason}")
