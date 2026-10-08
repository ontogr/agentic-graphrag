"""E2E document structure: sections, tables, chunks and versions in the graph.

The scenario ingests a Markdown file with nested headings and a table, a plain text
file, and a CSV file. It then edits the Markdown file under the same document key. It
shows that:

- every section, table and chunk has exactly one ``HAS_CHILD`` parent,
- a section hangs under the section that contains it and a chunk under the section
  that holds its text,
- a table has its own node and its chunks hang under it,
- a CSV file is a Source with one Document for each row, and each row has one chunk,
- after an edit, the old version's structure is closed and the new one is current,
- a section keeps its ``section_key`` across the edit.

The embedder and extractor are fake and deterministic. The test writes its outcome to
``reports/e2e/sections.json``.
"""

from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import validate_identifier
from agrag.cypher.relations import fetch_all_relations_query
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.e2e._artifact import write_artifact


_MARKDOWN = (
    "# Harbor Guide\n\n"
    "Intro paragraph about the harbor.\n\n"
    "## Tides\n\n"
    "Tide tables are posted daily.\n\n"
    "| port | depth |\n| --- | --- |\n| north | 12 |\n| south | 9 |\n\n"
    "## Moorings\n\n"
    "Moorings are rented by the month.\n"
)
_EDITED = _MARKDOWN.replace("## Moorings", "## Berths")


