"""Pure record construction for the Section tree of a document.

This module is internal. ``Graph.add`` and ``Graph.update`` call these functions to
turn a ``Document`` and its chunks into ``NodeRecord`` and ``RelationRecord`` writes.
Nothing here touches ``GraphStore``.
"""

import json
import logging
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID

from agrag.chunking.chunker import ChunkedDocument, ChunkPlacement
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    Unit,
    UnitKind,
)
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.provenance import PageProvenance
from agrag.common.data_models.structure import (
    FIGURE_LABEL,
    HAS_CHILD,
    HAS_DOCUMENT,
    SECTION_LABEL,
    SOURCE_LABEL,
    TABLE_LABEL,
    node_id,
    reading_positions,
    section_keys,
    source_node_id,
    unit_keys,
    version_id,
)
from agrag.ingestion._lexical_backbone import build_part_of_records
from agrag.ingestion.merge import has_child_id, relation_id


logger = logging.getLogger(__name__)


@dataclass
class StructureRecords:
    """The graph records for the sections, tables and figures of one document version.

    Attributes:
        sections: One node record for each section.
        tables: One node record for each table.
        figures: One node record for each figure.
        sources: One node record for each record file.
        relations: The ``HAS_CHILD``, ``PART_OF`` and ``HAS_DOCUMENT`` edges.
        structure_node_ids: The id of every section, table and figure node.
            Chunk ids are not included; callers union them in when they need
            the full linked set, as ``build_document_structure`` does for its
            ``PART_OF`` edges.
    """

    sections: list[NodeRecord] = field(default_factory=list)
    tables: list[NodeRecord] = field(default_factory=list)
    figures: list[NodeRecord] = field(default_factory=list)
    sources: list[NodeRecord] = field(default_factory=list)
    relations: list[RelationRecord] = field(default_factory=list)
    structure_node_ids: list[UUID] = field(default_factory=list)

    @property
    def node_count(self) -> int:
        """Return the number of section, table, figure and source nodes."""
        return len(self.structure_node_ids) + len(self.sources)


def _page_range(units: list[Unit]) -> dict[str, int]:
    pages = [span.page_no for unit in units for span in unit.pages]
    return {"page_start": min(pages), "page_end": max(pages)} if pages else {}


def _char_range(units: list[Unit]) -> dict[str, int]:
    starts = [u.char_start for u in units if u.char_start is not None]
    ends = [u.char_end for u in units if u.char_end is not None]
    if not starts or not ends:
        return {}
    return {"char_start": min(starts), "char_end": max(ends)}


def _require_chunk_ids(chunks: list[Chunk]) -> list[UUID]:
    """Return every chunk's id, failing fast when one is missing.

    Args:
        chunks: The chunks to link into the structure.

    Returns:
        Every chunk's id, in chunk order.

    Raises:
        ValueError: A chunk has no id yet.
    """
    ids: list[UUID] = []
    for chunk in chunks:
        if chunk.id is None:
            raise ValueError("Chunk.id must be set before building structure records.")
        ids.append(chunk.id)
    return ids


def _link(parent: UUID, child: UUID, order: int, *, version: str) -> RelationRecord:
    """Return one versioned parent ``-[HAS_CHILD]->`` child edge.

    The edge id folds in the document version, the same convergence rule
    ``PART_OF`` edges use: an identical re-ingest rebuilds the same ids,
    while a new version shares no edge with the subtree it supersedes, so
    closing the old ``PART_OF`` edges detaches that subtree with no orphans.
    """
    return RelationRecord(
        id=has_child_id(parent, child, version),
        type=HAS_CHILD,
        start_id=parent,
        end_id=child,
        properties={"order": order},
    )


def _section_records(
    document: Document,
    keys: list[UUID],
    section_ids: list[UUID],
    document_id: UUID,
    *,
    version: str,
    heading_positions: list[int],
) -> tuple[list[NodeRecord], list[RelationRecord]]:
    """Return one node and one parent edge for each section."""
    sections: list[NodeRecord] = []
    relations: list[RelationRecord] = []
    for i, section in enumerate(document.sections):
        properties: dict[str, object] = {
            "document_id": str(document_id),
            "section_key": str(keys[i]),
            "index": i,
            "heading": section.heading,
            "depth": section.depth,
            "version_id": version,
            **_page_range(section.units),
            **_char_range(section.units),
        }
        if section.source_id is not None:
            properties["source_id"] = section.source_id
        sections.append(
            NodeRecord(id=section_ids[i], labels=[SECTION_LABEL], properties=properties)
        )
        parent = document_id if section.parent is None else section_ids[section.parent]
        relations.append(
            _link(parent, section_ids[i], heading_positions[i], version=version)
        )
    return sections, relations


