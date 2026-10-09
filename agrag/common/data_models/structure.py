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


def _uuid(*parts: str | int | UUID) -> UUID:
    return uuid5(NAMESPACE_OID, json.dumps([str(part) for part in parts]))


def version_id_for_hash(*, content_hash: str) -> str:
    """Return the id of one document version from its content hash.

    Args:
        content_hash: The document's content hash.

    Returns:
        The version id, which changes when the content hash changes.
    """
    return str(Document.id_for(content_hash=content_hash))


def version_id(document: Document) -> str:
    """Return the id of one version of a document, as ``PART_OF`` edges use it.

    Thin wrapper over ``version_id_for_hash``.

    Args:
        document: The document.

    Returns:
        The id, which changes when the content hash changes.
    """
    return version_id_for_hash(content_hash=document.content_hash)


def ancestors(sections: list[DocumentSection], index: int) -> list[int]:
    """Return the index of a section and of each section above it.

    Args:
        sections: The sections of a document.
        index: The index of the section.

    Returns:
        The indexes from the outermost ancestor down to the section itself.

    Raises:
        ValueError: The index is outside ``sections``, or the parent links
            form a cycle or leave ``sections``.
    """
    if not 0 <= index < len(sections):
        raise ValueError(f"section index {index} is outside 0..{len(sections)}")
    found: list[int] = []
    seen: set[int] = set()
    current: int | None = index
    while current is not None:
        if current in seen:
            raise ValueError(f"section {current} links back to itself")
        seen.add(current)
        if not 0 <= current < len(sections):
            raise ValueError(f"section index {current} is outside 0..{len(sections)}")
        found.append(current)
        current = sections[current].parent
    return found[::-1]


def section_keys_for(sections: list[DocumentSection], document_key: str) -> list[UUID]:
    """Return one stable key for each section.

    A key stays the same across versions while the heading path of the
    section and its place among sections with the same path stay the same.

    Args:
        sections: The sections of a document, in reading order.
        document_key: The stable key of the document.

    Returns:
        The keys, in the order of ``sections``.
    """
    seen: dict[tuple[str, ...], int] = {}
    keys: list[UUID] = []
    for index in range(len(sections)):
        path = tuple(sections[i].heading for i in ancestors(sections, index))
        ordinal = seen.get(path, 0)
        seen[path] = ordinal + 1
        keys.append(
            _uuid(
                "Section",
                document_key,
                json.dumps(list(path)),
                ordinal,
            )
        )
    return keys


def section_keys(document: Document) -> list[UUID]:
    """Return one stable key for each section.

    Thin wrapper over ``section_keys_for``.

    A key stays the same across versions while the heading path of the section and
    its place among sections with the same path stay the same.

    Args:
        document: The document.

    Returns:
        The keys, in the order of ``document.sections``.
    """
    return section_keys_for(document.sections, document.resolved_document_key)


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


def reading_positions_for(
    sections: list[DocumentSection],
) -> tuple[list[int], list[list[int]]]:
    """Number every heading and unit of a section list in reading order.

    Args:
        sections: The sections of a document, in reading order.

    Returns:
        The position of each section heading, and the position of each unit.
    """
    position = 0
    heading_positions: list[int] = []
    unit_positions: list[list[int]] = []
    for section in sections:
        heading_positions.append(position)
        position += 1
        unit_positions.append(list(range(position, position + len(section.units))))
        position += len(section.units)
    return heading_positions, unit_positions


def reading_positions(document: Document) -> tuple[list[int], list[list[int]]]:
    """Number every heading and unit of a document in reading order.

    Thin wrapper over ``reading_positions_for``.

    Args:
        document: The document.

    Returns:
        The position of each section heading, and the position of each unit.
    """
    return reading_positions_for(document.sections)


def heading_paths(sections: list[DocumentSection]) -> list[list[str]]:
    """Return the non-empty headings from the top to each section."""
    return [
        [sections[i].heading for i in ancestors(sections, index) if sections[i].heading]
        for index in range(len(sections))
    ]


def common_ancestor(sections: list[DocumentSection], indexes: list[int]) -> int | None:
    """Return the lowest section that contains all the given sections.

    Args:
        sections: The sections of a document.
        indexes: The indexes of the sections to contain. A section contains itself.
            Must not be empty.

    Returns:
        The index of the section, or ``None`` when only the document contains them.

    Raises:
        ValueError: ``indexes`` is empty, or an index is outside ``sections``.
    """
    if not indexes:
        raise ValueError("indexes must hold at least one section")
    common: int | None = None
    for level in zip(*(ancestors(sections, i) for i in indexes), strict=False):
        if len(set(level)) != 1:
            break
        common = level[0]
    return common
