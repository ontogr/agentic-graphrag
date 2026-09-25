"""E2E corpus ingestion: a mixed-format directory through Graph.add and search.

The scenario writes a directory with Markdown, plain text, a Latin-1 text file,
a UTF-16 text file, CSV, JSON, JSON Lines, and HTML, plus bad input: invalid
JSON, a JSON Lines file with a bad last line, and a file with an unsupported
extension. It shows that:

- every supported format lands as documents and chunks with decoded text,
- entities from each format reach the graph and one shared name resolves to
  one node across formats,
- ``error_policy="raise"`` fails on the bad input and writes nothing,
- ``error_policy="skip"`` and ``"quarantine"`` report the bad sources in the
  result, and a source that fails part way adds no documents,
- an extractor failure on one chunk is reported and does not drop the chunk,
- ``SearchEngine`` finds the text of each supported format.

The extractor and embedder are fake and deterministic. All labels are unique
per run and cleanup removes only the nodes this test created. The test writes
its outcome to ``reports/e2e/corpus_ingestion.json``.
"""

import json
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.loaders.corpus.errors import IngestionError, UnsupportedFormatError
from agrag.retrieval.recipes import CHUNK
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.e2e._artifact import write_artifact


# Each marker word appears in exactly one supported file and maps to its own
# direction in 4-d space, so a query made of the marker word points at the
# chunk that holds it.
_MARKER_VECTORS: dict[str, list[float]] = {
    "mdmark": [1.0, 0.0, 0.0, 0.0],
    "txtmark": [0.0, 1.0, 0.0, 0.0],
    "latinmark": [0.0, 0.0, 1.0, 0.0],
    "utfsixteenmark": [0.0, 0.0, 0.0, 1.0],
    "csvmark": [1.0, 1.0, 0.0, 0.0],
    "jsonmark": [0.0, 0.0, 1.0, 1.0],
    "jsonlmark": [1.0, 0.0, 1.0, 0.0],
    "htmlmark": [0.0, 1.0, 0.0, 1.0],
    "brokenmark": [1.0, 0.0, 0.0, 1.0],
    "partialmark": [0.0, 1.0, 1.0, 0.0],
}
_PERSON_NAMES = (
    "Ottoline",
    "Percival",
    "Hestia",
    "Barnaby",
    "Cordelia",
    "Thaddeus",
    "Ignatius",
    "Winifred",
    "Leopold",
)
_ORG_NAMES = ("Brindle",)
_POISON = "EXTRACTOR_BOOM"
_FORMAT_MARKERS = {
    "markdown": "mdmark",
    "text": "txtmark",
    "latin1_text": "latinmark",
    "utf16_text": "utfsixteenmark",
    "csv": "csvmark",
    "json": "jsonmark",
    "jsonl": "jsonlmark",
    "html": "htmlmark",
}
_LATIN1_TEXT = (
    "Hestia sirvió café, crème brûlée y jalapeño en el "
    "mercado de la ciudad. latinmark. Ella también preparó una tarta de "
    "manzana con canela y azúcar moreno.\n"
)


class _MarkerEmbedder(Embedder):
    """Embedder whose vector is a small base plus the vectors of marker words."""

    model = "marker"

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the base vector plus one vector per marker word in each text."""
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.05] * 4
            lowered = text.lower()
            for marker, direction in _MARKER_VECTORS.items():
                if marker in lowered:
                    vector = [a + b for a, b in zip(vector, direction, strict=True)]
            vectors.append(vector)
        return vectors


class _NameExtractor(Extractor):
    """Extractor that finds fixed names and fails on a poison word."""

    def __init__(self, person_label: str, org_label: str) -> None:
        """Remember the labels to emit."""
        self._labels = dict.fromkeys(_PERSON_NAMES, person_label)
        self._labels.update(dict.fromkeys(_ORG_NAMES, org_label))

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return one entity per known name in the chunk text."""
        if _POISON in chunk.text:
            raise RuntimeError("extractor failed on poison chunk")
        entities = [
            ExtractedEntity(
                chunk_id=chunk.id,
                label=label,
                text=name,
                char_start=chunk.text.index(name),
                char_end=chunk.text.index(name) + len(name),
            )
            for name, label in self._labels.items()
            if name in chunk.text
        ]
        return ExtractionResult(entities=entities, relations=[], extractor_name="e2e")


@dataclass
class _Env:
    """Handles the tests share: store, graph, labels, and directories."""

    store: GraphStore
    graph: Graph
    engine: SearchEngine
    person_label: str
    org_label: str
    root: Path


