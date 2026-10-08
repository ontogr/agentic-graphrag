"""Tests for the graph records of a document's sections, tables and figures.

The functions are pure: plain data in, NodeRecord and RelationRecord out.
"""

from collections import Counter
from uuid import UUID

from agrag.chunking.chunker import Chunker
from agrag.common.data_models.document import (
    Document,
    DocumentSection,
    Unit,
    UnitKind,
)
from agrag.common.data_models.structure import source_node_id
from agrag.ingestion._structure import build_source_records, build_structure
from tests.unit.chunking._section_support import (
    page_unit,
    paragraph,
    record_document,
    sectioned_document,
)


def _table() -> Unit:
    return Unit(
        kind=UnitKind.TABLE,
        text="Stock",
        caption="Stock",
        rows=[["name", "qty"], ["a", "1"]],
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
        records = build_structure(document, Chunker(size=50).chunk(document))

        assert len(records.sections) == 3
        assert len(records.tables) == 1
        assert len(records.figures) == 1
        assert records.sections[0].labels == ["Section"]
        assert records.tables[0].labels == ["Table"]
        assert records.tables[0].properties["columns"] == ["name", "qty"]
        assert records.tables[0].properties["caption"] == "Stock"
        assert len(records.node_ids) == 5

    def test_every_node_and_chunk_has_exactly_one_parent(self) -> None:
        """No node is orphaned and none is shared."""
        document = _document()
        chunks = Chunker(size=50, min_size=2).chunk(document)

        records = build_structure(document, chunks)

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
        records = build_structure(document, [])
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
        chunks = Chunker(size=50, min_size=2).chunk(document)
        records = build_structure(document, chunks)
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
        chunks = Chunker(size=50, min_size=10).chunk(document)

        records = build_structure(document, chunks)

        assert len(chunks) == 1
        assert _parents(records.relations)[chunks[0].id] == records.sections[0].id

    def test_the_order_property_follows_reading_order(self) -> None:
        """Sibling order is the order of the children in the document."""
        document = _document()
        chunks = Chunker(size=50, min_size=2).chunk(document)
        records = build_structure(document, chunks)
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
        chunks = Chunker().chunk(document)

        records = build_structure(document, chunks)

        assert records.node_ids == []
        [edge] = records.relations
        assert edge.end_id == chunks[0].id
        assert edge.start_id == Document.node_id_for(
            document_key=document.resolved_document_key
        )

    def test_a_new_version_gives_new_node_ids_and_the_same_keys(self) -> None:
        """Node ids carry the version. The section key does not."""
        first = build_structure(_document(), [])
        edited = _document().model_copy(update={"content_hash": "other"})
        second = build_structure(edited, [])

        assert [s.id for s in first.sections] != [s.id for s in second.sections]
        assert [s.properties["section_key"] for s in first.sections] == [
            s.properties["section_key"] for s in second.sections
        ]


class TestBuildSourceRecords:
    """Each record file gets one Source node."""

    def test_rows_of_one_file_share_a_source(self) -> None:
        """Two rows give one node and two edges."""
        rows = [
            record_document("a").model_copy(update={"record_index": 0}),
            record_document("b").model_copy(update={"record_index": 1}),
        ]

        nodes, relations = build_source_records(rows)

        assert [n.id for n in nodes] == [source_node_id("rows.csv")]
        assert nodes[0].labels == ["Source"]
        assert len(relations) == 2
        assert {r.type for r in relations} == {"HAS_DOCUMENT"}

    def test_prose_documents_have_no_source(self) -> None:
        """Only record documents come from a Source."""
        assert build_source_records([_document()]) == ([], [])
