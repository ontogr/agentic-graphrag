"""End-to-end test that every vector store backend serves the same search.

The scenario ingests three short documents through ``Graph.add`` with a real
Neo4j graph store and one vector store backend (Qdrant, Weaviate, or Milvus).
It then searches with the ENTITY, CHUNK, and HYBRID recipes and checks the
ranked names, the result limit, fusion deduplication, and that deleting a
document removes its vectors from search and from the collections.

Each backend ingests the corpus once for the whole module. The read-only tests
share that run, and the one test that deletes data ingests its own. When a
backend finishes, it writes its ordered top results to the
``vector_backends_<backend>`` artifact. ``test_vector_backends_parity.py``
compares those artifacts across backends.

A backend is skipped when its service is not reachable. Set ``QDRANT_URL``,
``WEAVIATE_URL``, ``MILVUS_URI``, and the matching keys as for the vector store
integration tests. Every collection name and document key carries a random
suffix, and the test removes only what it created.
"""

import contextlib
import importlib.util
import re
import zlib
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from uuid import uuid4

import pytest
import pytest_asyncio

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    SourceFormat,
)
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.settings import CutoverJobSettings
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.recipes import CHUNK, ENTITY, HYBRID, Recipe
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb import VectorStore, build_vector_store
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.e2e._artifact import write_artifact


neo4j_missing = importlib.util.find_spec("neo4j") is None

BACKENDS = (
    "qdrant",
    "weaviate",
    "milvus",
)

# Module-scoped fixtures and the tests that use them must share one event loop.
pytestmark = pytest.mark.asyncio(loop_scope="module")

# Text of each document, keyed by title. One chunk each, so a chunk result
# maps back to its document by title.
CORPUS: dict[str, str] = {
    "cardiology": (
        "Warfarin is an anticoagulant that prevents blood clots. "
        "Heparin is also an anticoagulant used in hospitals."
    ),
    "diabetes": (
        "Metformin lowers blood sugar in diabetes. "
        "Insulin is essential for diabetes control."
    ),
    "respiratory": (
        "Salbutamol relieves asthma. Asthma narrows the airways and limits breathing."
    ),
}

DRUGS = ("Warfarin", "Heparin", "Metformin", "Insulin", "Salbutamol")

_TOPICS = (
    {"warfarin", "heparin", "anticoagulant", "clot", "clots"},
    {"metformin", "insulin", "diabetes", "sugar", "glucose"},
    {"salbutamol", "asthma", "airways", "breathing"},
)
_DRUG_SIGNS = {
    "warfarin": 0.5,
    "heparin": -0.5,
    "metformin": 0.5,
    "insulin": -0.5,
    "salbutamol": 0.5,
}
_DRUG_AXIS = 3
# The Neo4j vector index on the shared Chunk label keeps the size of the first
# suite that creates it, and every other suite embeds with four dimensions.
_DIMENSIONS = 4


class _TopicEmbedder(Embedder):
    """Deterministic four-dimensional embedder for topic words and drug names.

    Each topic word adds to one topic axis. A drug name also moves the last axis
    up or down, so two drugs of one topic differ enough that entity resolution
    never sends them to an LLM, yet stay closer to each other than to drugs of
    another topic. A small hash-based jitter separates texts that share words,
    so dense scores never tie and rankings do not depend on backend tie breaking.
    """

    model = "topic"

    async def dimensions(self) -> int:
        """Return the fixed vector size."""
        return _DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per text, identical on every call."""
        return [self._vector(text) for text in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        """Build the vector for one text."""
        vector = [0.01] * _DIMENSIONS
        for word in re.findall(r"\w+", text.lower()):
            for axis, topic in enumerate(_TOPICS):
                if word in topic:
                    vector[axis] += 1.0
            if word in _DRUG_SIGNS:
                vector[_DRUG_AXIS] += _DRUG_SIGNS[word]
        # crc32 is stable across processes, unlike hash().
        crc = zlib.crc32(text.encode())
        return [
            value + ((crc >> (4 * axis)) & 0xF) / 15 * 0.02
            for axis, value in enumerate(vector)
        ]


class _DrugExtractor(Extractor):
    """Extract each known drug name found in a chunk."""

    def __init__(self, label: str) -> None:
        """Bind the graph label the drugs are extracted to."""
        self._label = label

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return one entity per drug name in the chunk text."""
        lowered = chunk.text.lower()
        entities = [
            ExtractedEntity(
                chunk_id=chunk.id,
                label=self._label,
                text=name,
                char_start=lowered.find(name.lower()),
                char_end=lowered.find(name.lower()) + len(name),
            )
            for name in DRUGS
            if name.lower() in lowered
        ]
        return ExtractionResult(entities=entities, relations=[], extractor_name="e2e")


