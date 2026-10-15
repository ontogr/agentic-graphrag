"""E2E test of the default agent's tools over a real seeded graph, with no LLM.

Seeds a small connected graph through ``Graph.add`` and a second, disconnected
graph in another document. It then calls the tools ``make_core_tools`` returns
the way the agent does (``tool.ainvoke``) and checks what the agent would read:

- discovery and entity search name the expected passages and entities;
- a document scope hides the other document's passages and entities, and a
  fetch cannot read an id from outside the scope;
- exploration follows relations within the connected component only;
- a tool-call budget ends further calls with a fixed message.
"""

import hashlib
import importlib.util
import json
import re
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.messages import ToolMessage

from agrag.agents.middleware import RunState, TaskEventMiddleware
from agrag.agents.tools.core import make_core_tools
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    SourceFormat,
)
from agrag.common.data_models.entity_search import EntityResult, ExplorationResult
from agrag.common.data_models.evidence import (
    DiscoveryResult,
    FetchOutcome,
    FetchStatus,
)
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.memory import DecisionMemory, TaskMemory
from agrag.retrieval.methods.traversal import extract_entity_ids
from agrag.retrieval.rerank.node_distance import node_distance_rerank
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration._schema_cleanup import drop_schema_for


neo4j_missing = importlib.util.find_spec("neo4j") is None

_KEYWORD_VECTORS = {
    "alice": [3.0, 1.0, -2.0, 1.0],
    "bob": [1.0, -3.0, 1.0, 2.0],
    "zed": [1.0, 1.0, 2.0, 0.0],
    "acme": [2.0, -1.0, 1.0, 3.0],
    "globex": [1.0, 3.0, 1.0, 0.0],
    "zeta": [1.0, 1.0, -4.0, 1.0],
    "paris": [1.0, -2.0, 0.0, 2.0],
}

_DOC_MAIN = (
    "Alice founded Acme. Bob works at Acme. Acme acquired Globex. "
    "Globex is located in Paris."
)
_DOC_OTHER = "Zed founded Zeta."

# Keyword -> (entity label kind, display name).
_ENTITY_KIND = {
    "alice": ("person", "Alice"),
    "bob": ("person", "Bob"),
    "zed": ("person", "Zed"),
    "acme": ("org", "Acme"),
    "globex": ("org", "Globex"),
    "zeta": ("org", "Zeta"),
    "paris": ("place", "Paris"),
}

# (source keyword, relation label, target keyword). A triple applies to a
# chunk that mentions both keywords.
_TRIPLES = (
    ("alice", "FOUNDED", "acme"),
    ("bob", "WORKS_AT", "acme"),
    ("acme", "ACQUIRED", "globex"),
    ("globex", "LOCATED_IN", "paris"),
    ("zed", "FOUNDED", "zeta"),
)


class _KeywordEmbedder(Embedder):
    """Give each known name its own direction, so search ranks are exact.

    The shared chunk vector index has 4 dimensions, so the vectors are 4-wide.
    Names of the same label are orthogonal, so resolution finds no duplicates.
    The vectors are off-axis so that vectors other suites left in the shared
    indexes rank below an exact name match. A text mentioning several names
    gets the sum of their vectors.
    """

    model = "keyword"

    async def dimensions(self) -> int:
        """Return 4 dimensions, matching the shared chunk index."""
        return FAKE_EMBEDDING_DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the summed keyword vectors, or a uniform vector for none.

        Neo4j rejects an all-zero query vector, so text with no keyword gets
        a neutral vector.
        """
        vectors: list[list[float]] = []
        for text in texts:
            words = set(re.findall(r"[a-z]+", text.lower()))
            total = [0.0] * 4
            for keyword, vector in _KEYWORD_VECTORS.items():
                if keyword in words:
                    total = [a + b for a, b in zip(total, vector, strict=True)]
            vectors.append(total if any(total) else [1.0] * 4)
        return vectors


class _TripleExtractor(Extractor):
    """Extract the known names and relation triples a chunk mentions."""

    def __init__(self, labels: dict[str, str]) -> None:
        """Store the graph label to use for each entity kind."""
        self._labels = labels

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return every known name in the chunk and the triples between them."""
        lowered = chunk.text.lower()
        entities: list[ExtractedEntity] = []
        index_by_keyword: dict[str, int] = {}
        for keyword, (kind, name) in _ENTITY_KIND.items():
            match = re.search(rf"\b{keyword}\b", lowered)
            if match is None:
                continue
            index_by_keyword[keyword] = len(entities)
            entities.append(
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label=self._labels[kind],
                    text=name,
                    char_start=match.start(),
                    char_end=match.end(),
                )
            )
        relations = [
            ExtractedRelation(
                chunk_id=chunk.id,
                label=label,
                source_index=index_by_keyword[source],
                target_index=index_by_keyword[target],
            )
            for source, label, target in _TRIPLES
            if source in index_by_keyword and target in index_by_keyword
        ]
        return ExtractionResult(
            entities=entities, relations=relations, extractor_name="e2e"
        )


