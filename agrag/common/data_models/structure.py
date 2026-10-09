"""Stable keys, node ids, reading order and ancestry for the sections of a Document."""

import json
from uuid import NAMESPACE_OID, UUID, uuid5

from agrag.common.data_models.document import (
    Document,
    DocumentSection,
    UnitKind,
)


SECTION_LABEL = "Section"
TABLE_LABEL = "Table"
FIGURE_LABEL = "Figure"
SOURCE_LABEL = "Source"
HAS_CHILD = "HAS_CHILD"
HAS_DOCUMENT = "HAS_DOCUMENT"

_PATH_SEPARATOR = "\x1f"


def _uuid(*parts: object) -> UUID:
    return uuid5(NAMESPACE_OID, json.dumps([str(part) for part in parts]))


def version_id(document: Document) -> str:
    """Return the id of one version of a document, as ``PART_OF`` edges use it.

    Args:
        document: The document.

    Returns:
        The id, which changes when the content hash changes.
    """
    return str(Document.id_for(content_hash=document.content_hash))


def section_keys(document: Document) -> list[UUID]:
    """Return one stable key for each section.

    A key stays the same across versions while the heading path of the section and
    its place among sections with the same path stay the same.

    Args:
        document: The document.

    Returns:
        The keys, in the order of ``document.sections``.
    """
    paths: list[tuple[str, ...]] = []
    seen: dict[tuple[str, ...], int] = {}
    keys: list[UUID] = []
    for section in document.sections:
        parent = paths[section.parent] if section.parent is not None else ()
        path = (*parent, section.heading)
        paths.append(path)
        ordinal = seen.get(path, 0)
        seen[path] = ordinal + 1
        keys.append(
            _uuid(
                "Section",
                document.resolved_document_key,
                _PATH_SEPARATOR.join(path),
                ordinal,
            )
        )
    return keys


def unit_keys(document: Document, keys: list[UUID]) -> dict[tuple[int, int], UUID]:
    """Return a stable key for each table and figure.

    Args:
        document: The document.
        keys: The section keys from ``section_keys``.

    Returns:
        The keys, by section index and unit index.
    """
    found: dict[tuple[int, int], UUID] = {}
    for i, section in enumerate(document.sections):
        counts: dict[UnitKind, int] = {}
        for j, unit in enumerate(section.units):
            if unit.kind in (UnitKind.TABLE, UnitKind.FIGURE):
                ordinal = counts.get(unit.kind, 0)
                counts[unit.kind] = ordinal + 1
                found[i, j] = _uuid(unit.kind.value, keys[i], ordinal)
    return found


def node_id(key: UUID, version: str) -> UUID:
    """Return the id of the node that holds ``key`` in one document version."""
    return _uuid("Version", key, version)


def chunk_id(document_id: UUID, version: str, chunker_hash: str, index: int) -> UUID:
    """Return the id of a chunk.

    Args:
        document_id: The id of the Document node.
        version: The document version from ``version_id``.
        chunker_hash: The fingerprint of the chunker settings.
        index: The position of the chunk in the document.

    Returns:
        The id. It changes with the version and with the chunker settings.
    """
    return _uuid("Chunk", document_id, version, chunker_hash, index)


def source_node_id(uri: str) -> UUID:
    """Return the id of the Source node for a file."""
    return _uuid("Source", uri)


def reading_positions(document: Document) -> tuple[list[int], list[list[int]]]:
    """Number every heading and unit of a document in reading order.

    Args:
        document: The document.

    Returns:
        The position of each section heading, and the position of each unit.
    """
    position = 0
    heading_positions: list[int] = []
    unit_positions: list[list[int]] = []
    for section in document.sections:
        heading_positions.append(position)
        position += 1
        unit_positions.append(list(range(position, position + len(section.units))))
        position += len(section.units)
    return heading_positions, unit_positions


def heading_paths(sections: list[DocumentSection]) -> list[list[str]]:
    """Return the non-empty headings from the top to each section."""
    paths: list[list[str]] = []
    for section in sections:
        parent = paths[section.parent] if section.parent is not None else []
        paths.append([*parent, section.heading] if section.heading else list(parent))
    return paths


def common_ancestor(sections: list[DocumentSection], indexes: list[int]) -> int | None:
    """Return the lowest section that contains all the given sections.

    Args:
        sections: The sections of a document.
        indexes: The indexes of the sections to contain. A section contains itself.

    Returns:
        The index of the section, or ``None`` when only the document contains them.
    """

    def chain(index: int | None) -> list[int]:
        found: list[int] = []
        while index is not None:
            found.append(index)
            index = sections[index].parent
        return found[::-1]

    common: int | None = None
    for level in zip(*(chain(i) for i in indexes), strict=False):
        if len(set(level)) != 1:
            break
        common = level[0]
    return common