@dataclass
class _Run:
    """One backend with a graph loaded from the corpus."""

    backend: str
    graph: Graph
    engine: SearchEngine
    vector_store: VectorStore
    settings: RetrievalSettings
    keys: dict[str, str]
    graph_store: GraphStore
    label: str
    collections: list[str]


def _title_of_chunk(text: str) -> str:
    """Return the title of the corpus document a chunk text comes from."""
    for title, body in CORPUS.items():
        if text in body or body in text:
            return title
    raise AssertionError(f"chunk text matches no corpus document: {text!r}")


def _names(results: list) -> list[str]:
    """Name each result: entity name, or the title of the chunk's document."""
    return [
        result.item.name
        if isinstance(result.item, Entity)
        else _title_of_chunk(result.item.text)
        for result in results
    ]


async def _drop_created(
    graph_store: GraphStore,
    vector_store: VectorStore,
    collections: Sequence[str],
    label: str,
    keys: Sequence[str],
) -> None:
    """Remove the documents, chunks, entities, and collections one run made."""
    for key in keys:
        await graph_store.execute_write(
            "MATCH (d:Document {document_key: $key}) "
            "OPTIONAL MATCH (d)-[:PART_OF]->(c:Chunk) DETACH DELETE c, d",
            {"key": key},
        )
    await graph_store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
    await drop_schema_for(graph_store, label)
    for name in collections:
        with contextlib.suppress(Exception):
            await vector_store.delete_collection(name)


async def _open_run(backend: str) -> _Run:
    """Connect a backend, open a graph on it, and ingest the corpus."""
    suffix = uuid4().hex[:8]
    label = validate_identifier(f"Drug_{suffix}")
    vector_store = build_vector_store(backend)
    try:
        await vector_store.collection_exists(f"Probe_{suffix}")
    except Exception as exc:  # noqa: BLE001
        await vector_store.close()
        pytest.skip(f"{backend} is not reachable: {type(exc).__name__}")
    settings = RetrievalSettings(
        entity_collection=f"Entities_{suffix}",
        resolved_entity_collection=f"Resolved_{suffix}",
        chunk_collection=f"Chunks_{suffix}",
        community_collection=f"Communities_{suffix}",
    )
    collections = [
        settings.entity_collection,
        settings.resolved_entity_collection,
        settings.chunk_collection,
        settings.community_collection,
    ]
    schema = GraphSchema(
        name="vector_backends",
        version="1",
        entities=[EntityType(label=label, description="A medication.")],
        relations=[],
    )
    graph_store = build_graph_store("neo4j")
    embedder = _TopicEmbedder()
    keys = {title: f"{title}_{suffix}" for title in CORPUS}
    try:
        graph = await Graph.open(
            schema=schema,
            graph_store=graph_store,
            embedder=embedder,
            extractor=_DrugExtractor(label),
            vector_store=vector_store,
            retrieval_settings=settings,
            # Milvus writes are slow enough that one add can outlive the default
            # 60 second lease.
            cutover_settings=CutoverJobSettings(lease_ttl_seconds=600),
        )
    except Exception:
        await vector_store.close()
        raise
    documents = [
        Document(
            text=body,
            title=title,
            uri=keys[title],
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash=f"hash_{title}_{suffix}",
            loader_name="text",
            char_count=len(body),
            line_count=1,
            document_key=keys[title],
        )
        for title, body in CORPUS.items()
    ]
    engine = SearchEngine(
        graph_store=graph_store,
        embedder=embedder,
        vector_store=vector_store,
        settings=settings,
        graph_schema=schema,
    )
    run = _Run(
        backend,
        graph,
        engine,
        vector_store,
        settings,
        keys,
        graph_store,
        label,
        collections,
    )
    try:
        await graph.add(documents=documents, error_policy="raise")
    except Exception:
        await _close_run(run)
        raise
    return run


