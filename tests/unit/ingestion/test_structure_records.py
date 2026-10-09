"""Tests for the graph records of a document's sections, tables and figures.

The functions are pure: plain data in, NodeRecord and RelationRecord out.
"""

from collections import Counter
from uuid import UUID

import pytest

from agrag.chunking.chunker import Chunker, ChunkPlacement
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import (
    Document,
    DocumentSection,
    Unit,
    UnitKind,
)
from agrag.common.data_models.structure import source_node_id
from agrag.cypher.relations import bfs_expand_query
from agrag.ingestion._structure import (
    build_document_structure,
    build_source_records,
    build_structure,
    placement_map,
)
from tests.unit.chunking._section_support import (
    page_unit,
    paragraph,
    record_document,
    sectioned_document,
)


def _placed(
    document: Document, **kwargs: object
) -> tuple[list[Chunk], dict[UUID, ChunkPlacement]]:
    """Chunk a document, returning its chunks with their placements by id."""
    chunked = Chunker(**kwargs).chunk(document)  # type: ignore[arg-type]
    return chunked.chunks, placement_map(chunked)


def _table() -> Unit:
    return Unit(
        kind=UnitKind.TABLE,
        text="Stock",
        caption="Stock",
        rows=[["name", "qty"], ["a", "1"]],
        header_rows=1,
    )


def _figure() -> Unit:
    return Unit(kind=UnitKind.FIGURE, text="A chart", caption="A chart")


def _document() -> Document:
    sections = [
        DocumentSection(heading="Intro", depth=1, units=[page_unit("x y", 1)]),
        DocumentSection(
            heading="Data",
            depth=1,
            units=[paragraph("a b c"), _table(), _figure(), paragraph("d e")],
        ),
        DocumentSection(heading="Detail", depth=2, parent=1, units=[paragraph("f g")]),
    ]
    return sectioned_document(sections)


def _parents(relations: list) -> dict[UUID, UUID]:
    return {r.end_id: r.start_id for r in relations}


