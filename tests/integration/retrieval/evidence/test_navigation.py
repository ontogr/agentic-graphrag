"""Integration tests for bounded navigation around one evidence passage.

The fixture writes two documents under keys that carry a per-test run id: a
sectioned Markdown-style guide and a document with a table. Chunks are cut at
20 tokens, so each authored paragraph becomes its own chunk and the expected
neighbors follow directly from the authored order. Each paragraph starts with a
marker word, and the tests identify items by the marker in their text.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import uuid4

import pytest

from agrag.chunking import Chunker
from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    DocumentSection,
    SourceFormat,
    Unit,
    UnitKind,
)
from agrag.common.data_models.evidence import (
    DiscoveryMode,
    EvidenceKind,
    EvidenceReference,
    FetchStatus,
    VersionStatus,
)
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.navigation import (
    NavigationRelation,
    NavigationStatus,
    TruncationReason,
)
from agrag.common.data_models.provenance import BoundingBox, PageSpan
from agrag.evidence import discover, fetch, navigate
from agrag.evidence.ids import encode_evidence_id
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.graph import Graph
from tests.integration.retrieval.evidence._corpus import (
    BagOfWordsEmbedder,
    NoEntityExtractor,
    sha256_of,
)


_CHUNK_SIZE = 20
_MARKERS = (
    "setupone",
    "setuptwo",
    "installone",
    "configureone",
    "usageone",
    "usagetwo",
    "usagethree",
)


def _paragraph(marker: str) -> str:
    """Return a paragraph of about 14 words that starts with the marker."""
    return f"{marker} starts this passage with steady routine notes about the layout."


def _sectioned_document(key: str) -> Document:
    """Build the guide: Setup has two chunks, with Install and Configure under it.

    The text offsets point into the paragraphs joined by blank lines, so the
    document has text provenance.
    """
    layout: list[tuple[str, int, int | None, list[str]]] = [
        ("Setup", 1, None, [_paragraph("setupone"), _paragraph("setuptwo")]),
        ("Install", 2, 0, [_paragraph("installone")]),
        ("Configure", 2, 0, [_paragraph("configureone")]),
        (
            "Usage",
            1,
            None,
            [_paragraph("usageone"), _paragraph("usagetwo"), _paragraph("usagethree")],
        ),
    ]
    paragraphs = [text for _, _, _, texts in layout for text in texts]
    text = "\n\n".join(paragraphs)
    sections: list[DocumentSection] = []
    position = 0
    for heading, depth, parent, texts in layout:
        units: list[Unit] = []
        for body in texts:
            units.append(
                Unit(
                    kind=UnitKind.PARAGRAPH,
                    text=body,
                    char_start=position,
                    char_end=position + len(body),
                )
            )
            position += len(body) + 2
        sections.append(
            DocumentSection(heading=heading, depth=depth, parent=parent, units=units)
        )
    return Document(
        text=text,
        title="guide",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=sha256_of(text),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(text),
        line_count=text.count("\n") + 1,
        sections=sections,
    )


def _table_document(key: str) -> Document:
    """Build a document with one section that holds a captioned table.

    The table has 12 data rows, so it becomes several row-group chunks, and each
    chunk repeats the header row. Units carry page provenance and no offsets.
    """
    span = PageSpan(page_no=1, bbox=BoundingBox(x0=0, y0=0, x1=1, y1=1))
    rows = [["item", "cost", "note"]] + [
        [f"fruit{i}", str(i), "ripe"] for i in range(12)
    ]
    caption = "Fruit costs"
    text = "pricesintro starts the section."
    section = DocumentSection(
        heading="Prices",
        depth=1,
        units=[
            Unit(kind=UnitKind.PARAGRAPH, text=text, pages=[span]),
            Unit(
                kind=UnitKind.TABLE,
                text=caption,
                caption=caption,
                rows=rows,
                header_rows=1,
                pages=[span],
            ),
        ],
    )
    return Document(
        text=text,
        title="prices",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=sha256_of(text),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(text),
        line_count=1,
        sections=[section],
    )


@dataclass
class NavEnv:
    """A graph with the guide and the price table, under one run id.

    Attributes:
        run: The per-test id that every document key carries.
        store: The connected graph store.
        graph: The graph that wrote the documents.
    """

    run: str
    store: GraphStore
    graph: Graph

    def key(self, name: str) -> str:
        """Return the document key for a short name."""
        return f"nav://{self.run}/{name}"

    @property
    def guide(self) -> str:
        """Return the key of the sectioned guide."""
        return self.key("guide")

    @property
    def prices(self) -> str:
        """Return the key of the price table document."""
        return self.key("prices")


async def _cleanup(env: NavEnv) -> None:
    """Delete the nodes written under this run's document keys."""
    prefix = env.key("")
    await env.store.execute_write(
        "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix "
        "MATCH (d)-[:HAS_PART]->(c:Chunk) DETACH DELETE c",
        {"prefix": prefix},
    )
    await env.store.execute_write(
        "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix DETACH DELETE d",
        {"prefix": prefix},
    )