async def _close_run(run: _Run) -> None:
    """Remove what a run created and close its connections."""
    await _drop_created(
        run.graph_store,
        run.vector_store,
        run.collections,
        run.label,
        list(run.keys.values()),
    )
    await run.graph_store.close()
    await run.vector_store.close()


@pytest_asyncio.fixture(scope="module", loop_scope="module", params=BACKENDS)
async def run(request: pytest.FixtureRequest) -> AsyncGenerator[_Run, None]:
    """Yield one loaded run per backend, shared by the read-only tests.

    Teardown writes the backend's rankings to its artifact, then cleans up.
    """
    loaded = await _open_run(request.param)
    try:
        yield loaded
        rankings = await _rankings(loaded.engine)
        recorded = write_artifact(
            f"vector_backends_{loaded.backend}",
            {"backend": loaded.backend, "corpus": sorted(CORPUS), "rankings": rankings},
        )
        assert recorded["rankings"] == rankings
    finally:
        await _close_run(loaded)


@pytest_asyncio.fixture(loop_scope="module", params=BACKENDS)
async def own_run(request: pytest.FixtureRequest) -> AsyncGenerator[_Run, None]:
    """Yield a private run for a test that changes data."""
    loaded = await _open_run(request.param)
    try:
        yield loaded
    finally:
        await _close_run(loaded)