def _document(uri: str, text: str) -> Document:
    """Build a prose document with a content-derived hash."""
    return Document(
        text=text,
        title=uri,
        uri=uri,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        loader_name="text",
        char_count=len(text),
    )


def _names(found: EntityResult, suffix: str) -> list[str]:
    """Return the names of this test's entities in a search result, in order.

    Entities that other suites left in the shared indexes can appear in an
    unscoped search. Only labels ending in this test's suffix are kept.
    """
    return [hit.name for hit in found.hits if hit.label.endswith(f"_{suffix}")]


async def _core_tools(
    env: dict, scope_keys: list[str], task: str, *, max_tool_calls: int = 50
) -> list[Any]:
    """Build the default agent's tools over the seeded graph for one scope."""
    store: GraphStore = env["store"]
    memory = TaskMemory(store, project_id=env["project_id"], agent_id="e2e")
    await memory.create_task(task, "Read the seeded graph.")
    decisions = DecisionMemory(store, project_id=env["project_id"], agent_id="e2e")
    tools, _ = make_core_tools(
        graph_store=store,
        embedder=env["embedder"],
        scope=frozenset(scope_keys),
        task_name=task,
        memory=memory,
        decisions=decisions,
        fetched_ids=[],
        fetched_outcomes=[],
        max_chars=12_000,
        max_tool_calls=max_tool_calls,
    )
    return tools


async def _cleanup_task_memory(store: GraphStore, project_id: str) -> None:
    """Delete the tasks, events and steps that the seeded tools wrote."""
    params = {"project_id": project_id}
    await store.execute_write(
        "MATCH (t:MemoryTask {project_id: $project_id}) "
        "OPTIONAL MATCH (t)-[:HAS_EVENT|HAS_STEP]->(child) "
        "DETACH DELETE child, t",
        params,
    )
    await store.execute_write(
        "MATCH (r:MemoryRequest {project_id: $project_id}) DETACH DELETE r", params
    )
    await store.execute_write(
        "MATCH (p:MemoryProject {project_id: $project_id}) DETACH DELETE p", params
    )


def _tool(tools: list, name: str):  # type: ignore[no-untyped-def]
    """Return the tool with the given name."""
    return next(tool for tool in tools if tool.name == name)


async def _snapshot(
    store: GraphStore, labels: list[str], document_ids: list[str]
) -> dict[str, object]:
    """Read every node, relationship and chunk this test owns."""
    nodes = await store.execute_read(
        "MATCH (n) WHERE any(l IN labels(n) WHERE l IN $labels) "
        "RETURN n.name AS name, n.id AS id ORDER BY name, id",
        {"labels": labels},
    )
    relations = await store.execute_read(
        "MATCH (a)-[r]->(b) WHERE any(l IN labels(a) WHERE l IN $labels) "
        "RETURN type(r) AS type, a.name AS source, b.name AS target "
        "ORDER BY type, source, target",
        {"labels": labels},
    )
    chunks = await store.execute_read(
        "MATCH (c:Chunk) WHERE c.document_id IN $ids RETURN count(c) AS total",
        {"ids": document_ids},
    )
    return {"nodes": nodes, "relations": relations, "chunks": chunks}


async def _cleanup(
    store: GraphStore,
    labels: list[str],
    document_ids: list[str],
) -> None:
    """Delete only the rows this test wrote, found by label and id."""
    await store.execute_write(
        "MATCH (n) WHERE any(l IN labels(n) WHERE l IN $labels) DETACH DELETE n",
        {"labels": labels},
    )
    await store.execute_write(
        "MATCH (c:Chunk) WHERE c.document_id IN $ids DETACH DELETE c",
        {"ids": document_ids},
    )
    await store.execute_write(
        "MATCH (d:Document) WHERE d.id IN $ids DETACH DELETE d",
        {"ids": document_ids},
    )


