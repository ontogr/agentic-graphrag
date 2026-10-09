"""Shared chunk-node parsing for retrieval."""

import json
import logging
from typing import Any, Literal
from uuid import UUID

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.provenance import (
    PageProvenance,
    TextProvenance,
)


logger = logging.getLogger(__name__)


def _prop(node: object, name: str, default: object = None) -> object:
    if isinstance(node, dict):
        if name in node:
            return node[name]
        nested = node.get("properties")
        if isinstance(nested, dict) and name in nested:
            return nested[name]
        return default
    getter = getattr(node, "get", None)
    if getter is None:
        return default
    try:
        value = getter(name)
    except Exception:
        return default
    return value if value is not None else default


def _node_id(node: object) -> object | None:
    if isinstance(node, dict):
        top = node.get("id")
        if top is not None:
            return top
        nested = node.get("properties")
        if isinstance(nested, dict):
            return nested.get("id")
        return None
    getter = getattr(node, "get", None)
    if getter is None:
        return None
    try:
        return getter("id")
    except Exception:
        return None


def _provenance_data(raw: object) -> dict[str, Any] | None:
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None
    if isinstance(raw, dict):
        return raw
    return None


def _content_kind(raw: object) -> Literal["text", "table"]:
    return "table" if raw == "table" else "text"


def _chunk_index(raw: object) -> int:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        try:
            return int(raw)
        except ValueError:
            return 0
    return 0


def _heading_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [h for h in raw if isinstance(h, str)]


def _section_ids(raw: object) -> list[UUID]:
    if not isinstance(raw, list):
        return []
    ids: list[UUID] = []
    for item in raw:
        try:
            ids.append(UUID(str(item)))
        except (TypeError, ValueError, AttributeError):
            continue
    return ids


def _uuid_or_none(raw: object) -> UUID | None:
    if raw is None:
        return None
    try:
        return UUID(str(raw))
    except (TypeError, ValueError, AttributeError):
        return None


def parse_chunk_node(value: object) -> Chunk | None:
    """Build a Chunk from a chunk-shaped row value, or None.

    Accepts a plain dict, a dict carrying ``properties``, or a neo4j
    Node-like object. ``section_ids`` parses per item, so stored data is kept
    whenever its id, document id, and provenance are valid.

    Args:
        value: The chunk node value from a graph row.

    Returns:
        The parsed Chunk, or None when the value lacks an id, a document id,
            or valid provenance, or is a table or figure node.
    """
    try:
        chunk_id = _uuid_or_none(_node_id(value))
        if chunk_id is None:
            return None

        prov_data = _provenance_data(_prop(value, "provenance"))
        if prov_data is None or _prop(value, "section_key") is not None:
            return None
        try:
            provenance = (
                PageProvenance(**prov_data)
                if prov_data.get("kind") == "page"
                else TextProvenance(**prov_data)
            )
        except (ValueError, TypeError) as exc:
            logger.debug("Skipping node %s: bad provenance: %s", chunk_id, exc)
            return None

        document_id = _uuid_or_none(_prop(value, "document_id"))
        if document_id is None:
            return None

        text_raw = _prop(value, "text", "")
        if text_raw is None:
            text = ""
        elif isinstance(text_raw, str):
            text = text_raw
        else:
            text = str(text_raw)

        chunker_raw = _prop(value, "chunker")
        chunker = chunker_raw if isinstance(chunker_raw, str) else None
        hash_raw = _prop(value, "chunker_hash")
        chunker_hash = hash_raw if isinstance(hash_raw, str) else None

        chunk = Chunk(
            id=chunk_id,
            document_id=document_id,
            index=_chunk_index(_prop(value, "index", 0)),
            text=text,
            provenance=provenance,
            heading_path=_heading_list(_prop(value, "heading_path", [])),
            content_kind=_content_kind(_prop(value, "content_kind", "text")),
            chunker=chunker,
            chunker_hash=chunker_hash,
            section_ids=_section_ids(_prop(value, "section_ids", [])),
        )
        embedding = _prop(value, "embedding")
        if isinstance(embedding, list):
            chunk.embedding = list(embedding)
        return chunk
    except (ValueError, TypeError) as exc:
        logger.debug("Skipping a node that is not a valid chunk: %s", exc)
        return None