async def _rankings(engine: SearchEngine) -> dict[str, list[str]]:
    """Return the ordered result names for the queries every backend answers."""
    return {
        "entity_warfarin": _names(await engine.search("warfarin", ENTITY)),
        "entity_insulin": _names(await engine.search("insulin", ENTITY)),
        "chunk_clots": _names(await engine.search("anticoagulant clot", CHUNK)),
        "chunk_asthma": _names(await engine.search("asthma airways", CHUNK)),
        "hybrid_metformin": _names(await engine.search("metformin sugar", HYBRID)),
    }


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestVectorBackendsE2E:
    """The same ingest and search flow on each vector store backend."""

    async def test_search_ranks_expected_names(self, run: _Run) -> None:
        """Each query puts the matching entity or document first."""
        rankings = await _rankings(run.engine)

        assert rankings["entity_warfarin"][:2] == ["Warfarin", "Heparin"]
        assert rankings["entity_insulin"][0] == "Insulin"
        assert rankings["entity_insulin"][1] == "Metformin"
        assert rankings["chunk_clots"][0] == "cardiology"
        assert rankings["chunk_asthma"][0] == "respiratory"
        # A hybrid query mixes entities and chunks; the diabetes ones lead.
        assert rankings["hybrid_metformin"][0] in {"Metformin", "diabetes"}
        assert set(rankings["hybrid_metformin"][:2]) <= {
            "Metformin",
            "Insulin",
            "diabetes",
        }
        assert set(rankings["entity_warfarin"]) == set(DRUGS)
        assert set(rankings["chunk_clots"]) == set(CORPUS)

    async def test_hybrid_has_no_duplicates_and_covers_both_methods(
        self, run: _Run
    ) -> None:
        """HYBRID returns every entity and chunk once, with both methods present."""
        results = await run.engine.search("anticoagulant warfarin", HYBRID)

        keys = [result.identity_key for result in results]
        assert len(keys) == len(set(keys))
        entity_names = {r.item.name for r in results if isinstance(r.item, Entity)}
        chunk_titles = {
            _title_of_chunk(r.item.text) for r in results if isinstance(r.item, Chunk)
        }
        assert entity_names == set(DRUGS)
        assert chunk_titles == set(CORPUS)
        entity_only = await run.engine.search("anticoagulant warfarin", ENTITY)
        chunk_only = await run.engine.search("anticoagulant warfarin", CHUNK)
        assert len(results) == len(entity_only) + len(chunk_only)

    @pytest.mark.parametrize("limit", [1, 2])
    async def test_limit_caps_results_and_keeps_the_top_hit(
        self, run: _Run, limit: int
    ) -> None:
        """A smaller limit returns a prefix of the full ranking."""
        full = _names(await run.engine.search("warfarin", ENTITY))
        capped = _names(
            await run.engine.search("warfarin", Recipe(methods=["entity"], limit=limit))
        )

        assert capped == full[:limit]

    async def test_limit_zero_returns_nothing(self, run: _Run) -> None:
        """A zero limit is an empty result, not an error."""
        assert (
            await run.engine.search("warfarin", Recipe(methods=["chunk"], limit=0))
            == []
        )

    async def test_label_filter_with_no_match_returns_nothing(self, run: _Run) -> None:
        """A label filter that no entity has gives an empty result, not a hit."""
        results = await run.engine.search(
            "warfarin", ENTITY, filters=SearchFilters(labels=["NoSuchLabel"])
        )

        assert results == []

    async def test_off_topic_query_has_low_dense_similarity(self, run: _Run) -> None:
        """Raw dense scores separate an on-topic query from an off-topic one.

        Fused scores are rank-normalized on some backends, so the top hit
        always scores 1.0. Dense search gives comparable cosine values.
        """
        embedder = _TopicEmbedder()
        collection = run.settings.entity_collection
        top = {}
        for query in ("warfarin", "quantum chromodynamics"):
            hits = await run.vector_store.search(
                collection, await embedder.embed_one(query), limit=5
            )
            top[query] = max(hit.score for hit in hits)

        assert top["warfarin"] > 0.9
        assert top["quantum chromodynamics"] < top["warfarin"] - 0.2

    async def test_delete_document_removes_its_vectors(self, own_run: _Run) -> None:
        """Deleting a document drops its chunk and its drugs from search."""
        run = own_run
        entity_before = await run.vector_store.count(run.settings.entity_collection)
        chunk_before = await run.vector_store.count(run.settings.chunk_collection)
        assert entity_before == len(DRUGS)
        assert chunk_before == len(CORPUS)

        outcome = await run.graph.delete_document(run.keys["cardiology"])

        assert outcome.no_op is False
        assert outcome.chunks_closed == 1
        entity_names = _names(await run.engine.search("warfarin", ENTITY))
        assert "Warfarin" not in entity_names
        assert "Heparin" not in entity_names
        assert set(entity_names) == {"Metformin", "Insulin", "Salbutamol"}
        chunk_names = _names(await run.engine.search("anticoagulant clot", CHUNK))
        assert "cardiology" not in chunk_names
        assert set(chunk_names) == {"diabetes", "respiratory"}
        assert await run.vector_store.count(run.settings.entity_collection) == 3

    async def test_deleting_an_unknown_document_is_a_no_op(self, run: _Run) -> None:
        """An unknown document key leaves every collection unchanged."""
        outcome = await run.graph.delete_document(f"missing_{uuid4().hex[:8]}")

        assert outcome.no_op is True
        assert await run.vector_store.count(run.settings.chunk_collection) == 3
