"""Cypher builders for node writes and filters.

Leaf module: imports nothing from ``agrag.graphdb`` or other store packages, so
the dependency points one way (store -> cypher).
"""

import re
from collections.abc import Sequence
from typing import Any


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Every node this store writes carries this label, used only to MERGE onto a
# node by id independently of its other, mutable labels. MERGE-ing on the
# full requested label set instead would only match a node that already has
# every one of those labels, so adding a label to an existing same-id node
# would create a duplicate node (and violate any per-label uniqueness
# constraint) rather than update it.
NODE_IDENTITY_LABEL = "_AgragNode"


def validate_identifier(value: str) -> str:
    """Check that a label or relationship type is a safe Cypher identifier.

    Args:
        value: The label or relationship type to check.

    Returns:
        ``value`` unchanged, once validated.

    Raises:
        ValueError: ``value`` is not a safe identifier.
    """
    if not _IDENTIFIER.match(value):
        raise ValueError(f"{value!r} is not a valid Cypher identifier")
    return value


def is_safe_identifier(value: str) -> bool:
    """Report whether a label or relationship type is a safe Cypher identifier.

    A non-raising counterpart to ``validate_identifier``, for filtering a
    batch of names (for example ones read back from the database) rather
    than validating one name a caller must supply correctly.

    Args:
        value: The label or relationship type to check.

    Returns:
        ``True`` if ``value`` is a safe identifier.
    """
    return _IDENTIFIER.match(value) is not None


def upsert_node_query(labels: Sequence[str]) -> str:
    """Build the Cypher for an UNWIND-batched node upsert.

    MERGE identity is anchored to ``NODE_IDENTITY_LABEL``, not to ``labels``
    itself, so a node keeps resolving to the same id regardless of what
    labels it currently carries. ``labels`` is then applied additively with
    ``SET``, which is idempotent (a label the node already has is a no-op)
    and never removes a label a previous upsert of the same id set but this
    one omits: labels only ever accumulate. Every node in one call gets the
    same additive label set, since Cypher requires labels to be literal in
    the query text rather than a runtime parameter; nodes whose
    ``NodeRecord.labels`` differ need separate calls, one per distinct label
    set (see ``Neo4jGraphStore.upsert_nodes`` for how a mixed batch is
    grouped and split before reaching this builder).

    Identity is reasserted after applying properties, so a caller-supplied
    ``properties["id"]`` cannot overwrite the ``id`` used to ``MERGE`` and
    orphan the node from later upserts of the same record.

    Args:
        labels: The node's labels to add, in addition to the identity anchor.
            Must already be validated, and non-empty.

    Returns:
        A parameterized Cypher query expecting a ``$records`` list parameter.

    Raises:
        ValueError: ``labels`` is empty, or any label is not a safe
            identifier.
    """
    if not labels:
        raise ValueError("upsert_node_query requires at least one label")
    label_expr = ":".join(validate_identifier(label) for label in labels)
    return (
        f"UNWIND $records AS record "
        f"MERGE (n:{NODE_IDENTITY_LABEL} {{id: record.id}}) "
        f"SET n:{label_expr} "
        f"SET n += record.properties "
        f"SET n.id = record.id"
    )


def filter_clause(
    filters: dict[str, Any], node_var: str = "node"
) -> tuple[str, dict[str, Any]]:
    """Build a Cypher WHERE clause and parameters from a flat-dict filter.

    Args:
        filters: A flat-dict filter: a scalar value means exact match, a list
            value means any of, and all keys are AND-ed together.
        node_var: The Cypher variable bound to the node in the surrounding query.

    Returns:
        The ``WHERE`` clause text (beginning with ``WHERE`` when ``filters`` is
        non-empty, otherwise an empty string) and the parameter dict to pass
        with it.
    """
    if not filters:
        return "", {}
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for key, value in filters.items():
        field = validate_identifier(key)
        param = f"filter_{field}"
        if isinstance(value, list):
            clauses.append(f"{node_var}.{field} IN ${param}")
        else:
            clauses.append(f"{node_var}.{field} = ${param}")
        params[param] = value
    return "WHERE " + " AND ".join(clauses), params