def _write_supported_files(directory: Path) -> None:
    """Write one file per supported format."""
    (directory / "notes.md").write_text(
        "# Harbor Notes\n\nOttoline logged the tide tables. mdmark.\n"
        "Brindle keeps the ledger.\n"
    )
    (directory / "log.txt").write_text("Percival walked the pier at dawn. txtmark.\n")
    (directory / "cafe_latin1.txt").write_bytes(_LATIN1_TEXT.encode("latin-1"))
    (directory / "wide_utf16.txt").write_bytes(
        "Barnaby counted the lanterns. utfsixteenmark.\n".encode("utf-16")
    )
    (directory / "people.csv").write_text(
        "id,title,text\n1,First,Cordelia mends nets. csvmark.\n"
        "2,Second,Nothing to report here.\n"
    )
    (directory / "items.json").write_text(
        json.dumps(
            [
                {"text": "Thaddeus sold kites. jsonmark."},
                {"text": "A second entry."},
                {"text": f"Ypsilon {_POISON}"},
            ]
        )
    )
    (directory / "events.jsonl").write_text(
        '{"text": "Ignatius rang the bell. jsonlmark."}\n{"text": "Second line."}\n'
    )
    (directory / "page.html").write_text(
        "<html><head><title>T</title><style>.x{}</style></head><body>"
        "<main><p>Winifred baked bread.</p>"
        "<p>htmlmark. Brindle sells flour.</p></main></body></html>"
    )


def _write_bad_files(directory: Path) -> None:
    """Write input the readers must reject."""
    (directory / "broken.json").write_text('{"text": "brokenmark", ')
    (directory / "partial.jsonl").write_text(
        '{"text": "Leopold wrote first. partialmark."}\n'
        '{"text": "second line"}\n'
        "this line is not json\n"
    )
    (directory / "data.xyz").write_text("brokenmark in an unsupported format\n")


async def _remove_created(store: GraphStore, env: _Env) -> None:
    """Delete only the nodes this test created, found by uri prefix and label."""
    params = {"prefix": str(env.root)}
    await store.execute_write(
        f"MATCH (d:{DOCUMENT_LABEL}) WHERE d.uri STARTS WITH $prefix "
        f"OPTIONAL MATCH (c:{CHUNK_LABEL})-[:PART_OF]-(d) DETACH DELETE c, d",
        params,
    )
    await store.execute_write(
        "MATCH (j:CutoverJob) WHERE j.document_key STARTS WITH $prefix DETACH DELETE j",
        params,
    )
    for label in (env.person_label, env.org_label):
        await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")


@pytest.fixture
async def env(tmp_path: Path) -> AsyncGenerator[_Env, None]:
    """Provide a graph over a fresh store with unique labels and a corpus root."""
    store = build_graph_store("neo4j")
    await store.connect()
    suffix = uuid4().hex[:8]
    person_label = validate_identifier(f"Person_{suffix}")
    org_label = validate_identifier(f"Org_{suffix}")
    schema = GraphSchema(
        name="e2e_corpus",
        version="1",
        entities=[
            EntityType(label=person_label, description="A person."),
            EntityType(label=org_label, description="An organization."),
        ],
        relations=[],
    )
    embedder = _MarkerEmbedder()
    for label in (person_label, org_label, CHUNK_LABEL):
        await store.ensure_vector_index(
            label=label,
            vector_property="embedding",
            dimensions=4,
            distance=Distance.COSINE,
        )
    graph = Graph(
        schema=schema,
        graph_store=store,
        embedder=embedder,
        extractor=_NameExtractor(person_label, org_label),
    )
    engine = SearchEngine(
        graph_store=store,
        embedder=embedder,
        settings=RetrievalSettings(entity_top_k=10, chunk_top_k=10),
        graph_schema=schema,
    )
    current = _Env(store, graph, engine, person_label, org_label, tmp_path)
    try:
        yield current
    finally:
        await _remove_created(store, current)
        await drop_schema_for(store, person_label, org_label)
        await store.close()


async def _document_rows(env: _Env) -> list[dict]:
    """Return one row per chunk stored for this test's documents, in stable order."""
    return await env.store.execute_read(
        f"MATCH (c:{CHUNK_LABEL})-[:PART_OF]-(d:{DOCUMENT_LABEL}) "
        "WHERE d.uri STARTS WITH $prefix "
        "RETURN d.document_key AS key, d.title AS title, c.text AS text "
        "ORDER BY key",
        {"prefix": str(env.root)},
    )


def _relative(env: _Env, key: str) -> str:
    """Return a document key with the run-specific directory removed."""
    return key.replace(str(env.root) + "/", "")


