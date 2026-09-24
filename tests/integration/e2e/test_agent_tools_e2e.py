"""E2E test of the agent tool layer over a real seeded graph, with no LLM.

Seeds a small connected graph through ``Graph.add`` and a second, disconnected
graph in another document. It then calls the tools ``make_tools`` returns the
way the agent does (``tool.ainvoke``) and checks what the agent would read:

- search and look-up tools name the expected entities and passages;
- a caller scope (labels, documents, relation types, properties) hides
  out-of-scope data, and a tool argument cannot widen the scope;
- traversal follows direction and depth and never reaches the disconnected
  component;
- the node-distance reranker puts closer entities first;
- the generated-Cypher tool, with a fixed query generator, runs read queries
  and refuses write queries and CALL procedures with side effects, and the
  graph is unchanged afterwards.

The run writes ``reports/e2e/agent_tools.json``. The test reads it back and
asserts on the content. Labels, document keys and ids carry a random suffix in
the database, but the artifact holds stable names only.
"""

import ast
import hashlib
import importlib.util
import re
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from agrag.agents.ledger import Ledger
from agrag.agents.tools import make_tools
from agrag.agents.tools.search import SCOPE_DENIED
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    SourceFormat,
)
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType
from agrag.cypher.entities import validate_identifier
from agrag.cypher.safety import UnsafeCypherError, reject_write_cypher
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.traversal import extract_entity_ids
from agrag.retrieval.recipes import Recipe
from agrag.retrieval.rerank.node_distance import node_distance_rerank
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings
from tests.integration.e2e._artifact import write_artifact


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
_ENTITY_LINE = re.compile(r"^\[E\d+\] Entity: (.+) \((\w+)\)$", re.MULTILINE)

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
        return 4

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