@asynccontextmanager
async def _seed_graph(*, one_add_call: bool) -> AsyncGenerator[dict, None]:
    """Seed the connected and the disconnected documents; clean up after.

    Args:
        one_add_call: Add both documents in one ``Graph.add`` call. When
            False, each document gets its own call.
    """
    suffix = uuid4().hex[:8]
    labels = {
        "person": validate_identifier(f"Person_{suffix}"),
        "org": validate_identifier(f"Org_{suffix}"),
        "place": validate_identifier(f"Place_{suffix}"),
    }
    schema = GraphSchema(
        name="agent_tools_e2e",
        version="1",
        entities=[
            EntityType(label=labels["person"], description="A person."),
            EntityType(label=labels["org"], description="An organization."),
            EntityType(label=labels["place"], description="A place."),
        ],
        relations=[
            RelationType(
                label="FOUNDED",
                description="A person founded an organization.",
                patterns=[(labels["person"], labels["org"])],
            ),
            RelationType(
                label="WORKS_AT",
                description="A person works at an organization.",
                patterns=[(labels["person"], labels["org"])],
            ),
            RelationType(
                label="ACQUIRED",
                description="An organization acquired another.",
                patterns=[(labels["org"], labels["org"])],
            ),
            RelationType(
                label="LOCATED_IN",
                description="An organization is located in a place.",
                patterns=[(labels["org"], labels["place"])],
            ),
        ],
    )
    main = _document(f"e2e://agent_tools/{suffix}/main", _DOC_MAIN)
    other = _document(f"e2e://agent_tools/{suffix}/other", _DOC_OTHER)
    # Chunks and the Document node share one id, derived from the document key.
    document_ids = [
        str(Document.node_id_for(document_key=doc.resolved_document_key))
        for doc in (main, other)
    ]
    embedder = _KeywordEmbedder()
    store = build_graph_store("neo4j")
    graph = await Graph.open(
        schema=schema,
        graph_store=store,
        embedder=embedder,
        extractor=_TripleExtractor(labels),
    )
    all_labels = list(labels.values())
    project_id = f"e2e-{suffix}"
    try:
        if one_add_call:
            await graph.add(documents=[main, other], error_policy="skip")
        else:
            await graph.add(documents=[main], error_policy="skip")
            await graph.add(documents=[other], error_policy="skip")
        yield {
            "store": store,
            "embedder": embedder,
            "schema": schema,
            "labels": labels,
            "suffix": suffix,
            "all_labels": all_labels,
            "main_id": document_ids[0],
            "other_id": document_ids[1],
            "main_key": main.resolved_document_key,
            "other_key": other.resolved_document_key,
            "project_id": project_id,
            "document_ids": document_ids,
        }
    finally:
        await _cleanup_task_memory(store, project_id)
        await _cleanup(store, all_labels, document_ids)
        await drop_schema_for(store, *all_labels)
        await store.close()


@pytest.fixture
async def seeded() -> AsyncGenerator[dict, None]:
    """Seed the graph with one add call per document."""
    async with _seed_graph(one_add_call=False) as env:
        yield env


