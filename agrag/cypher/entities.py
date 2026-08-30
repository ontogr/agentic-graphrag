"""Cypher builders for node writes and filters.

Leaf module: imports nothing from ``agrag.graphdb`` or other store packages, so
the dependency points one way (store -> cypher).
"""

import re
from collections.abc import Sequence
from typing import Any


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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


def upsert_node_query(labels: Sequence[str]) -> str:
    """Build the Cypher for an UNWIND-batched node upsert.

    Every node in one call gets the same label set, since Cypher requires
    labels to be literal in the query text rather than a runtime parameter.
    Nodes whose ``NodeRecord.labels`` differ need separate calls, one per
    distinct label set: see ``Neo4jGraphStore.upsert_nodes`` for how a mixed
    batch is grouped and split before reaching this builder.

    Identity is reasserted after applying properties, so a caller-supplied
    ``properties["id"]`` cannot overwrite the ``id`` used to ``MERGE`` and
    orphan the node from later upserts of the same record.

    Args:
        labels: The node's labels. Must already be validated, and non-empty.

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
        f"MERGE (n:{label_expr} {{id: record.id}}) "
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