class TestBuildStructure:
    """Every node has exactly one parent in the tree."""

    def test_makes_one_node_for_each_section_table_and_figure(self) -> None:
        """Counts and labels follow the document."""
        document = _document()
        chunks, placements = _placed(document, size=50)
        records = build_structure(document, chunks, placements)

        assert len(records.sections) == 3
        assert len(records.tables) == 1
        assert len(records.figures) == 1
        assert records.sections[0].labels == ["Section"]
        assert records.tables[0].labels == ["Table"]
        assert records.tables[0].properties["columns"] == ["name", "qty"]
        assert records.tables[0].properties["caption"] == "Stock"
        assert len(records.structure_node_ids) == 5

    def test_every_node_and_chunk_has_exactly_one_parent(self) -> None:
        """No node is orphaned and none is shared."""
        document = _document()
        chunks, placements = _placed(document, size=50, min_size=2)

        records = build_structure(document, chunks, placements)

        children = Counter(r.end_id for r in records.relations)
        expected = {
            n.id for n in [*records.sections, *records.tables, *records.figures]
        }
        expected |= {c.id for c in chunks if c.id is not None}
        assert set(children) == expected
        assert set(children.values()) == {1}
        assert {r.type for r in records.relations} == {"HAS_CHILD"}

    def test_sections_hang_under_their_parent_or_the_document(self) -> None:
        """A top-level section sits under the document node."""
        document = _document()
        records = build_structure(document, [], {})
        parents = _parents(records.relations)
        document_node = Document.node_id_for(document_key=document.document_key)
        ids = [s.id for s in records.sections]

        assert parents[ids[0]] == document_node
        assert parents[ids[1]] == document_node
        assert parents[ids[2]] == ids[1]

    def test_a_table_chunk_hangs_under_its_table_and_text_under_its_section(
        self,
    ) -> None:
        """The table node, not the section, holds the table chunks."""
        document = _document()
        chunks, placements = _placed(document, size=50, min_size=2)
        records = build_structure(document, chunks, placements)
        parents = _parents(records.relations)
        table = records.tables[0].id

        table_chunks = [c for c in chunks if c.content_kind == "table"]
        assert table_chunks
        assert all(parents[c.id] == table for c in table_chunks)
        data_section = records.sections[1].id
        assert parents[table] == data_section
        assert parents[records.figures[0].id] == data_section

    def test_a_chunk_over_two_sections_hangs_under_their_common_ancestor(
        self,
    ) -> None:
        """Two small sibling sections share one chunk. Their parent holds it."""
        sections = [
            DocumentSection(heading="Top", depth=1),
            DocumentSection(heading="One", depth=2, parent=0, units=[paragraph("a b")]),
            DocumentSection(heading="Two", depth=2, parent=0, units=[paragraph("c d")]),
        ]
        document = sectioned_document(sections)
        chunks, placements = _placed(document, size=50, min_size=10)

        records = build_structure(document, chunks, placements)

        assert len(chunks) == 1
        assert _parents(records.relations)[chunks[0].id] == records.sections[0].id

    def test_a_table_takes_its_columns_from_the_merged_header_rows(self) -> None:
        """Spanned header rows give one column name for each column."""
        table = Unit(
            kind=UnitKind.TABLE,
            text="",
            rows=[["Region", "Sales", ""], ["", "Q1", "Q2"], ["north", "1", "2"]],
            header_rows=2,
        )
        document = sectioned_document(
            [DocumentSection(heading="S", depth=1, units=[table])]
        )

        records = build_structure(document, [], {})

        assert records.tables[0].properties["columns"] == ["Region", "Sales Q1", "Q2"]

    def test_the_order_property_follows_reading_order(self) -> None:
        """Sibling order is the order of the children in the document."""
        document = _document()
        chunks, placements = _placed(document, size=50, min_size=2)
        records = build_structure(document, chunks, placements)
        data_section = records.sections[1].id

        under_data = sorted(
            (r.properties["order"], r.end_id)
            for r in records.relations
            if r.start_id == data_section
        )

        kinds = []
        for _, child in under_data:
            if child == records.tables[0].id:
                kinds.append("table")
            elif child == records.figures[0].id:
                kinds.append("figure")
            elif child == records.sections[2].id:
                kinds.append("section")
            else:
                kinds.append("chunk")
        assert kinds == ["chunk", "table", "figure", "chunk", "section"]

    def test_a_record_row_has_no_nodes_and_its_chunk_hangs_under_the_document(
        self,
    ) -> None:
        """A document with no sections gives only the edge to its chunk."""
        document = record_document("name: ada")
        chunks, placements = _placed(document)

        records = build_structure(document, chunks, placements)

        assert records.structure_node_ids == []
        [edge] = records.relations
        assert edge.end_id == chunks[0].id
        assert edge.start_id == Document.node_id_for(
            document_key=document.resolved_document_key
        )

    def test_a_new_version_gives_new_node_ids_and_the_same_keys(self) -> None:
        """Node ids carry the version. The section key does not."""
        first = build_structure(_document(), [], {})
        edited = _document().model_copy(update={"content_hash": "other"})
        second = build_structure(edited, [], {})

        assert [s.id for s in first.sections] != [s.id for s in second.sections]
        assert [s.properties["section_key"] for s in first.sections] == [
            s.properties["section_key"] for s in second.sections
        ]

    def test_a_new_version_shares_no_edge_with_the_old_subtree(self) -> None:
        """Versioned edge ids retire the old subtree with no orphans."""
        document = _document()
        chunks, placements = _placed(document, size=50, min_size=2)
        first = build_structure(document, chunks, placements)

        edited = _document().model_copy(update={"content_hash": "other"})
        edited_chunks, edited_placements = _placed(edited, size=50, min_size=2)
        second = build_structure(edited, edited_chunks, edited_placements)

        first_ids = {r.id for r in first.relations}
        second_ids = {r.id for r in second.relations}
        assert first_ids.isdisjoint(second_ids)

    def test_an_identical_reingest_rebuilds_the_same_edges(self) -> None:
        """The same version gives the same edge ids, so re-ingest converges."""
        document = _document()
        chunks, placements = _placed(document, size=50, min_size=2)

        first = build_structure(document, chunks, placements)
        second = build_structure(document, chunks, placements)

        assert [r.id for r in first.relations] == [r.id for r in second.relations]

    def test_a_chunk_with_no_placement_raises(self) -> None:
        """A chunk missing from the placement map fails loudly."""
        document = _document()
        chunks, _ = _placed(document, size=50, min_size=2)

        with pytest.raises(ValueError, match="has no placement"):
            build_structure(document, chunks, {})

    def test_a_table_chunk_with_no_table_unit_raises(self) -> None:
        """A table chunk whose placement parent is no table unit fails loudly."""
        document = sectioned_document(
            [DocumentSection(heading="S", depth=1, units=[paragraph("a b c")])]
        )
        chunks, placements = _placed(document, size=50, min_size=2)
        table_chunk = chunks[0].model_copy(update={"content_kind": "table"})

        with pytest.raises(ValueError, match="has no table unit"):
            build_structure(document, [table_chunk], placements)


