"""Read nodes out of the rows a GraphStore read returns."""

from typing import Any


def row_node(row: Any) -> Any:
    """Return the node a result row holds under ``n``, or the row itself.

    Args:
        row: One row of a read. Queries that return a node name it ``n``.
            A row that is already the node is returned unchanged.

    Returns:
        The node value.
    """
    return row["n"] if isinstance(row, dict) and "n" in row else row


def node_properties(node: Any) -> dict[str, Any]:
    """Return the properties of a graph node as a new dict.

    Accepts a flat dict, a dict that holds its values under ``properties``, and
    a neo4j node or other value that ``dict()`` can read. The nested
    ``properties`` values win over top-level keys of the same name.

    Args:
        node: The node value from a graph row.

    Returns:
        A new dict of the node properties. A value that ``dict()`` cannot read
        gives an empty dict, so the caller's validation names the missing
        fields.
    """
    if isinstance(node, dict):
        nested = node.get("properties")
        if isinstance(nested, dict):
            flat = {key: value for key, value in node.items() if key != "properties"}
            return {**flat, **nested}
        return dict(node)
    try:
        return dict(node)
    except (TypeError, ValueError):
        return {}
