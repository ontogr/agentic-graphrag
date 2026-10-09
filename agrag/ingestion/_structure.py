"""Pure record construction for the Section tree of a document.

This module is internal. ``Graph.add`` and ``Graph.update`` call these functions to
turn a ``Document`` and its chunks into ``NodeRecord`` and ``RelationRecord`` writes.
Nothing here touches ``GraphStore``.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID

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
from agrag.ingestion.merge import relation_id


@dataclass
class StructureRecords:
    """The graph records for the sections, tables and figures of one document version.

    Attributes:
        sections: One node record for each section.
        tables: One node record for each table.
        figures: One node record for each figure.
        sources: One node record for each record file.
        relations: The ``HAS_CHILD``, ``PART_OF`` and ``HAS_DOCUMENT`` edges.
        node_ids: The id of every section, table and figure node.
    """

    sections: list[NodeRecord] = field(default_factory=list)
    tables: list[NodeRecord] = field(default_factory=list)
    figures: list[NodeRecord] = field(default_factory=list)
    sources: list[NodeRecord] = field(default_factory=list)
    relations: list[RelationRecord] = field(default_factory=list)
    node_ids: list[UUID] = field(default_factory=list)

    @property
    def node_count(self) -> int:
        """Return the number of section, table, figure and source nodes."""
        return (
            len(self.sections)
            + len(self.tables)
            + len(self.figures)
            + len(self.sources)
        )


def _page_range(units: list[Unit]) -> dict[str, int]:
    pages = [span.page_no for unit in units for span in unit.pages]
    return {"page_start": min(pages), "page_end": max(pages)} if pages else {}


def _char_range(units: list[Unit]) -> dict[str, int]:
    starts = [u.char_start for u in units if u.char_start is not None]
    ends = [u.char_end for u in units if u.char_end is not None]
    if not starts or not ends:
        return {}
    return {"char_start": min(starts), "char_end": max(ends)}


def build_structure(document: Document, chunks: list[Chunk]) -> StructureRecords:
    """Build the structure records of one document version.

    Every section hangs under its parent section, or under the document. A table or
    figure hangs under its section. A chunk hangs under the table it came from, or
    under the lowest section that holds its text, or under the document when no
    section does. Each edge carries an ``order``: the reading position of the child,
    or the chunk index for the chunks of a table.

    Args:
        document: The document.
        chunks: The chunks that the chunker made from the document.

    Returns:
        The node records and edges. A document with no sections gives only the edges
        from the document to its chunks.
    """
    sections = document.sections
    version = version_id(document)
    keys = section_keys(document)
    section_ids = [node_id(key, version) for key in keys]
    unit_ids = {
        at: node_id(key, version) for at, key in unit_keys(document, keys).items()
    }
    heading_positions, unit_positions = reading_positions(document)
    document_id = Document.node_id_for(document_key=document.resolved_document_key)
    out = StructureRecords(node_ids=list(section_ids))
    table_by_position: dict[int, UUID] = {}

    def link(parent: UUID, child: UUID, order: int) -> None:
        out.relations.append(
            RelationRecord(
                id=relation_id(parent, child, HAS_CHILD),
                type=HAS_CHILD,
                start_id=parent,
                end_id=child,
                properties={"order": order},
            )
        )

    for i, section in enumerate(sections):
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
        out.sections.append(
            NodeRecord(id=section_ids[i], labels=[SECTION_LABEL], properties=properties)
        )
        parent = document_id if section.parent is None else section_ids[section.parent]
        link(parent, section_ids[i], heading_positions[i])
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
                out.tables.append(
                    NodeRecord(id=unit_id, labels=[TABLE_LABEL], properties=properties)
                )
                table_by_position[unit_positions[i][j]] = unit_id
            else:
                out.figures.append(
                    NodeRecord(id=unit_id, labels=[FIGURE_LABEL], properties=properties)
                )
            out.node_ids.append(unit_id)
            link(section_ids[i], unit_id, unit_positions[i][j])

    for chunk in chunks:
        if chunk.id is None:
            raise ValueError("Chunk.id must be set before building structure records.")
        if chunk.content_kind == "table":
            link(table_by_position[chunk.position], chunk.id, chunk.index)
            continue
        parent = (
            document_id if chunk.parent_section_id is None else chunk.parent_section_id
        )
        link(parent, chunk.id, chunk.position)
    return out


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
    documents: list[Document], chunks: list[Chunk]
) -> StructureRecords:
    """Build the structure records for the documents of one ``add`` call.

    Each document contributes its section, table and figure nodes, with the edges
    from ``build_structure``. Each structure node also gets a ``PART_OF`` edge from
    its document, and each record file gets a Source node. Chunks of documents that
    are not in ``documents`` are ignored.

    Args:
        documents: The distinct documents of the call, as ``distinct_documents``
            returns them.
        chunks: The chunks that the chunker made from the documents.

    Returns:
        The structure records. ``relations`` holds the edges of every document in
        document order, followed by the edges of the record sources.
    """
    selected = {
        Document.node_id_for(document_key=document.resolved_document_key)
        for document in documents
    }
    chunks_by_document_id: dict[UUID, list[Chunk]] = defaultdict(list)
    for chunk in chunks:
        if chunk.document_id in selected:
            chunks_by_document_id[chunk.document_id].append(chunk)

    out = StructureRecords()
    for document in documents:
        document_node_id = Document.node_id_for(
            document_key=document.resolved_document_key
        )
        # The version matches chunk versioning's own version_id, so an
        # identical re-ingest rebuilds the same edge ids and converges.
        version = str(Document.id_for(content_hash=document.content_hash))
        document_chunks = chunks_by_document_id.get(document_node_id, [])
        records = build_structure(document, document_chunks)
        out.sections.extend(records.sections)
        out.tables.extend(records.tables)
        out.figures.extend(records.figures)
        out.relations.extend(records.relations)
        out.relations.extend(
            build_part_of_records(
                document_node_id,
                [
                    *(c.id for c in document_chunks if c.id is not None),
                    *records.node_ids,
                ],
                version_id=version,
            )
        )
    source_nodes, source_relations = build_source_records(documents)
    out.sources = source_nodes
    out.relations.extend(source_relations)
    return out
