"""Turns graph node values into Chunk models for retrieval."""

import logging
from collections.abc import Mapping

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.graph_rows import node_properties


logger = logging.getLogger(__name__)

# Fields that only a stored Chunk node carries among the node types a
# retriever reads. Used when a row gives no labels.
_CHUNK_ONLY_FIELDS = frozenset({"document_id", "provenance"})


def is_chunk_node(value: object) -> bool:
    """Tell whether a node value is a stored Chunk node.

    A driver node is judged by its labels. A plain property dict carries no
    labels, so it is judged by the fields only a Chunk node holds.

    Args:
        value: The node value from a graph row.

    Returns:
        True when the value is labelled ``Chunk``, or is a property dict
        with the chunk-only fields. False for any other value.
    """
    labels = getattr(value, "labels", None)
    if labels is not None:
        return CHUNK_LABEL in labels
    if not isinstance(value, Mapping):
        return False
    return _CHUNK_ONLY_FIELDS.issubset(node_properties(value))


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