class TestBfsStructureTraversal:
    """bfs_expand_query skips structure edges unless asked to cross them."""

    def test_default_traversal_excludes_structure_types(self) -> None:
        """PART_OF, HAS_CHILD and HAS_DOCUMENT never widen the default walk."""
        query, _ = bfs_expand_query()

        assert "NOT type(r) IN ['PART_OF', 'HAS_CHILD', 'HAS_DOCUMENT']" in query

    def test_explicit_structure_types_opt_in_to_crossing_them(self) -> None:
        """Naming a structure type crosses it without the exclusion guard."""
        query, _ = bfs_expand_query(relation_types=["PART_OF"])

        assert "NOT type(r) IN" not in query
        assert ":PART_OF" in query


class TestBuildSourceRecords:
    """Each record file gets one Source node."""

    def test_rows_of_one_file_share_a_source(self) -> None:
        """Two rows give one node and two edges."""
        rows = [
            record_document("a").model_copy(
                update={"record_index": 0, "document_key": "rows.csv:0"}
            ),
            record_document("b").model_copy(
                update={"record_index": 1, "document_key": "rows.csv:1"}
            ),
        ]

        nodes, relations = build_source_records(rows)

        assert [n.id for n in nodes] == [source_node_id("rows.csv")]
        assert nodes[0].labels == ["Source"]
        assert len(relations) == 2
        assert {r.type for r in relations} == {"HAS_DOCUMENT"}
        assert relations[0].end_id != relations[1].end_id

    def test_prose_documents_have_no_source(self) -> None:
        """Only record documents come from a Source."""
        assert build_source_records([_document()]) == ([], [])


class TestBuildDocumentStructure:
    """The structure of one add call covers every document in it."""

    def test_collects_the_nodes_and_edges_of_each_document_and_each_source(
        self,
    ) -> None:
        """Prose sections get PART_OF edges, and a record file gets a Source."""
        prose = _document()
        row = record_document("name: ada")
        prose_chunks, prose_placements = _placed(prose, size=50, min_size=2)
        row_chunks, row_placements = _placed(row)
        chunks = [*prose_chunks, *row_chunks]
        placements = {**prose_placements, **row_placements}

        structure = build_document_structure([prose, row], chunks, placements)

        assert len(structure.sections) == 3
        assert len(structure.tables) == 1
        assert len(structure.sources) == 1
        assert structure.node_count == 6
        relation_types = Counter(r.type for r in structure.relations)
        assert relation_types["PART_OF"] > 0
        assert relation_types["HAS_DOCUMENT"] == 1