def _names(rendered: str, suffix: str) -> list[str]:
    """Return the names of this test's entities a tool rendered, in order.

    Entities that other suites left in the shared indexes can appear in an
    unscoped search. Only labels ending in this test's suffix are kept.
    """
    return [
        name
        for name, label in _ENTITY_LINE.findall(rendered)
        if label.endswith(f"_{suffix}")
    ]


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
    injected_label = validate_identifier(f"Injected_{suffix}")
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
    all_labels = [*labels.values(), injected_label]
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
            "injected_label": injected_label,
            "all_labels": all_labels,
            "main_id": document_ids[0],
            "other_id": document_ids[1],
            "document_ids": document_ids,
        }
    finally:
        await _cleanup(store, all_labels, document_ids)
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
async def test_agent_tools_over_seeded_graph(  # noqa: PLR0915
    seeded: dict,
) -> None:
    """Tools read, scope, traverse, rerank and query the graph correctly."""
    env = seeded
    labels = env["labels"]
    suffix = env["suffix"]

    def names(rendered: str) -> list[str]:
        return _names(rendered, suffix)

    store: GraphStore = env["store"]
    engine = _engine(env)
    tools = make_tools(engine, Ledger())
    record: dict[str, object] = {}

    async def call(name: str, **args: object) -> str:
        return await _tool(tools, name).ainvoke(args)

    # Search and look-up: the tool names the entity the query is about.
    lookup = await call("look_up_entity", query="Acme")
    assert names(lookup)[0] == "Acme"
    orgs_only = await call("look_up_entity", query="Acme", labels=[labels["org"]])
    assert sorted(names(orgs_only)) == ["Acme", "Globex", "Zeta"]
    record["look_up_entity"] = {
        "first": names(lookup)[0],
        "org_labelled": sorted(names(orgs_only)),
    }

    # Relationship listing.
    listed = await call("list_relationship_types", entity="Acme")
    assert listed.splitlines()[-1] == "Relationship types: ACQUIRED, FOUNDED, WORKS_AT"
    only_founded = await call(
        "list_relationship_types", entity="Acme", relation_type_filter="FOUNDED"
    )
    assert only_founded.splitlines()[-1] == "Relationship types: FOUNDED"
    absent = await call(
        "list_relationship_types", entity="Acme", relation_type_filter="LOCATED_IN"
    )
    assert absent.splitlines()[-1] == "No relationships found."
    record["relationship_types_of_acme"] = ["ACQUIRED", "FOUNDED", "WORKS_AT"]

    # One relationship type, with direction.
    directions: dict[str, list[str]] = {}
    for entity, relation, direction, expected in (
        ("Acme", "WORKS_AT", "incoming", ["Bob"]),
        ("Acme", "WORKS_AT", "outgoing", []),
        ("Acme", "ACQUIRED", "outgoing", ["Globex"]),
        ("Acme", "ACQUIRED", "incoming", []),
        ("Acme", "FOUNDED", "both", ["Alice"]),
    ):
        rendered = await call(
            "find_related_entities",
            entity=entity,
            relation_type=relation,
            direction=direction,
        )
        assert names(rendered) == expected, (entity, relation, direction)
        if not expected:
            assert rendered == "No results found."
        directions[f"{entity}:{relation}:{direction}"] = names(rendered)
    record["find_related_entities"] = directions

    # Multi-hop traversal reaches the second hop, and only the connected one.
    hops: dict[str, list[str]] = {}
    for entity, direction, depth, expected in (
        ("Alice", "both", 1, ["Acme"]),
        ("Alice", "both", 2, ["Acme", "Bob", "Globex", "Paris"]),
        ("Alice", "both", 3, ["Acme", "Bob", "Globex", "Paris"]),
        ("Alice", "outgoing", 2, ["Acme", "Globex"]),
        ("Alice", "incoming", 3, []),
        ("Globex", "incoming", 2, ["Acme", "Alice", "Bob"]),
        ("Zed", "both", 5, ["Zeta"]),
    ):
        rendered = await call(
            "traverse_from_entity", entity=entity, direction=direction, depth=depth
        )
        assert sorted(names(rendered)) == expected, (entity, direction, depth)
        hops[f"{entity}:{direction}:{depth}"] = sorted(names(rendered))
    for key, reached in hops.items():
        if not key.startswith("Zed"):
            assert not {"Zed", "Zeta"} & set(reached), key
    typed = await call(
        "traverse_from_entity",
        entity="Alice",
        relation_type="FOUNDED",
        direction="outgoing",
        depth=3,
    )
    assert names(typed) == ["Acme"]
    record["traverse_from_entity"] = hops

    described = await call("describe_entity", entity="Acme")
    assert described.splitlines()[0].startswith("[E") and "Acme" in described
    assert labels["org"] in described

    # Scope: a label scope hides other types, even on the path to a neighbour.
    person_tools = make_tools(
        engine, Ledger(), filters=SearchFilters(labels=[labels["person"]])
    )
    assert "query_graph_directly" not in {tool.name for tool in person_tools}
    scoped_lookup = await _tool(person_tools, "look_up_entity").ainvoke(
        {"query": "Acme"}
    )
    assert sorted(names(scoped_lookup)) == ["Alice", "Bob", "Zed"]
    widened = await _tool(person_tools, "look_up_entity").ainvoke(
        {"query": "Acme", "labels": [labels["org"]]}
    )
    assert widened == SCOPE_DENIED
    scoped_hops = await _tool(person_tools, "traverse_from_entity").ainvoke(
        {"entity": "Bob", "depth": 2}
    )
    assert names(scoped_hops) == ["Alice"]

    # Scope: a document scope hides the other document's passages and
    # neighbours, and a tool argument cannot select the other document.
    doc_tools = make_tools(
        engine, Ledger(), filters=SearchFilters(document_ids=[env["main_id"]])
    )
    scoped_passages = await _tool(doc_tools, "search_source_text").ainvoke(
        {"query": "Zed"}
    )
    assert "Zed" not in scoped_passages
    main_passages = await _tool(doc_tools, "search_source_text").ainvoke(
        {"query": "Alice"}
    )
    assert "Alice founded Acme" in main_passages
    doc_widened = await _tool(doc_tools, "search_source_text").ainvoke(
        {"query": "Zed", "document_ids": [env["other_id"]]}
    )
    assert doc_widened == SCOPE_DENIED
    other_tools = make_tools(
        engine, Ledger(), filters=SearchFilters(document_ids=[env["other_id"]])
    )
    other_passages = await _tool(other_tools, "search_source_text").ainvoke(
        {"query": "Alice"}
    )
    assert "Alice" not in other_passages
    own_passages = await _tool(other_tools, "search_source_text").ainvoke(
        {"query": "Zed"}
    )
    assert "Zed founded Zeta" in own_passages
    other_hops = await _tool(other_tools, "traverse_from_entity").ainvoke(
        {"entity": "Zed", "depth": 3}
    )
    assert names(other_hops) == ["Zeta"]

    # Scope: a relation type allowlist refuses a call outside it.
    founded_tools = make_tools(
        engine, Ledger(), filters=SearchFilters(relation_types=["FOUNDED"])
    )
    refused = await _tool(founded_tools, "find_related_entities").ainvoke(
        {"entity": "Acme", "relation_type": "ACQUIRED"}
    )
    assert refused == SCOPE_DENIED
    allowed_types = await _tool(founded_tools, "list_relationship_types").ainvoke(
        {"entity": "Acme"}
    )
    assert allowed_types.splitlines()[-1] == "Relationship types: FOUNDED"
    allowed_hops = await _tool(founded_tools, "traverse_from_entity").ainvoke(
        {"entity": "Alice", "depth": 3}
    )
    assert names(allowed_hops) == ["Acme"]

    # Scope: a property scope makes name resolution pick an in-scope entity, so
    # a name outside the scope never becomes a traversal start.
    alice_tools = make_tools(
        engine,
        Ledger(),
        filters=SearchFilters(
            labels=list(labels.values()), properties={"name": "Alice"}
        ),
    )
    resolved_in_scope = await _tool(alice_tools, "describe_entity").ainvoke(
        {"entity": "Acme"}
    )
    assert f"Alice ({labels['person']})" in resolved_in_scope
    assert "Acme" not in resolved_in_scope
    found = await _tool(alice_tools, "describe_entity").ainvoke({"entity": "Alice"})
    assert f"Alice ({labels['person']})" in found
    record["scope"] = {
        "label_scope_lookup": sorted(names(scoped_lookup)),
        "label_scope_widen": "refused",
        "label_scope_traverse_bob_depth2": names(scoped_hops),
        "document_scope_excludes_other_document": True,
        "document_scope_widen": "refused",
        "relation_scope_widen": "refused",
        "property_scope_resolves_only_in_scope": True,
    }

    # Node-distance rerank: closer to the seed ranks higher.
    seed = await engine.find_entity("Alice")
    zed = await engine.find_entity("Zed")
    globex = await engine.find_entity("Globex")
    acme = await engine.find_entity("Acme")
    assert seed and zed and globex and acme
    candidates = [zed, globex, acme]
    reranked = await node_distance_rerank(
        candidates, graph_store=store, seed_ids=extract_entity_ids([seed])
    )
    assert [r.item.name for r in reranked] == ["Acme", "Globex", "Zed"]  # type: ignore[union-attr]
    unchanged = await node_distance_rerank(candidates, graph_store=store, seed_ids=[])
    assert [r.item.name for r in unchanged] == ["Zed", "Globex", "Acme"]  # type: ignore[union-attr]
    rerank_engine = _engine(env, node_distance_seed_top_k=1)
    ranked = await rerank_engine.search(
        "Alice",
        Recipe(methods=["entity"], reranker="node_distance", limit=10),
        filters=SearchFilters(labels=list(labels.values())),
    )
    order = [
        r.item.name  # type: ignore[union-attr]
        for r in ranked
        if r.item.name != "Alice"  # type: ignore[union-attr]
    ]
    assert order[0] == "Acme"
    # Chunk nodes join every entity of a document, so the rest of the
    # connected document is at distance 2 and the other document is unreachable.
    assert sorted(order[1:4]) == ["Bob", "Globex", "Paris"]
    assert sorted(order[4:]) == ["Zed", "Zeta"]
    record["node_distance"] = {
        "direct_rerank": [r.item.name for r in reranked],  # type: ignore[union-attr]
        "engine_rerank_tiers_without_seed": [
            [order[0]],
            sorted(order[1:4]),
            sorted(order[4:]),
        ],
    }

    # Generated Cypher with a fixed generator.
    org, person = labels["org"], labels["person"]
    before = await _snapshot(store, env["all_labels"], env["document_ids"])

    async def ask(cypher: str | list[str], tool_engine: SearchEngine = engine) -> str:
        generator = (
            AsyncMock(side_effect=cypher)
            if isinstance(cypher, list)
            else AsyncMock(return_value=cypher)
        )
        cypher_tools = make_tools(tool_engine, Ledger())
        with patch("agrag.llm.baml_client.b.GenerateCypherQuery", generator):
            return await _tool(cypher_tools, "query_graph_directly").ainvoke(
                {"query": "a question"}
            )

    read_orgs = await ask(f"MATCH (n:{org}) RETURN n")
    assert sorted(names(read_orgs)) == ["Acme", "Globex", "Zeta"]
    fenced = await ask(f"```cypher\nMATCH (n:{org}) RETURN n\n```")
    assert sorted(names(fenced)) == ["Acme", "Globex", "Zeta"]
    recovered = await ask([f"MATCH (n:{org} RETURN n", f"MATCH (n:{org}) RETURN n"])
    assert sorted(names(recovered)) == ["Acme", "Globex", "Zeta"]
    founders = await ask(
        f"MATCH (a:{person})-[:FOUNDED]->(b:{org}) "
        "RETURN a.name AS founder, b.name AS company ORDER BY founder"
    )
    founder_rows = [
        ast.literal_eval(match) for match in re.findall(r"Value: (\{.*\})", founders)
    ]
    assert founder_rows == [
        {"founder": "Alice", "company": "Acme"},
        {"founder": "Zed", "company": "Zeta"},
    ]
    commented = await ask(
        f"MATCH (n:{org}) /* CREATE */ WHERE n.name <> 'it\\'s DELETE' "
        "RETURN n // MERGE"
    )
    assert sorted(names(commented)) == ["Acme", "Globex", "Zeta"]
    quoted_keyword = await ask(
        f"MATCH (n:{org}) WHERE n.name = 'CREATE or DELETE' RETURN n"
    )
    assert quoted_keyword == "No results found."
    capped = await ask(
        f"MATCH (n:{org}) RETURN n.name AS name",
        _engine(env, text2cypher_max_rows=2),
    )
    assert len(re.findall(r"Value: ", capped)) == 2
    uncapped = await ask(f"MATCH (n:{org}) RETURN n.name AS name")
    assert len(re.findall(r"Value: ", uncapped)) == 3

    counts: dict[str, int] = {}
    for kind in ("person", "org", "place"):
        rendered = await ask(f"MATCH (n:{labels[kind]}) RETURN count(n) AS total")
        counts[kind] = ast.literal_eval(re.findall(r"Value: (\{.*\})", rendered)[0])[
            "total"
        ]
    assert counts == {"person": 3, "org": 3, "place": 1}
    total = await call(
        "compute_over_evidence", operation="sum", values=list(counts.values())
    )
    assert total == "7"
    assert (
        await call(
            "compute_over_evidence",
            operation="compare",
            values=[counts["person"], counts["place"]],
            compare_op="gt",
        )
        == "true"
    )
    assert (
        await call("compute_over_evidence", operation="count", values=[1, 2, 3]) == "3"
    )
    assert "exactly two" in await call(
        "compute_over_evidence", operation="compare", values=[1, 2, 3], compare_op="eq"
    )

    injected = env["injected_label"]
    write_queries = {
        "create": f"CREATE (n:{injected} {{name: 'Injected'}}) RETURN n",
        "merge": f"MERGE (n:{injected} {{name: 'Injected'}}) RETURN n",
        "detach_delete": f"MATCH (n:{org}) DETACH DELETE n",
        "lowercase_delete": f"match (n:{org}) delete n",
        "set": f"MATCH (n:{org}) SET n.name = 'Renamed' RETURN n",
        "remove": f"MATCH (n:{org}) REMOVE n.name",
        "call_side_effect": f"CALL db.createLabel('{injected}')",
        "call_subquery": f"CALL {{ CREATE (n:{injected}) }} RETURN 1",
    }
    refusals: dict[str, str] = {}
    for name, cypher in write_queries.items():
        with pytest.raises(UnsafeCypherError):
            reject_write_cypher(cypher)
        outcome = await ask(cypher)
        assert outcome == "No results found.", name
        refusals[name] = "refused"
    unknown_label = await ask(f"MATCH (n:Ghost_{injected}) RETURN n")
    assert unknown_label == "No results found."

    after = await _snapshot(store, env["all_labels"], env["document_ids"])
    assert after == before
    assert len(after["nodes"]) == 7  # type: ignore[arg-type]
    assert len(after["relations"]) == 5  # type: ignore[arg-type]
    record["text2cypher"] = {
        "org_names": sorted(names(read_orgs)),
        "founder_rows": founder_rows,
        "row_cap_2": 2,
        "counts": counts,
        "compute_sum": total,
        "write_queries": refusals,
        "unknown_label_rows": 0,
        "nodes_before": len(before["nodes"]),  # type: ignore[arg-type]
        "nodes_after": len(after["nodes"]),  # type: ignore[arg-type]
        "relations_before": len(before["relations"]),  # type: ignore[arg-type]
        "relations_after": len(after["relations"]),  # type: ignore[arg-type]
    }

    artifact = write_artifact("agent_tools", record)
    assert artifact == record


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
async def test_document_scope_hides_entities_of_other_documents(
    seeded: dict,
) -> None:
    """A document-scoped agent must not see entities found only elsewhere."""
    env = seeded
    tools = make_tools(
        _engine(env),
        Ledger(),
        filters=SearchFilters(
            document_ids=[env["main_id"]], labels=list(env["labels"].values())
        ),
    )
    for name in ("look_up_entity", "explore_related"):
        rendered = await _tool(tools, name).ainvoke({"query": "Zed"})
        seen = _names(rendered, env["suffix"])
        assert not {"Zed", "Zeta"} & set(seen), (name, seen)


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