@pytest.fixture
async def nav_env() -> AsyncGenerator[NavEnv, None]:
    """Open a graph, add the guide and the price table, and wait for the indexes."""
    run = uuid4().hex[:8]
    schema = GraphSchema(name="navigation", version="1", entities=[], relations=[])
    store = build_graph_store("neo4j")
    graph = await Graph.open(
        schema=schema,
        graph_store=store,
        embedder=BagOfWordsEmbedder(),
        extractor=NoEntityExtractor(),
        chunker=Chunker(size=_CHUNK_SIZE),
    )
    env = NavEnv(run=run, store=store, graph=graph)
    try:
        await store.execute_read("CALL db.awaitIndexes(60)")
        await graph.add(
            documents=[
                _sectioned_document(env.guide),
                _table_document(env.prices),
            ]
        )
        yield env
    finally:
        try:
            await _cleanup(env)
        finally:
            await store.close()


async def _id_of(env: NavEnv, marker: str, key: str) -> str:
    """Return the evidence id of the chunk whose text holds a marker word."""
    result = await discover(
        env.store,
        BagOfWordsEmbedder(),
        marker,
        mode=DiscoveryMode.LEXICAL,
        limit=5,
        scope=frozenset({key}),
    )
    [hit] = [hit for hit in result.hits if marker in hit.snippet]
    return hit.evidence_id


def _marker_of(text: str) -> str:
    """Return the marker word that a navigation item text holds."""
    [marker] = [marker for marker in _MARKERS if marker in text]
    return marker


def _markers(items: list) -> list[str]:
    """Return the marker of each navigation item, in order."""
    return [_marker_of(item.text) for item in items]