def _engine(env: dict, **settings: object) -> SearchEngine:
    """Build a SearchEngine over the seeded graph."""
    return SearchEngine(
        graph_store=env["store"],
        embedder=env["embedder"],
        settings=RetrievalSettings(**settings),
        graph_schema=env["schema"],
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
async def test_core_tools_read_and_scope_the_seeded_graph(seeded: dict) -> None:
    """Search, fetch and explore honour the document scope and the tool budget."""
    env = seeded
    suffix = env["suffix"]
    labels = env["labels"]
    full = await _core_tools(env, [env["main_key"], env["other_key"]], "full-scope")
    main = await _core_tools(env, [env["main_key"]], "main-scope")

    alice = DiscoveryResult.model_validate_json(
        await _tool(main, "discover_evidence").ainvoke({"query": "Alice"})
    )
    fetched = FetchOutcome.model_validate(
        json.loads(
            await _tool(main, "fetch_evidence").ainvoke(
                {"evidence_ids": [alice.hits[0].evidence_id]}
            )
        )[0]
    )
    assert fetched.status is FetchStatus.OK
    assert "Alice founded Acme" in (fetched.text or "")

    zed_in_full = DiscoveryResult.model_validate_json(
        await _tool(full, "discover_evidence").ainvoke({"query": "Zed"})
    )
    zed_hit = next(hit for hit in zed_in_full.hits if "Zed" in hit.snippet)
    zed_from_main = FetchOutcome.model_validate(
        json.loads(
            await _tool(main, "fetch_evidence").ainvoke(
                {"evidence_ids": [zed_hit.evidence_id]}
            )
        )[0]
    )
    assert zed_from_main.status is not FetchStatus.OK
    assert zed_from_main.text is None

    orgs = EntityResult.model_validate_json(
        await _tool(full, "find_entities").ainvoke(
            {"query": "Acme", "labels": [labels["org"]]}
        )
    )
    assert sorted(_names(orgs, suffix)) == ["Acme", "Globex", "Zeta"]
    scoped = EntityResult.model_validate_json(
        await _tool(main, "find_entities").ainvoke(
            {"query": "Zed", "labels": list(labels.values())}
        )
    )
    assert not {"Zed", "Zeta"} & set(_names(scoped, suffix))
    scoped_alice = EntityResult.model_validate_json(
        await _tool(main, "find_entities").ainvoke(
            {"query": "Alice", "labels": list(labels.values())}
        )
    )
    assert "Alice" in _names(scoped_alice, suffix)

    alice_entity = next(
        hit
        for hit in EntityResult.model_validate_json(
            await _tool(full, "find_entities").ainvoke(
                {"query": "Alice", "labels": [labels["person"]]}
            )
        ).hits
        if hit.name == "Alice"
    )
    explored = ExplorationResult.model_validate_json(
        await _tool(full, "explore").ainvoke(
            {"entity_id": alice_entity.entity_id, "depth": 2}
        )
    )
    reached = {node.name for node in explored.nodes}
    assert {"Acme", "Bob", "Globex"} <= reached
    assert not {"Zed", "Zeta"} & reached

    limited = await _core_tools(env, [env["main_key"]], "budget", max_tool_calls=2)
    budget_memory = TaskMemory(
        env["store"], project_id=env["project_id"], agent_id="e2e"
    )
    budget_middleware = TaskEventMiddleware(
        budget_memory, "budget", RunState(max_tool_calls=2)
    )

    async def call_discover(call_id: str) -> Any:
        call = {
            "name": "discover_evidence",
            "args": {"query": "Alice"},
            "id": call_id,
        }
        request = SimpleNamespace(tool_call=call)

        async def invoke_tool(_request: Any) -> Any:
            return await _tool(limited, "discover_evidence").ainvoke(call["args"])

        return await budget_middleware.awrap_tool_call(request, invoke_tool)

    for index in range(2):
        assert isinstance(await call_discover(f"budget-{index}"), str)
    rejected = await call_discover("budget-3")
    assert isinstance(rejected, ToolMessage)
    assert rejected.status == "error"
    assert rejected.content == "Tool budget exhausted."


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
async def test_node_distance_rerank_puts_the_seed_entity_first(
    seeded: dict,
) -> None:
    """A candidate that is its own seed has distance zero and ranks first."""
    env = seeded
    engine = _engine(env)
    seed = await engine.find_entity("Alice")
    acme = await engine.find_entity("Acme")
    assert seed and acme
    reranked = await node_distance_rerank(
        [acme, seed],
        graph_store=env["store"],
        seed_ids=extract_entity_ids([seed]),
    )
    assert [r.item.name for r in reranked] == ["Alice", "Acme"]  # type: ignore[union-attr]


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
async def test_one_add_call_with_two_documents_keeps_every_relation() -> None:
    """Relations extracted per chunk keep their endpoints in a joint add."""
    async with _seed_graph(one_add_call=True) as env:
        snapshot = await _snapshot(env["store"], env["all_labels"], env["document_ids"])
    relations = snapshot["relations"]
    assert isinstance(relations, list)
    assert [(r["type"], r["source"], r["target"]) for r in relations] == [
        ("ACQUIRED", "Acme", "Globex"),
        ("FOUNDED", "Alice", "Acme"),
        ("FOUNDED", "Zed", "Zeta"),
        ("LOCATED_IN", "Globex", "Paris"),
        ("WORKS_AT", "Bob", "Acme"),
    ]
