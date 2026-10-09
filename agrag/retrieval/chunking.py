"""Turns graph node values into Chunk models for retrieval."""

import logging

from agrag.common.data_models.chunk import Chunk
from agrag.common.graph_rows import node_properties


logger = logging.getLogger(__name__)


def parse_chunk_node(value: object) -> Chunk | None:
    """Build a Chunk from a node value, or return None when it is not a chunk.

    Args:
        value: The node value from a graph row.

    Returns:
        The parsed Chunk, or None when the value fails Chunk validation.
    """
    properties = node_properties(value)
    if not properties:
        return None
    try:
        return Chunk.from_node(properties)
    except ValueError as exc:
        logger.warning(
            "Skipping chunk %s: it failed validation: %s",
            properties.get("id"),
            exc,
        )
        return None