class TestNavigate:
    """Navigation returns bounded neighbors of one passage in its own version."""

    async def test_previous_and_next_follow_reading_order(
        self, nav_env: NavEnv
    ) -> None:
        """Previous and next return the chunks before and after in the document."""
        install = await _id_of(nav_env, "installone", nav_env.guide)

        previous = await navigate(
            nav_env.store,
            install,
            NavigationRelation.PREVIOUS,
            scope=frozenset({nav_env.guide}),
            limit=5,
            max_chars=10_000,
        )
        following = await navigate(
            nav_env.store,
            install,
            NavigationRelation.NEXT,
            scope=frozenset({nav_env.guide}),
            limit=5,
            max_chars=10_000,
        )

        assert previous.status is NavigationStatus.OK
        assert _markers(previous.items) == ["setuptwo"]
        assert following.status is NavigationStatus.OK
        assert _markers(following.items) == ["configureone"]

    async def test_first_chunk_has_no_previous_neighbor(self, nav_env: NavEnv) -> None:
        """The first chunk of a document reports no match for previous."""
        first = await _id_of(nav_env, "setupone", nav_env.guide)

        result = await navigate(
            nav_env.store,
            first,
            NavigationRelation.PREVIOUS,
            scope=frozenset({nav_env.guide}),
            limit=5,
            max_chars=10_000,
        )

        assert result.status is NavigationStatus.NO_MATCH
        assert result.items == []

    async def test_parent_returns_the_section_path_and_its_first_passage(
        self, nav_env: NavEnv
    ) -> None:
        """Parent returns the heading path of the section and its passage id."""
        install = await _id_of(nav_env, "installone", nav_env.guide)

        result = await navigate(
            nav_env.store,
            install,
            NavigationRelation.PARENT,
            scope=frozenset({nav_env.guide}),
            limit=5,
            max_chars=10_000,
        )

        assert result.status is NavigationStatus.OK
        [item] = result.items
        assert item.heading_path == ["Setup", "Install"]
        assert item.evidence_id == install
        assert result.multi_section is False

    async def test_children_are_the_other_passages_of_the_same_section(
        self, nav_env: NavEnv
    ) -> None:
        """Children return the other chunks under the section of the passage."""
        first = await _id_of(nav_env, "setupone", nav_env.guide)

        result = await navigate(
            nav_env.store,
            first,
            NavigationRelation.CHILDREN,
            scope=frozenset({nav_env.guide}),
            limit=5,
            max_chars=10_000,
        )

        assert _markers(result.items) == ["setuptwo"]

    async def test_siblings_are_the_other_sections_under_the_same_parent(
        self, nav_env: NavEnv
    ) -> None:
        """Siblings return the sibling sections with their first passage."""
        install = await _id_of(nav_env, "installone", nav_env.guide)

        result = await navigate(
            nav_env.store,
            install,
            NavigationRelation.SIBLINGS,
            scope=frozenset({nav_env.guide}),
            limit=5,
            max_chars=10_000,
        )

        assert result.status is NavigationStatus.OK
        assert _markers(result.items) == ["configureone"]
        assert result.items[0].heading_path == ["Setup", "Configure"]

    async def test_top_level_siblings_include_the_other_top_level_section(
        self, nav_env: NavEnv
    ) -> None:
        """A top-level section has the other top-level section as its sibling."""
        usage = await _id_of(nav_env, "usageone", nav_env.guide)

        result = await navigate(
            nav_env.store,
            usage,
            NavigationRelation.SIBLINGS,
            scope=frozenset({nav_env.guide}),
            limit=5,
            max_chars=10_000,
        )

        assert _markers(result.items) == ["setupone"]

    async def test_a_small_limit_reports_truncation_by_limit(
        self, nav_env: NavEnv
    ) -> None:
        """A limit below the neighbor count returns the first items and says so."""
        usage = await _id_of(nav_env, "usageone", nav_env.guide)

        result = await navigate(
            nav_env.store,
            usage,
            NavigationRelation.CHILDREN,
            scope=frozenset({nav_env.guide}),
            limit=1,
            max_chars=10_000,
        )

        assert _markers(result.items) == ["usagetwo"]
        assert result.truncated is True
        assert result.truncation_reason is TruncationReason.LIMIT

    async def test_a_small_char_budget_cuts_the_text_and_says_so(
        self, nav_env: NavEnv
    ) -> None:
        """Text beyond max_chars is cut, and the result reports the chars reason."""
        usage = await _id_of(nav_env, "usageone", nav_env.guide)

        result = await navigate(
            nav_env.store,
            usage,
            NavigationRelation.CHILDREN,
            scope=frozenset({nav_env.guide}),
            limit=5,
            max_chars=30,
        )

        assert sum(len(item.text) for item in result.items) == 30
        assert result.items[-1].text_truncated is True
        assert result.truncated is True
        assert result.truncation_reason is TruncationReason.CHARS

    async def test_out_of_scope_and_missing_ids_give_the_same_answer(
        self, nav_env: NavEnv
    ) -> None:
        """An id outside the scope and an id to nothing are both unavailable."""
        install = await _id_of(nav_env, "installone", nav_env.guide)
        other_document = Document.node_id_for(document_key=nav_env.key("missing"))
        missing_document = encode_evidence_id(
            EvidenceReference(
                kind=EvidenceKind.SPAN,
                document_node_id=other_document,
                content_hash_prefix=install.split(":")[3],
                char_start=0,
                char_end=5,
            )
        )

        out_of_scope = await navigate(
            nav_env.store,
            install,
            NavigationRelation.NEXT,
            scope=frozenset({nav_env.prices}),
            limit=5,
            max_chars=10_000,
        )
        missing = await navigate(
            nav_env.store,
            missing_document,
            NavigationRelation.NEXT,
            scope=frozenset({nav_env.guide}),
            limit=5,
            max_chars=10_000,
        )

        assert out_of_scope.status is NavigationStatus.UNAVAILABLE
        assert missing.status is NavigationStatus.UNAVAILABLE
        assert out_of_scope.model_dump() == missing.model_dump()

    async def test_table_context_keeps_the_header_in_every_row_group(
        self, nav_env: NavEnv
    ) -> None:
        """Each table item in table context repeats the header row."""
        middle = await _id_of(nav_env, "fruit5", nav_env.prices)

        result = await navigate(
            nav_env.store,
            middle,
            NavigationRelation.TABLE_CONTEXT,
            scope=frozenset({nav_env.prices}),
            limit=5,
            max_chars=10_000,
        )

        assert result.status is NavigationStatus.OK
        assert len(result.items) == 3
        assert all("| item | cost | note |" in item.text for item in result.items)
        assert all(item.kind == "table" for item in result.items)
        assert any("fruit5" in item.text for item in result.items)

    async def test_table_context_of_a_text_passage_is_no_match(
        self, nav_env: NavEnv
    ) -> None:
        """A text passage has no table context."""
        install = await _id_of(nav_env, "installone", nav_env.guide)

        result = await navigate(
            nav_env.store,
            install,
            NavigationRelation.TABLE_CONTEXT,
            scope=frozenset({nav_env.guide}),
            limit=5,
            max_chars=10_000,
        )

        assert result.status is NavigationStatus.NO_MATCH

    async def test_superseded_id_navigates_its_own_version(
        self, nav_env: NavEnv
    ) -> None:
        """An id of an old version keeps its own neighbors and reports superseded."""
        old_install = await _id_of(nav_env, "installone", nav_env.guide)
        await nav_env.graph.update(
            nav_env.guide,
            text="A new guide with one plain paragraph about the changed layout.",
        )

        result = await navigate(
            nav_env.store,
            old_install,
            NavigationRelation.NEXT,
            scope=frozenset({nav_env.guide}),
            limit=5,
            max_chars=10_000,
        )

        assert _markers(result.items) == ["configureone"]
        assert result.version_status is VersionStatus.SUPERSEDED

    async def test_deleted_id_is_superseded_when_navigating(
        self, nav_env: NavEnv
    ) -> None:
        """A deleted document's retained passage is not reported as current."""
        old_install = await _id_of(nav_env, "installone", nav_env.guide)
        await nav_env.graph.delete_document(nav_env.guide)

        result = await navigate(
            nav_env.store,
            old_install,
            NavigationRelation.NEXT,
            scope=frozenset({nav_env.guide}),
            limit=5,
            max_chars=10_000,
        )

        assert _markers(result.items) == ["configureone"]
        assert result.version_status is VersionStatus.SUPERSEDED

    async def test_items_of_a_headed_document_resolve_through_fetch(
        self, nav_env: NavEnv
    ) -> None:
        """Items of a headed document have evidence ids that fetch resolves.

        Headed chunks carry the heading line in their text, so their evidence ids
        are chunk references. Fetch must return the same text for each item.
        """
        install = await _id_of(nav_env, "installone", nav_env.guide)
        scope = frozenset({nav_env.guide})
        items = []
        for relation in (
            NavigationRelation.PARENT,
            NavigationRelation.PREVIOUS,
            NavigationRelation.NEXT,
            NavigationRelation.SIBLINGS,
            NavigationRelation.CHILDREN,
        ):
            result = await navigate(
                nav_env.store,
                install,
                relation,
                scope=scope,
                limit=5,
                max_chars=10_000,
            )
            items.extend(result.items)

        fetched = await fetch(
            nav_env.store,
            [item.evidence_id for item in items],
            scope=scope,
            max_chars=10_000,
        )

        assert items
        assert [outcome.status for outcome in fetched] == [FetchStatus.OK] * len(items)
        assert [outcome.text for outcome in fetched] == [item.text for item in items]

    async def test_malformed_id_is_reported_as_malformed(self, nav_env: NavEnv) -> None:
        """An id that does not decode gives the malformed status."""
        result = await navigate(
            nav_env.store,
            "not-an-evidence-id",
            NavigationRelation.PARENT,
            scope=frozenset({nav_env.guide}),
            limit=5,
            max_chars=10_000,
        )

        assert result.status is NavigationStatus.MALFORMED
        assert result.items == []

    @pytest.mark.parametrize("limit", [0, 51])
    async def test_rejects_a_limit_outside_one_to_fifty(
        self, nav_env: NavEnv, limit: int
    ) -> None:
        """A limit below one or above fifty raises ValueError."""
        install = await _id_of(nav_env, "installone", nav_env.guide)

        with pytest.raises(ValueError):
            await navigate(
                nav_env.store,
                install,
                NavigationRelation.NEXT,
                scope=frozenset({nav_env.guide}),
                limit=limit,
                max_chars=100,
            )