def _unit_records(
    document: Document,
    keys: list[UUID],
    unit_ids: dict[tuple[int, int], UUID],
    section_ids: list[UUID],
    document_id: UUID,
    *,
    version: str,
    unit_positions: list[list[int]],
) -> tuple[list[NodeRecord], list[NodeRecord], list[RelationRecord], dict[int, UUID]]:
    """Return the table and figure nodes, their section edges, and the table lookup."""
    tables: list[NodeRecord] = []
    figures: list[NodeRecord] = []
    relations: list[RelationRecord] = []
    table_by_position: dict[int, UUID] = {}
    for i, section in enumerate(document.sections):
        for j, unit in enumerate(section.units):
            if unit.kind not in (UnitKind.TABLE, UnitKind.FIGURE):
                continue
            unit_id = unit_ids[i, j]
            pages = PageProvenance(page_spans=unit.pages).model_dump(mode="json")
            properties = {
                "document_id": str(document_id),
                "section_key": str(keys[i]),
                "provenance": json.dumps(pages),
                "version_id": version,
                **_page_range([unit]),
            }
            if unit.caption is not None:
                properties["caption"] = unit.caption
            if unit.kind == UnitKind.TABLE:
                properties["columns"] = unit.header
                properties["n_rows"] = len(unit.rows)
                tables.append(
                    NodeRecord(id=unit_id, labels=[TABLE_LABEL], properties=properties)
                )
                table_by_position[unit_positions[i][j]] = unit_id
            else:
                figures.append(
                    NodeRecord(id=unit_id, labels=[FIGURE_LABEL], properties=properties)
                )
            relations.append(
                _link(section_ids[i], unit_id, unit_positions[i][j], version=version)
            )
    return tables, figures, relations, table_by_position


def placement_map(chunked: ChunkedDocument) -> dict[UUID, ChunkPlacement]:
    """Return the placements of one chunked document, by chunk id.

    Args:
        chunked: The chunks of one document with their placements.

    Returns:
        Each placement by its chunk's id. Chunks with no id yet are left out.
    """
    return {
        chunk.id: placement
        for chunk, placement in zip(chunked.chunks, chunked.placements, strict=True)
        if chunk.id is not None
    }


def _chunk_links(
    document_id: UUID,
    chunks: list[Chunk],
    placements: Mapping[UUID, ChunkPlacement],
    table_by_position: dict[int, UUID],
    *,
    version: str,
) -> list[RelationRecord]:
    """Return one parent edge for each chunk.

    A chunk hangs under its placement's parent: the table it came from, the
    lowest section that holds its text, or the document when no section does.
    A chunk with no placement hangs under the document with its index as the
    order, so hand-built chunks without a chunker still build.

    Raises:
        ValueError: A chunk has no id, or a table chunk's placement parent is
            not a table node of the document.
    """
    table_ids = set(table_by_position.values())
    links: list[RelationRecord] = []
    for chunk in chunks:
        if chunk.id is None:
            raise ValueError("Chunk.id must be set before building structure records.")
        placement = placements.get(chunk.id)
        if placement is None:
            links.append(_link(document_id, chunk.id, chunk.index, version=version))
            continue
        if chunk.content_kind == "table" and placement.parent_node_id not in table_ids:
            raise ValueError(
                f"table chunk {chunk.index} has no table unit in the document"
            )
        links.append(
            _link(placement.parent_node_id, chunk.id, placement.order, version=version)
        )
    return links


def build_structure(
    document: Document,
    chunks: list[Chunk],
    placements: Mapping[UUID, ChunkPlacement] | None = None,
) -> StructureRecords:
    """Build the structure records of one document version.

    Every section hangs under its parent section, or under the document. A table or
    figure hangs under its section. A chunk hangs under its placement's parent node.
    Each edge carries an ``order``: the placement order, or the chunk index for a
    chunk with no placement.

    Args:
        document: The document.
        chunks: The chunks that the chunker made from the document.
        placements: Each chunk's placement by chunk id, from
            :func:`placement_map`. A chunk with no entry hangs under the
            document.

    Returns:
        The node records and edges. A document with no sections gives only the edges
        from the document to its chunks.
    """
    version = version_id(document)
    keys = section_keys(document)
    section_ids = [node_id(key, version) for key in keys]
    unit_ids = {
        at: node_id(key, version) for at, key in unit_keys(document, keys).items()
    }
    heading_positions, unit_positions = reading_positions(document)
    document_id = Document.node_id_for(document_key=document.resolved_document_key)
    _require_chunk_ids(chunks)
    section_nodes, section_links = _section_records(
        document,
        keys,
        section_ids,
        document_id,
        version=version,
        heading_positions=heading_positions,
    )
    tables, figures, unit_links, table_by_position = _unit_records(
        document,
        keys,
        unit_ids,
        section_ids,
        document_id,
        version=version,
        unit_positions=unit_positions,
    )
    chunk_links = _chunk_links(
        document_id, chunks, placements or {}, table_by_position, version=version
    )
    return StructureRecords(
        sections=section_nodes,
        tables=tables,
        figures=figures,
        relations=[*section_links, *unit_links, *chunk_links],
        structure_node_ids=[*section_ids, *unit_ids.values()],
    )


