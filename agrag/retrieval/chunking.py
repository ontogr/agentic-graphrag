"""Turns graph node values into Chunk models for retrieval."""

import logging
from typing import Any

from agrag.common.data_models.chunk import Chunk


logger = logging.getLogger(__name__)


def node_properties(node: Any) -> dict[str, Any]:
    """Return the properties of a graph node as a plain dict.

    Accepts a flat dict, a dict whose values sit under ``properties``, and a
    neo4j node. Any other value gives an empty dict, which fails Chunk
    validation with the missing fields named.

    Args:
        node: The node value from a graph row.

    Returns:
        A new dict of the node properties.
    """
    if isinstance(node, dict):
        nested = node.get("properties")
        if isinstance(nested, dict):
            return {**node, **nested}
        return dict(node)
    try:
        return dict(node)
    except (TypeError, ValueError):
        return {}


def parse_chunk_node(value: object) -> Chunk | None:
    """Build a Chunk from a node value, or return None when it is not a chunk.

    Args:
        value: The node value from a graph row.

    Returns:
        The parsed Chunk, or None when the value fails Chunk validation.
    """
    try:
        return Chunk.from_node(node_properties(value))
    except ValueError as exc:
        logger.debug("Skipping a node that is not a valid chunk: %s", exc)
        return None