class _ZeroEmbedder(Embedder):
    """Embedder that returns one small vector for every text."""

    model = "zero"

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the same vector for every text."""
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


class _NoEntityExtractor(Extractor):
    """Extractor that finds nothing."""

    async def extract(self, chunk: object, schema: GraphSchema) -> ExtractionResult:
        """Return an empty result."""
        return ExtractionResult(entities=[], relations=[], extractor_name="e2e")


@dataclass
class _Env:
    """Handles the test shares: store, graph and the corpus root."""

    store: GraphStore
    graph: Graph
    root: Path


async def _remove_created(env: _Env) -> None:
    """Delete only the nodes this test created, found by uri prefix."""
    params = {"prefix": str(env.root)}
    await env.store.execute_write(
        "MATCH (d:Document) WHERE d.uri STARTS WITH $prefix "
        "OPTIONAL MATCH (d)-[:PART_OF]->(n) DETACH DELETE n, d",
        params,
    )
    await env.store.execute_write(
        "MATCH (s:Source) WHERE s.uri STARTS WITH $prefix DETACH DELETE s", params
    )
    await env.store.execute_write(
        "MATCH (j:CutoverJob) WHERE j.document_key STARTS WITH $prefix DETACH DELETE j",
        params,
    )


@pytest.fixture
async def env(tmp_path: Path) -> AsyncGenerator[_Env, None]:
    """Provide a graph over a fresh store and a corpus root."""
    store = build_graph_store("neo4j")
    await store.connect()
    label = validate_identifier(f"Thing_{uuid4().hex[:8]}")
    schema = GraphSchema(
        name="e2e_sections",
        version="1",
        entities=[EntityType(label=label, description="A thing.")],
        relations=[],
    )
    await store.ensure_vector_index(
        label=CHUNK_LABEL,
        vector_property="embedding",
        dimensions=4,
        distance=Distance.COSINE,
    )
    graph = await Graph.open(
        schema=schema,
        graph_store=store,
        embedder=_ZeroEmbedder(),
        extractor=_NoEntityExtractor(),
    )
    current = _Env(store, graph, tmp_path)
    try:
        yield current
    finally:
        await _remove_created(current)
        await drop_schema_for(store, label)
        await store.close()


async def _rows(env: _Env, query: str) -> list[dict]:
    return await env.store.execute_read(query, {"prefix": str(env.root)})


async def _outline(env: _Env, name: str) -> list[tuple[str, str]]:
    """Return (heading, parent heading) for the current sections of one file."""
    rows = await _rows(
        env,
        "MATCH (d:Document)-[p:PART_OF]->(s:Section) "
        "WHERE d.uri = $prefix + '/" + name + "' AND p.invalid_at IS NULL "
        "OPTIONAL MATCH (parent)-[:HAS_CHILD]->(s) "
        "RETURN s.heading AS heading, coalesce(parent.heading, '(document)') "
        "AS parent ORDER BY s.index",
    )
    return [(row["heading"], row["parent"]) for row in rows]


async def test_structure_is_written_and_versioned(env: _Env) -> None:  # noqa: PLR0915
    """The tree, the table, the rows and an edit all appear in the graph."""
    corpus = env.root
    (corpus / "guide.md").write_text(_MARKDOWN)
    (corpus / "notes.txt").write_text("First note.\n\nSecond note.\n")
    (corpus / "rows.csv").write_text("id,text\n1,alpha row\n2,beta row\n")

    result = await env.graph.add(corpus, return_chunks=True)

    assert result.chunking.tables == 1
    guide = await _outline(env, "guide.md")
    assert guide == [
        ("Harbor Guide", "(document)"),
        ("Tides", "Harbor Guide"),
        ("Moorings", "Harbor Guide"),
    ]
    assert await _outline(env, "notes.txt") == [("", "(document)")]

    parents = await _rows(
        env,
        "MATCH (n) WHERE (n:Section OR n:Table OR n:Chunk) AND "
        "(n.document_id = n.document_id) "
        "OPTIONAL MATCH (p)-[r:HAS_CHILD]->(n) "
        "WITH n, count(r) AS parents "
        "MATCH (d:Document)-[:PART_OF]->(n) WHERE d.uri STARTS WITH $prefix "
        "RETURN labels(n)[0] AS label, parents",
    )
    assert parents
    assert {row["parents"] for row in parents} == {1}

    table_chunks = await _rows(
        env,
        "MATCH (d:Document)-[:PART_OF]->(t:Table)-[:HAS_CHILD]->(c:Chunk) "
        "WHERE d.uri STARTS WITH $prefix "
        "RETURN t.n_rows AS rows, c.content_kind AS kind",
    )
    assert [(row["rows"], row["kind"]) for row in table_chunks] == [(3, "table")]

    sources = await _rows(
        env,
        "MATCH (s:Source)-[:HAS_DOCUMENT]->(d:Document)-[:HAS_CHILD]->(c:Chunk) "
        "WHERE s.uri STARTS WITH $prefix "
        "RETURN s.uri AS uri, count(DISTINCT d) AS rows, count(c) AS chunks",
    )
    assert [(row["rows"], row["chunks"]) for row in sources] == [(2, 2)]

    relations = await env.store.execute_read(
        fetch_all_relations_query(), {"skip": 0, "limit": 1000}
    )
    assert {row["rel_type"] for row in relations}.isdisjoint(
        {"HAS_CHILD", "HAS_DOCUMENT", "PART_OF"}
    )

    keys_before = await _rows(
        env,
        "MATCH (d:Document)-[:PART_OF]->(s:Section) "
        "WHERE d.uri STARTS WITH $prefix AND s.heading = 'Tides' "
        "RETURN s.section_key AS key, s.id AS id",
    )

    (corpus / "guide.md").write_text(_EDITED)
    update = await env.graph.update(
        str(corpus / "guide.md"), source=corpus / "guide.md"
    )

    assert update.no_op is False
    assert update.chunks_closed > 0
    edited = await _outline(env, "guide.md")
    assert edited == [
        ("Harbor Guide", "(document)"),
        ("Tides", "Harbor Guide"),
        ("Berths", "Harbor Guide"),
    ]
    keys_after = await _rows(
        env,
        "MATCH (d:Document)-[p:PART_OF]->(s:Section) "
        "WHERE d.uri STARTS WITH $prefix AND s.heading = 'Tides' "
        "AND p.invalid_at IS NULL RETURN s.section_key AS key, s.id AS id",
    )
    assert keys_after[0]["key"] == keys_before[0]["key"]
    assert keys_after[0]["id"] != keys_before[0]["id"]
    closed = await _rows(
        env,
        "MATCH (d:Document)-[p:PART_OF]->(s:Section) "
        "WHERE d.uri STARTS WITH $prefix AND p.invalid_at IS NOT NULL "
        "RETURN count(s) AS closed",
    )
    assert closed[0]["closed"] == 3

    outcome = write_artifact(
        "sections",
        {
            "guide_outline": guide,
            "guide_outline_after_edit": edited,
            "table_chunks": [(row["rows"], row["kind"]) for row in table_chunks],
            "csv_source": [(row["rows"], row["chunks"]) for row in sources],
            "closed_sections_after_edit": closed[0]["closed"],
            "document_label": DOCUMENT_LABEL,
        },
    )
    assert outcome["closed_sections_after_edit"] == 3
    assert outcome["table_chunks"] == [[3, "table"]]