def build_source_records(
    documents: list[Document],
) -> tuple[list[NodeRecord], list[RelationRecord]]:
    """Build a Source node for each record file and an edge to each of its rows.

    Args:
        documents: The documents of one ``add`` call. Only record documents count.

    Returns:
        The Source node records, one for each distinct file, and one
        ``Source -[HAS_DOCUMENT]-> Document`` edge for each record document.
    """
    nodes: dict[UUID, NodeRecord] = {}
    relations: list[RelationRecord] = []
    for document in documents:
        if document.family != DocumentFamily.RECORD:
            continue
        source_id = source_node_id(document.uri)
        nodes.setdefault(
            source_id,
            NodeRecord(
                id=source_id,
                labels=[SOURCE_LABEL],
                properties={
                    "uri": document.uri,
                    "source_format": document.source_format.value,
                },
            ),
        )
        row_id = Document.node_id_for(document_key=document.resolved_document_key)
        relations.append(
            RelationRecord(
                id=relation_id(source_id, row_id, HAS_DOCUMENT),
                type=HAS_DOCUMENT,
                start_id=source_id,
                end_id=row_id,
                properties={},
            )
        )
    return list(nodes.values()), relations


def build_document_structure(
    documents: list[Document],
    chunks: list[Chunk],
    placements: Mapping[UUID, ChunkPlacement] | None = None,
) -> StructureRecords:
    """Build the structure records for the documents of one ``add`` call.

    Each document contributes its section, table and figure nodes, with the edges
    from ``build_structure``. Each structure node also gets a ``PART_OF`` edge from
    its document, and each record file gets a Source node. Chunks of documents that
    are not in ``documents`` are ignored; the ignore is logged at debug level,
    since the walk is expected to hand over exactly the chunks of ``documents``.

    Args:
        documents: The distinct documents of the call, as ``distinct_documents``
            returns them.
        chunks: The chunks that the chunker made from the documents.
        placements: Each chunk's placement by chunk id, from
            :func:`placement_map`. A chunk with no entry hangs under the
            document.

    Returns:
        The structure records. ``relations`` holds the edges of every document in
        document order, followed by the edges of the record sources.
    """
    selected = {
        Document.node_id_for(document_key=document.resolved_document_key)
        for document in documents
    }
    chunks_by_document_id: dict[UUID, list[Chunk]] = defaultdict(list)
    ignored = 0
    for chunk in chunks:
        if chunk.document_id in selected:
            chunks_by_document_id[chunk.document_id].append(chunk)
        else:
            ignored += 1
    if ignored:
        logger.debug("Ignoring %d chunks of documents outside this call.", ignored)

    out = StructureRecords()
    for document in documents:
        document_node_id = Document.node_id_for(
            document_key=document.resolved_document_key
        )
        # The version matches chunk versioning's own version_id, so an
        # identical re-ingest rebuilds the same edge ids and converges.
        version = str(Document.id_for(content_hash=document.content_hash))
        document_chunks = chunks_by_document_id.get(document_node_id, [])
        chunk_ids = _require_chunk_ids(document_chunks)
        records = build_structure(document, document_chunks, placements)
        out.sections.extend(records.sections)
        out.tables.extend(records.tables)
        out.figures.extend(records.figures)
        out.structure_node_ids.extend(records.structure_node_ids)
        out.relations.extend(records.relations)
        out.relations.extend(
            build_part_of_records(
                document_node_id,
                [
                    *chunk_ids,
                    *records.structure_node_ids,
                ],
                version_id=version,
            )
        )
    source_nodes, source_relations = build_source_records(documents)
    out.sources = source_nodes
    out.relations.extend(source_relations)
    return out
