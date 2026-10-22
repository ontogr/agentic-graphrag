"""Equivalence tests for the relation and evidence Cypher rewrites.

Each test seeds one graph, then runs the query text that was in place before
the rewrite and the current builder output with the same parameters. Both must
return the same rows. The old texts are copied from the previous revision of
``agrag/cypher/relations.py`` and ``agrag/cypher/evidence.py``.

The fixture seeds documents, chunks, entities and edges under a per-test id
prefix, so the tests can share one database. Chunks and edges tagged with a
pending job id are visible only to queries that pass that job id. Every seeded
node is deleted when the test ends.
"""

import importlib.util
import json
import os
from collections.abc import AsyncGenerator, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY
from agrag.common.data_models.graph_schema import RESERVED_RELATION_TYPES
from agrag.common.data_models.structure import HAS_PART
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.cypher.evidence import (
    evidence_chunk_at_offset_query,
    evidence_chunks_query,
    explore_edges_query,
)
from agrag.cypher.relations import (
    bfs_expand_query,
    close_has_part_query,
    entities_in_documents_query,
)


pytestmark = pytest.mark.neo4j_only


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _Neo4jRunner:
    """Runs raw Cypher against the Neo4j server named by the NEO4J_* variables.

    The equivalence cases compare two query texts on one server, so they call the
    driver directly and bypass the store wrapper.
    """

    def __init__(self) -> None:
        """Read the connection settings from the environment."""
        self._uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self._auth = (
            os.environ.get("NEO4J_USERNAME", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", ""),
        )
        self._driver: Any = None

    async def connect(self) -> None:
        """Open the driver."""
        from neo4j import AsyncGraphDatabase  # noqa: PLC0415

        self._driver = AsyncGraphDatabase.driver(self._uri, auth=self._auth)

    async def close(self) -> None:
        """Close the driver."""
        await self._driver.close()

    async def execute_read(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a query and return its rows as dictionaries."""
        return await self._run(query, parameters)

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a write query and return its rows as dictionaries."""
        return await self._run(query, parameters)

    async def _run(
        self, query: str, parameters: Mapping[str, Any] | None
    ) -> list[dict[str, Any]]:
        """Run one query in an auto-commit session."""
        async with self._driver.session() as session:
            result = await session.run(query, dict(parameters or {}))
            return [record.data() async for record in result]


_OLD_CLOSE_HAS_PART_QUERY = (
    "MATCH (d:_Node:Document {id: $document_node_id})-[r:HAS_PART]->(c) WHERE "
    "r.invalid_at IS NULL AND r._pending_job_id IS NULL AND NOT c.id IN "
    "$keep_node_ids SET r.invalid_at = datetime() RETURN count(r) AS closed"
)

_OLD_BFS_DEFAULT_QUERY = (
    "UNWIND $seed_ids AS seed_id MATCH (start:_Node {id: seed_id}) MATCH path = "
    "(start)-[*1..2]-(neighbor) WHERE neighbor:_Node AND NOT neighbor:Chunk AND NOT "
    "neighbor.id IN $seed_ids AND NOT neighbor:Section AND NOT neighbor:Table AND "
    "NOT neighbor:Figure AND NOT neighbor:Source AND NOT neighbor:DocumentActivation "
    "AND (neighbor._pending_job_id IS NULL OR neighbor._pending_job_id = $job_id) "
    "AND ALL(path_node IN nodes(path) WHERE path_node:_Node) AND ALL(r IN "
    "relationships(path) WHERE (r._pending_job_id IS NULL OR r._pending_job_id = "
    "$job_id) AND NOT type(r) IN ['HAS_PART', 'HAS_CHILD', 'HAS_DOCUMENT', "
    "'HAS_ACTIVATION', 'HAS_EVENT', 'HAS_STEP']) AND EXISTS { MATCH "
    "(neighbor)<-[scoped_mention:MENTIONED_IN]-(scoped_chunk:_Node:Chunk) WHERE "
    "scoped_chunk.document_id IN $document_ids AND (scoped_chunk._pending_job_id IS "
    "NULL OR scoped_chunk._pending_job_id = $job_id) AND "
    "(scoped_mention._pending_job_id IS NULL OR scoped_mention._pending_job_id = "
    "$job_id) } RETURN DISTINCT neighbor, neighbor.id AS id LIMIT 50"
)

_OLD_BFS_TYPED_QUERY = (
    "UNWIND $seed_ids AS seed_id MATCH (start:_Node {id: seed_id}) MATCH path = "
    "(start)-[:WORKS_WITH*1..2]->(neighbor) WHERE neighbor:_Node AND NOT "
    "neighbor:Chunk AND NOT neighbor.id IN $seed_ids AND NOT neighbor:Section AND "
    "NOT neighbor:Table AND NOT neighbor:Figure AND NOT neighbor:Source AND NOT "
    "neighbor:DocumentActivation AND (neighbor._pending_job_id IS NULL OR "
    "neighbor._pending_job_id = $job_id) AND ALL(path_node IN nodes(path) WHERE "
    "path_node:_Node) AND ALL(r IN relationships(path) WHERE (r._pending_job_id IS "
    "NULL OR r._pending_job_id = $job_id)) AND EXISTS { MATCH "
    "(neighbor)<-[scoped_mention:MENTIONED_IN]-(scoped_chunk:_Node:Chunk) WHERE "
    "scoped_chunk.document_id IN $document_ids AND (scoped_chunk._pending_job_id IS "
    "NULL OR scoped_chunk._pending_job_id = $job_id) AND "
    "(scoped_mention._pending_job_id IS NULL OR scoped_mention._pending_job_id = "
    "$job_id) } AND (neighbor:Person OR neighbor:Organization) RETURN DISTINCT "
    "neighbor, neighbor.id AS id LIMIT 50"
)

_OLD_ENTITIES_IN_DOCUMENTS_QUERY = (
    "MATCH (chunk:_Node:Chunk)-[mention:MENTIONED_IN]->(entity:_Node) WHERE EXISTS { "
    "MATCH (document:_Node:Document)-[part:HAS_PART]->(chunk) WHERE document.id IN "
    "$document_ids AND part.invalid_at IS NULL AND (document._pending_job_id IS NULL "
    "OR document._pending_job_id = $job_id) AND (part._pending_job_id IS NULL OR "
    "part._pending_job_id = $job_id) } AND (entity._pending_job_id IS NULL OR "
    "entity._pending_job_id = $job_id) AND (chunk._pending_job_id IS NULL OR "
    "chunk._pending_job_id = $job_id) AND (mention._pending_job_id IS NULL OR "
    "mention._pending_job_id = $job_id) RETURN DISTINCT entity.id AS id"
)

_OLD_CHUNKS_BY_ID_QUERY = (
    "MATCH (document:_Node:Document {id: "
    "$document_id})-[part:HAS_PART]->(chunk:_Node:Chunk) WHERE chunk.content_hash "
    "STARTS WITH $content_hash_prefix AND chunk.id = $chunk_id AND "
    "document._pending_job_id IS NULL AND part._pending_job_id IS NULL AND "
    "chunk._pending_job_id IS NULL AND EXISTS { MATCH "
    "(document)-[open:HAS_PART]->(:_Node:Chunk) WHERE open.invalid_at IS NULL AND "
    "open._pending_job_id IS NULL } RETURN chunk {.id, .document_id, .content_hash, "
    ".index, .text, .provenance, .heading_path, .content_kind, .chunker, "
    ".chunker_hash, .schema_fingerprint, .extraction_fingerprint, .section_ids, "
    ".created_at} AS chunk, part.version_id AS version_id, toString(part.invalid_at) "
    "AS closed_at, document.document_key AS document_key, document.title AS title, "
    "document.uri AS uri, document.current_content_hash AS current_content_hash, "
    "document.activation_seq AS activation_seq"
)

_OLD_CHUNKS_BY_PREFIX_QUERY = (
    "MATCH (document:_Node:Document {id: "
    "$document_id})-[part:HAS_PART]->(chunk:_Node:Chunk) WHERE chunk.content_hash "
    "STARTS WITH $content_hash_prefix AND document._pending_job_id IS NULL AND "
    "part._pending_job_id IS NULL AND chunk._pending_job_id IS NULL AND EXISTS { "
    "MATCH (document)-[open:HAS_PART]->(:_Node:Chunk) WHERE open.invalid_at IS NULL "
    "AND open._pending_job_id IS NULL } RETURN chunk {.id, .document_id, "
    ".content_hash, .index, .text, .provenance, .heading_path, .content_kind, "
    ".chunker, .chunker_hash, .schema_fingerprint, .extraction_fingerprint, "
    ".section_ids, .created_at} AS chunk, part.version_id AS version_id, "
    "toString(part.invalid_at) AS closed_at, document.document_key AS document_key, "
    "document.title AS title, document.uri AS uri, document.current_content_hash AS "
    "current_content_hash, document.activation_seq AS activation_seq"
)

_OLD_CHUNK_AT_OFFSET_QUERY = (
    "MATCH (document:_Node:Document {id: "
    "$document_id})-[part:HAS_PART]->(chunk:_Node:Chunk) WHERE chunk.content_hash "
    "STARTS WITH $content_hash_prefix AND chunk.char_start <= $char_start AND "
    "$char_start < chunk.char_end AND document._pending_job_id IS NULL AND "
    "part._pending_job_id IS NULL AND chunk._pending_job_id IS NULL AND EXISTS { "
    "MATCH (document)-[open:HAS_PART]->(:_Node:Chunk) WHERE open.invalid_at IS NULL "
    "AND open._pending_job_id IS NULL } RETURN chunk {.id, .document_id, "
    ".content_hash, .index, .text, .provenance, .heading_path, .content_kind, "
    ".chunker, .chunker_hash, .schema_fingerprint, .extraction_fingerprint, "
    ".section_ids, .created_at} AS chunk, part.version_id AS version_id, "
    "toString(part.invalid_at) AS closed_at, document.document_key AS document_key, "
    "document.title AS title, document.current_content_hash AS current_content_hash, "
    "document.activation_seq AS activation_seq ORDER BY chunk.index LIMIT 1"
)

_OLD_EXPLORE_EDGES_QUERY = (
    "UNWIND $node_ids AS node_id MATCH (node:_Node {id: node_id}) WHERE "
    "node._pending_job_id IS NULL MATCH (node)-[relation]-(other:_Node) WHERE "
    "relation._pending_job_id IS NULL AND other._pending_job_id IS NULL AND "
    "other.merge_key IS NOT NULL AND CASE WHEN size($relation_types) > 0 THEN "
    "type(relation) IN $relation_types ELSE NOT type(relation) IN $system_types END "
    "AND EXISTS { MATCH (scope_document:_Node:Document)-[scope_part:HAS_PART]->"
    "(scope_chunk:_Node:Chunk)-[:MENTIONED_IN]->(other) "
    "WHERE scope_document.id IN $scope_ids AND scope_document._pending_job_id IS "
    "NULL AND scope_part._pending_job_id IS NULL AND scope_chunk._pending_job_id IS "
    "NULL } WITH DISTINCT relation, other, startNode(relation) AS source, "
    "endNode(relation) AS target ORDER BY relation.id LIMIT $row_limit CALL { WITH "
    "relation OPTIONAL MATCH "
    "(support_document:_Node:Document)-[support_part:HAS_PART]->"
    "(support_chunk:_Node:Chunk) "
    "WHERE support_chunk.id IN coalesce(relation.source_chunk_ids, []) AND "
    "support_part.invalid_at IS NULL AND support_document.id IN $scope_ids AND "
    "support_document._pending_job_id IS NULL AND support_part._pending_job_id IS "
    "NULL AND support_chunk._pending_job_id IS NULL WITH support_chunk, "
    "support_document, support_part ORDER BY support_chunk.index LIMIT "
    "$support_limit RETURN collect(CASE WHEN support_chunk IS NULL THEN NULL ELSE "
    "{chunk: support_chunk {.id, .document_id, .content_hash, .index, .text, "
    ".provenance, .heading_path, .content_kind, .chunker, .chunker_hash, "
    ".schema_fingerprint, .extraction_fingerprint, .section_ids, .created_at}, "
    "version_id: support_part.version_id, closed_at: "
    "toString(support_part.invalid_at), document_key: support_document.document_key, "
    "current_content_hash: support_document.current_content_hash} END) AS supports } "
    "RETURN relation.id AS relation_id, type(relation) AS relation_type, source.id "
    "AS source_id, target.id AS target_id, other.id AS entity_id, other.name AS "
    "name, [label IN labels(other) WHERE label <> '_Node'][0] AS label, "
    "size(coalesce(relation.source_chunk_ids, [])) AS source_count, supports ORDER "
    "BY relation_id"
)

_CREATE_DOCUMENTS = (
    f"UNWIND $rows AS row CREATE (n:{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL}) "
    "SET n += row"
)
_CREATE_CHUNKS = (
    f"UNWIND $rows AS row CREATE (n:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL}) SET n += row"
)
_CREATE_ENTITIES = (
    f"UNWIND $rows AS row CREATE (n:{NODE_IDENTITY_LABEL}:Person) SET n += row"
)
_CLOSED_AT = "2026-10-01T00:00:00+00:00"

# Document names, then chunks as (name, document, index, char_start, char_end,
# version, closed, pending).
_DOCUMENT_NAMES = ("doc_in", "doc_out", "doc_gone", "close_old", "close_new")
_CHUNKS = (
    ("c_in_a", "doc_in", 0, 0, 10, "v2", False, False),
    ("c_in_b", "doc_in", 1, 10, 20, "v2", False, False),
    ("c_in_pending", "doc_in", 2, 20, 30, "v2", False, True),
    ("c_in_old", "doc_in", 3, 30, 40, "v1", True, False),
    ("c_out", "doc_out", 0, 0, 10, "v1", False, False),
    ("c_gone", "doc_gone", 0, 0, 10, "v1", True, False),
    ("old_open", "close_old", 0, 0, 0, "v2", False, False),
    ("old_keep", "close_old", 1, 0, 0, "v2", False, False),
    ("old_closed", "close_old", 2, 0, 0, "v1", True, False),
    ("old_pending", "close_old", 3, 0, 0, "v2", False, True),
    ("new_open", "close_new", 0, 0, 0, "v2", False, False),
    ("new_keep", "close_new", 1, 0, 0, "v2", False, False),
    ("new_closed", "close_new", 2, 0, 0, "v1", True, False),
    ("new_pending", "close_new", 3, 0, 0, "v2", False, True),
)
_ENTITY_NAMES = (
    "seed",
    "e_in_a",
    "e_in_b",
    "e_chain",
    "e_pending",
    "e_old",
    "e_out",
    "e_gone",
)
_MENTIONS = (
    ("c_in_a", "e_in_a"),
    ("c_in_b", "e_in_b"),
    ("c_in_pending", "e_pending"),
    ("c_in_old", "e_old"),
    ("c_out", "e_out"),
    ("c_gone", "e_gone"),
)
# Relations as (name, start, end, source chunk names, pending).
_RELATIONS = (
    ("rel_in_a", "seed", "e_in_a", ("c_in_a",), False),
    ("rel_chain", "seed", "e_chain", (), False),
    ("rel_chain_in_b", "e_chain", "e_in_b", ("c_in_b",), False),
    ("rel_out", "seed", "e_out", ("c_out",), False),
    ("rel_old", "seed", "e_old", ("c_in_old",), False),
    ("rel_gone", "seed", "e_gone", ("c_gone",), False),
    ("rel_pending", "seed", "e_pending", ("c_in_pending",), True),
)

_ENTITY_CASES: list[tuple[tuple[str, ...], bool, set[str]]] = [
    (("doc_in",), False, {"e_in_a", "e_in_b"}),
    (("doc_in",), True, {"e_in_a", "e_in_b", "e_pending"}),
    (("doc_out",), False, {"e_out"}),
    (("doc_gone",), True, set()),
    (("missing",), False, set()),
]
_BFS_CASES: list[tuple[str, tuple[str, ...], bool, set[str]]] = [
    ("default", ("doc_in",), False, {"e_in_a", "e_old", "e_in_b"}),
    ("default", ("doc_in",), True, {"e_in_a", "e_old", "e_in_b", "e_pending"}),
    ("default", ("doc_out",), False, {"e_out"}),
    ("default", ("doc_gone",), False, {"e_gone"}),
    ("typed", ("doc_in",), False, {"e_in_a", "e_old", "e_in_b"}),
    ("typed", ("doc_in",), True, {"e_in_a", "e_old", "e_in_b", "e_pending"}),
    ("default", ("missing",), False, set()),
]
_EXPLORE_CASES: list[tuple[tuple[str, ...], tuple[str, ...], set[str]]] = [
    (("doc_in",), (), {"rel_in_a", "rel_old"}),
    (("doc_in",), ("WORKS_WITH",), {"rel_in_a", "rel_old"}),
    (("doc_out",), (), {"rel_out"}),
    (("doc_gone",), (), {"rel_gone"}),
    (("missing",), (), set()),
]
# Chunk cases as (by_chunk_id, document, chunk, hash prefix, expected rows).
_CHUNK_CASES: list[tuple[bool, str, str | None, str, int]] = [
    (False, "doc_in", None, "abc", 3),
    (False, "doc_gone", None, "abc", 0),
    (False, "doc_in", None, "zzz", 0),
    (True, "doc_in", "c_in_a", "abc", 1),
    (True, "doc_in", "c_in_old", "abc", 1),
    (True, "doc_gone", "c_gone", "abc", 0),
]
# Offset cases as (document, char_start, expected rows).
_OFFSET_CASES: list[tuple[str, int, int]] = [
    ("doc_in", 12, 1),
    ("doc_in", 35, 1),
    ("doc_in", 25, 0),
    ("doc_gone", 5, 0),
    ("doc_in", 99, 0),
]
# Close cases as (document, kept chunk names, chunk names closed by the run).
_CLOSE_CASES: list[tuple[str, tuple[str, ...], set[str]]] = [
    ("close", (), {"open", "keep"}),
    ("close", ("keep",), {"open"}),
    ("missing", (), set()),
]


def _link_query(rel_type: str) -> str:
    """Build Cypher creating one relationship per row between seeded nodes.

    Args:
        rel_type: The relationship type. It comes from a module constant.

    Returns:
        Cypher expecting ``$rows``, each with ``start``, ``end`` and ``props``.
    """
    return (
        f"UNWIND $rows AS row MATCH (a:{NODE_IDENTITY_LABEL} {{id: row.start}}) "
        f"MATCH (b:{NODE_IDENTITY_LABEL} {{id: row.end}}) "
        f"CREATE (a)-[r:{rel_type}]->(b) SET r += row.props"
    )


def _rows_key(rows: Sequence[dict[str, Any]]) -> list[str]:
    """Return a sorted, comparable form of result rows."""
    return sorted(json.dumps(row, sort_keys=True, default=str) for row in rows)


class TestRelationsEvidenceEquivalence:
    """Rewritten relation and evidence queries return the rows they returned before."""

    @pytest.fixture(autouse=True)
    async def seeded_graph(self) -> AsyncGenerator[None, None]:
        """Seed one graph under a fresh id prefix and delete it afterwards."""
        self.store = _Neo4jRunner()
        await self.store.connect()
        self.run = f"eq{uuid4().hex[:10]}"
        self.job = f"{self.run}-job"
        await self._seed()
        yield
        await self.store.execute_write(
            f"MATCH (n:{NODE_IDENTITY_LABEL}) WHERE n.id STARTS WITH $prefix "
            "DETACH DELETE n",
            {"prefix": f"{self.run}-"},
        )
        await self.store.close()

    def _id(self, name: str) -> str:
        """Return the seeded id for a short node name."""
        return f"{self.run}-{name}"

    def _name(self, node_id: str) -> str:
        """Return the short name for a seeded id."""
        return node_id.removeprefix(f"{self.run}-")

    async def _seed(self) -> None:
        """Create the documents, chunks, entities and edges that the cases read."""
        documents = [
            {
                "id": self._id(name),
                "document_key": name,
                "title": name,
                "uri": f"memory://{name}",
                "current_content_hash": f"hash-{name}",
                "activation_seq": 1,
            }
            for name in _DOCUMENT_NAMES
        ]
        chunks: list[dict[str, Any]] = []
        part_edges: list[dict[str, Any]] = []
        for name, document, index, start, end, version, closed, pending in _CHUNKS:
            chunk: dict[str, Any] = {
                "id": self._id(name),
                "document_id": self._id(document),
                "content_hash": f"abc-{name}",
                "index": index,
                "char_start": start,
                "char_end": end,
                "text": name,
            }
            props: dict[str, Any] = {"version_id": version}
            if closed:
                props["invalid_at"] = _CLOSED_AT
            if pending:
                chunk[PENDING_JOB_ID_PROPERTY] = self.job
                props[PENDING_JOB_ID_PROPERTY] = self.job
            chunks.append(chunk)
            part_edges.append(
                {"start": self._id(document), "end": self._id(name), "props": props}
            )
        entities = [
            {"id": self._id(name), "name": name, "merge_key": self._id(name)}
            for name in _ENTITY_NAMES
        ]
        mentions = [
            {"start": self._id(chunk), "end": self._id(entity), "props": {}}
            for chunk, entity in _MENTIONS
        ]
        relations: list[dict[str, Any]] = []
        for name, start, end, sources, pending in _RELATIONS:
            props = {
                "id": self._id(name),
                "source_chunk_ids": [self._id(source) for source in sources],
            }
            if pending:
                props[PENDING_JOB_ID_PROPERTY] = self.job
            relations.append(
                {"start": self._id(start), "end": self._id(end), "props": props}
            )
        await self.store.execute_write(_CREATE_DOCUMENTS, {"rows": documents})
        await self.store.execute_write(_CREATE_CHUNKS, {"rows": chunks})
        await self.store.execute_write(_CREATE_ENTITIES, {"rows": entities})
        await self.store.execute_write(_link_query(HAS_PART), {"rows": part_edges})
        await self.store.execute_write(_link_query("MENTIONED_IN"), {"rows": mentions})
        await self.store.execute_write(_link_query("WORKS_WITH"), {"rows": relations})

    def _scope_ids(self, documents: Sequence[str]) -> list[str]:
        """Return the seeded ids for short document names."""
        return [self._id(name) for name in documents]

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.parametrize(("documents", "job_scoped", "expected"), _ENTITY_CASES)
    async def test_entities_in_documents_matches_old_query(
        self,
        documents: tuple[str, ...],
        job_scoped: bool,
        expected: set[str],
    ) -> None:
        """Entities mentioned in scope are returned with the same rows as before."""
        params = {
            "document_ids": self._scope_ids(documents),
            "job_id": self.job if job_scoped else None,
        }
        old_rows = await self.store.execute_read(
            _OLD_ENTITIES_IN_DOCUMENTS_QUERY, params
        )
        new_rows = await self.store.execute_read(entities_in_documents_query(), params)

        assert _rows_key(new_rows) == _rows_key(old_rows)
        assert {self._name(row["id"]) for row in new_rows} == expected

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.parametrize(
        ("kind", "documents", "job_scoped", "expected"), _BFS_CASES
    )
    async def test_bfs_expand_matches_old_query(
        self,
        kind: str,
        documents: tuple[str, ...],
        job_scoped: bool,
        expected: set[str],
    ) -> None:
        """BFS neighbors inside the document scope match the old query's rows."""
        job_id = self.job if job_scoped else None
        if kind == "default":
            old_query = _OLD_BFS_DEFAULT_QUERY
            new_query, filter_params = bfs_expand_query(
                depth=2, document_ids=self._scope_ids(documents), job_id=job_id
            )
        else:
            old_query = _OLD_BFS_TYPED_QUERY
            new_query, filter_params = bfs_expand_query(
                depth=2,
                direction="outgoing",
                relation_types=["WORKS_WITH"],
                labels=["Person", "Organization"],
                document_ids=self._scope_ids(documents),
                job_id=job_id,
            )
        params = {
            **filter_params,
            "seed_ids": [self._id("seed")],
            "document_ids": self._scope_ids(documents),
            "job_id": job_id,
        }
        old_rows = await self.store.execute_read(old_query, params)
        new_rows = await self.store.execute_read(new_query, params)

        assert _rows_key(new_rows) == _rows_key(old_rows)
        assert {self._name(row["id"]) for row in new_rows} == expected

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.parametrize(
        ("documents", "relation_types", "expected"), _EXPLORE_CASES
    )
    async def test_explore_edges_matches_old_query(
        self,
        documents: tuple[str, ...],
        relation_types: tuple[str, ...],
        expected: set[str],
    ) -> None:
        """Relations to entities in scope match the old query's rows."""
        params = {
            "node_ids": [self._id("seed")],
            "relation_types": list(relation_types),
            "system_types": sorted(RESERVED_RELATION_TYPES),
            "scope_ids": self._scope_ids(documents),
            "support_limit": 5,
            "row_limit": 100,
        }
        old_rows = await self.store.execute_read(_OLD_EXPLORE_EDGES_QUERY, params)
        new_rows = await self.store.execute_read(explore_edges_query(), params)

        assert _rows_key(new_rows) == _rows_key(old_rows)
        assert {self._name(row["relation_id"]) for row in new_rows} == expected

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.parametrize(
        ("by_chunk_id", "document", "chunk", "prefix", "expected_rows"),
        _CHUNK_CASES,
    )
    async def test_evidence_chunks_matches_old_query(
        self,
        by_chunk_id: bool,
        document: str,
        chunk: str | None,
        prefix: str,
        expected_rows: int,
    ) -> None:
        """Document chunks are read only while the document has an open edge."""
        params: dict[str, Any] = {
            "document_id": self._id(document),
            "content_hash_prefix": prefix,
        }
        if chunk is not None:
            params["chunk_id"] = self._id(chunk)
        old_query = (
            _OLD_CHUNKS_BY_ID_QUERY if by_chunk_id else _OLD_CHUNKS_BY_PREFIX_QUERY
        )
        old_rows = await self.store.execute_read(old_query, params)
        new_rows = await self.store.execute_read(
            evidence_chunks_query(by_chunk_id=by_chunk_id), params
        )

        assert _rows_key(new_rows) == _rows_key(old_rows)
        assert len(new_rows) == expected_rows

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.parametrize(("document", "char_start", "expected_rows"), _OFFSET_CASES)
    async def test_evidence_chunk_at_offset_matches_old_query(
        self, document: str, char_start: int, expected_rows: int
    ) -> None:
        """The chunk at an offset is read only while the document has an open edge."""
        params = {
            "document_id": self._id(document),
            "content_hash_prefix": "abc",
            "char_start": char_start,
        }
        old_rows = await self.store.execute_read(_OLD_CHUNK_AT_OFFSET_QUERY, params)
        new_rows = await self.store.execute_read(
            evidence_chunk_at_offset_query(), params
        )

        assert _rows_key(new_rows) == _rows_key(old_rows)
        assert len(new_rows) == expected_rows

    @pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
    @pytest.mark.parametrize(("document", "keep", "expected"), _CLOSE_CASES)
    async def test_close_has_part_matches_old_query(
        self, document: str, keep: tuple[str, ...], expected: set[str]
    ) -> None:
        """Closing edges closes the same committed edges, stamped with the time."""
        if document == "missing":
            old_document = new_document = self._id("missing")
            old_keep: list[str] = []
            new_keep: list[str] = []
        else:
            old_document = self._id("close_old")
            new_document = self._id("close_new")
            old_keep = [self._id(f"old_{name}") for name in keep]
            new_keep = [self._id(f"new_{name}") for name in keep]

        old_rows = await self.store.execute_write(
            _OLD_CLOSE_HAS_PART_QUERY,
            {"document_node_id": old_document, "keep_node_ids": old_keep},
        )
        closed_at = datetime.now(UTC).isoformat()
        new_rows = await self.store.execute_write(
            close_has_part_query(),
            {
                "document_node_id": new_document,
                "keep_node_ids": new_keep,
                "closed_at": closed_at,
            },
        )
        old_values = await self._closed_values(old_document)
        new_values = await self._closed_values(new_document)

        assert old_rows == new_rows
        assert old_rows == [{"closed": len(expected)}]
        assert set(old_values) == set(new_values)
        assert {
            key for key, value in new_values.items() if value == closed_at
        } == expected

    async def _closed_values(self, document_id: str) -> dict[str, str]:
        """Return the invalid_at text of each closed edge of one document."""
        rows = await self.store.execute_read(
            f"MATCH (d:{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL} {{id: $document_id}})"
            f"-[r:{HAS_PART}]->(c) WHERE r.invalid_at IS NOT NULL "
            "RETURN c.id AS id, toString(r.invalid_at) AS invalid_at",
            {"document_id": document_id},
        )
        return {
            self._name(row["id"]).split("_", 1)[1]: row["invalid_at"] for row in rows
        }