async def test_mixed_corpus_ingests_and_reports_bad_sources(env: _Env) -> None:  # noqa: PLR0915
    """Supported formats land and are searchable; bad sources are reported."""
    corpus = env.root / "corpus"
    corpus.mkdir()
    _write_supported_files(corpus)
    _write_bad_files(corpus)

    with pytest.raises(IngestionError):
        await env.graph.add(corpus, error_policy="raise")
    assert await _document_rows(env) == []

    result = await env.graph.add(corpus, error_policy="skip", return_chunks=True)

    assert result.ingestion.sources == 8
    assert result.ingestion.skipped == 3
    assert result.ingestion.quarantined == 0
    assert result.ingestion.documents == 12
    assert len(result.chunks) == 12
    assert result.extraction.failures_total == 1
    assert result.extraction.failures[0].error_type == "RuntimeError"

    rows = await _document_rows(env)
    by_key = {_relative(env, row["key"]): row for row in rows}
    assert sorted(by_key) == [
        "corpus/cafe_latin1.txt",
        "corpus/events.jsonl:0",
        "corpus/events.jsonl:1",
        "corpus/items.json:0",
        "corpus/items.json:1",
        "corpus/items.json:2",
        "corpus/log.txt",
        "corpus/notes.md",
        "corpus/page.html",
        "corpus/people.csv:0",
        "corpus/people.csv:1",
        "corpus/wide_utf16.txt",
    ]
    all_text = "\n".join(row["text"] for row in rows)
    assert by_key["corpus/notes.md"]["title"] == "Harbor Notes"
    assert by_key["corpus/cafe_latin1.txt"]["text"] == _LATIN1_TEXT
    assert "�" not in all_text
    assert "utfsixteenmark" in by_key["corpus/wide_utf16.txt"]["text"]
    assert "<" not in by_key["corpus/page.html"]["text"]
    assert "Cordelia" in by_key["corpus/people.csv:0"]["text"]
    assert "Leopold" not in all_text
    assert "brokenmark" not in all_text
    assert "partialmark" not in all_text

    entity_rows = await env.store.execute_read(
        f"MATCH (n:{env.person_label}) RETURN n.name AS name ORDER BY name"
    )
    people = [row["name"] for row in entity_rows]
    assert people == sorted(_PERSON_NAMES[:-1])
    org_rows = await env.store.execute_read(
        f"MATCH (n:{env.org_label})-[:MENTIONED_IN]-(c:{CHUNK_LABEL}) "
        "RETURN n.name AS name, count(DISTINCT c) AS chunks"
    )
    assert [(row["name"], row["chunks"]) for row in org_rows] == [("Brindle", 2)]

    found: dict[str, str | None] = {}
    for format_name, marker in _FORMAT_MARKERS.items():
        hits = await env.engine.search(marker, CHUNK)
        texts = [hit.item.text for hit in hits if isinstance(hit.item, Chunk)]
        assert texts, f"no chunk hits for {format_name}"
        assert marker in texts[0], f"top hit for {format_name} lacks {marker}"
        found[format_name] = marker
    unwanted = await env.engine.search("brokenmark partialmark", CHUNK)
    unwanted_texts = [hit.item.text for hit in unwanted if isinstance(hit.item, Chunk)]
    assert not any(
        "brokenmark" in text or "partialmark" in text for text in unwanted_texts
    )

    quarantine_dir = env.root / "quarantine"
    quarantine_dir.mkdir()
    _write_bad_files(quarantine_dir)
    quarantined = await env.graph.add(quarantine_dir, error_policy="quarantine")
    assert quarantined.ingestion.documents == 0
    assert quarantined.ingestion.quarantined == 3
    assert quarantined.ingestion.skipped == 0
    quarantine_items = {
        _relative(env, item.item_id): item.error_message
        for item in quarantined.ingestion.quarantined_items
    }
    assert sorted(quarantine_items) == [
        "quarantine/broken.json",
        "quarantine/data.xyz",
        "quarantine/partial.jsonl",
    ]
    assert all(quarantine_items.values())
    assert len(await _document_rows(env)) == 12

    artifact = write_artifact(
        "corpus_ingestion",
        {
            "raise_policy": "IngestionError, no documents written",
            "skip_policy": {
                "documents": result.ingestion.documents,
                "sources": result.ingestion.sources,
                "skipped": result.ingestion.skipped,
                "extraction_failures": result.extraction.failures_total,
            },
            "quarantine_policy": {
                "documents": quarantined.ingestion.documents,
                "quarantined": sorted(quarantine_items),
            },
            "document_keys": sorted(by_key),
            "people": people,
            "shared_org_chunks": {row["name"]: row["chunks"] for row in org_rows},
            "search_top_hit_marker": found,
        },
    )
    assert artifact["skip_policy"] == {
        "documents": 12,
        "sources": 8,
        "skipped": 3,
        "extraction_failures": 1,
    }
    assert artifact["people"] == people
    assert artifact["search_top_hit_marker"] == _FORMAT_MARKERS


@pytest.mark.parametrize(
    ("file_name", "content", "error_type"),
    [
        ("broken.json", '{"text": "brokenmark", ', IngestionError),
        ("partial.jsonl", '{"text": "partialmark"}\nnot json\n', IngestionError),
        ("data.xyz", "brokenmark", UnsupportedFormatError),
    ],
)
async def test_raise_policy_stops_and_writes_nothing(
    env: _Env, file_name: str, content: str, error_type: type[Exception]
) -> None:
    """A bad source under ``raise`` fails the call before any document is written."""
    directory = env.root / "strict"
    directory.mkdir()
    (directory / "a_good.txt").write_text("Percival walked the pier. txtmark.\n")
    (directory / file_name).write_text(content)

    with pytest.raises(error_type):
        await env.graph.add(directory, error_policy="raise")

    assert await _document_rows(env) == []
    rows = await env.store.execute_read(f"MATCH (n:{env.person_label}) RETURN n")
    assert rows == []
