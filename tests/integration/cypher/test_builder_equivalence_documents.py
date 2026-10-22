"""Old-versus-new checks for the document Cypher builders against real Neo4j.

Each test runs the query text the builder produced before the change, copied
verbatim as a string constant, next to the current builder output on the same
seeded shape. The old text still uses ``EXISTS``, ``datetime()`` and
``elementId``, which the current builders no longer emit. Every test uses
its own id prefix, and teardown deletes the nodes it created.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). The ``skipif``
only guards the missing extra; with the extra installed the tests expect a
reachable Neo4j at the default ``NEO4J_URI``.
"""

import importlib.util
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL
from agrag.common.data_models.structure import (
    DOCUMENT_ACTIVATION_LABEL,
    HAS_ACTIVATION,
    HAS_PART,
)
from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.documents import (
    document_cited_relation_endpoints_query,
    document_cited_relation_ids_query,
    purge_relation_evidence_query,
    record_activation_query,
    source_status_query,
)
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.graphdb.base import GraphStore
from tests.integration._backend import build_test_store


pytestmark = pytest.mark.neo4j_only


neo4j_missing = importlib.util.find_spec("neo4j") is None

_EVIDENCE_REL = "H1EvidenceTest"

_OLD_PURGE_RELATION_EVIDENCE = (
    "MATCH ()-[r]->() "
    "WHERE r.source_chunk_ids IS NOT NULL "
    "AND EXISTS { "
    f"MATCH (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
    "{document_id: $document_node_id}) "
    "WHERE c.id IN r.source_chunk_ids } "
    "SET r.source_chunk_ids = "
    "[cid IN r.source_chunk_ids WHERE NOT EXISTS { "
    f"MATCH (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
    "{document_id: $document_node_id, id: cid}) }] "
    "WITH r WHERE size(r.source_chunk_ids) = 0 "
    "DELETE r RETURN count(r) AS deleted"
)

_OLD_CITED_RELATION_ENDPOINTS = (
    f"MATCH (a:{NODE_IDENTITY_LABEL})-[r]->(b:{NODE_IDENTITY_LABEL}) "
    "WHERE r.source_chunk_ids IS NOT NULL "
    "AND EXISTS { "
    f"MATCH (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
    "{document_id: $document_node_id}) "
    "WHERE c.id IN r.source_chunk_ids } "
    "UNWIND [a.id, b.id] AS id RETURN DISTINCT id LIMIT $limit"
)

_OLD_CITED_RELATION_IDS = (
    "MATCH ()-[r]->() WHERE r.source_chunk_ids IS NOT NULL AND EXISTS { "
    f"MATCH (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
    "{document_id: $document_node_id}) "
    "WHERE c.id IN r.source_chunk_ids } "
    "RETURN elementId(r) AS id LIMIT $limit"
)

_OLD_RECORD_ACTIVATION = (
    f"MATCH (d:{NODE_IDENTITY_LABEL}:Document {{id: $document_node_id}}) "
    "SET d.activation_seq = coalesce(d.activation_seq, 0) + 1 "
    "WITH d "
    f"CREATE (d)-[:{HAS_ACTIVATION}]->"
    f"(a:{NODE_IDENTITY_LABEL}:{DOCUMENT_ACTIVATION_LABEL} {{"
    "id: $id, document_key: $document_key, verb: $verb, "
    "content_hash: $content_hash, "
    "previous_content_hash: $previous_content_hash, "
    "version_id: $version_id, activation_seq: d.activation_seq, "
    "activated_at: datetime(), job_id: $job_id}) "
    "RETURN a.activation_seq AS activation_seq"
)

_OLD_SOURCE_STATUS = (
    f"OPTIONAL MATCH (d:{NODE_IDENTITY_LABEL}:Document "
    "{document_key: $document_key}) "
    f"OPTIONAL MATCH (job:{CUTOVER_JOB_LABEL} {{document_key: $document_key}}) "
    "WHERE job.status IN ['pending', 'rolling_back', 'committed', 'cleaning'] "
    "WITH d, job ORDER BY job.created_at DESC "
    "WITH d, collect(job)[0] AS job "
    f"OPTIONAL MATCH (d)-[part:{HAS_PART}]->"
    f"(chunk:{NODE_IDENTITY_LABEL}:Chunk) "
    "WHERE part.invalid_at IS NULL "
    f"AND {pending_filter_clause('d')} "
    f"AND {pending_filter_clause('part')} "
    f"AND {pending_filter_clause('chunk')} "
    "WITH d, job, collect(part.version_id)[0] AS version_id, "
    "count(part) > 0 AS has_current, "
    "count(CASE WHEN chunk.id IS NOT NULL AND "
    "chunk.extraction_fingerprint IS NULL THEN 1 END) = 0 AS complete "
    f"OPTIONAL MATCH (d)-[:{HAS_ACTIVATION}]->(a:{NODE_IDENTITY_LABEL}:"
    f"{DOCUMENT_ACTIVATION_LABEL}) "
    "WITH d, job, version_id, has_current, complete, a "
    "ORDER BY a.activation_seq DESC "
    "WITH d, job, version_id, has_current, complete, collect(a)[0] AS activation "
    f"RETURN d IS NOT NULL AND {pending_filter_clause('d')} "
    "AS document_exists, "
    f"CASE WHEN {pending_filter_clause('d')} "
    "THEN d.current_content_hash END AS content_hash, "
    f"CASE WHEN {pending_filter_clause('d')} "
    "THEN d.activation_seq END AS activation_seq, version_id, "
    "has_current, complete, "
    "activation.verb AS last_verb, job.id AS job_id, "
    "job.status AS job_status, toString(job.lease_expires_at) AS lease_expires_at, "
    "duration.inSeconds(datetime(job.created_at), datetime()).seconds "
    "AS job_age_seconds, "
    "job.error AS job_error, job.lease_expires_at < datetime() AS lease_expired"
)

# Each relation's source_chunk_ids mixes the document's own chunks, another
# document's chunk, and a chunk id that exists nowhere.
_RELATIONS: dict[str, tuple[str, str, list[str] | None]] = {
    "mixed": ("A", "B", ["c1", "other", "missing"]),
    "only_doc": ("C", "D", ["c1", "c2"]),
    "other_only": ("E", "F", ["other"]),
    "missing_only": ("G", "H", ["missing"]),
    "empty": ("C", "F", []),
    "null": ("D", "E", None),
}

_EXPECTED_AFTER_PURGE: dict[str, list[str] | str | None] = {
    "mixed": ["missing", "other"],
    "only_doc": "deleted",
    "other_only": ["other"],
    "missing_only": ["missing"],
    "empty": [],
    "null": None,
}


async def _seed_evidence(store: GraphStore, tag: str) -> None:
    """Create one document with two chunks, another document's chunk and relations.

    The relation set covers cases the cited-relation queries must include or
    skip: a mix of this document's and another document's chunks, only this
    document's chunks, only another document's chunk, only a missing id, an
    empty list, and no property at all.
    """
    document_id = f"{tag}-doc"
    for chunk, owner in (
        ("c1", document_id),
        ("c2", document_id),
        ("other", f"{tag}-doc2"),
    ):
        await store.execute_write(
            f"CREATE (:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
            "{id: $id, document_id: $document_id})",
            {"id": f"{tag}-{chunk}", "document_id": owner},
        )
    for entity in "ABCDEFGH":
        await store.execute_write(
            f"CREATE (:{NODE_IDENTITY_LABEL} {{id: $id}})",
            {"id": f"{tag}-{entity}"},
        )
    for relation, (source, target, chunk_names) in _RELATIONS.items():
        await store.execute_write(
            f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: $source}}), "
            f"(b:{NODE_IDENTITY_LABEL} {{id: $target}}) "
            f"CREATE (a)-[:{_EVIDENCE_REL} {{id: $id, source_chunk_ids: $ids}}]->(b)",
            {
                "source": f"{tag}-{source}",
                "target": f"{tag}-{target}",
                "id": f"{tag}-rel-{relation}",
                "ids": (
                    None
                    if chunk_names is None
                    else [f"{tag}-{name}" for name in chunk_names]
                ),
            },
        )


async def _relation_state(store: GraphStore, tag: str, relation: str) -> Any:
    """Return a relation's chunk ids with the tag removed, or ``deleted``."""
    rows = await store.execute_read(
        "MATCH ()-[r {id: $id}]->() RETURN r.source_chunk_ids AS ids",
        {"id": f"{tag}-rel-{relation}"},
    )
    if not rows:
        return "deleted"
    ids = rows[0]["ids"]
    if ids is None:
        return None
    return sorted(str(item).removeprefix(f"{tag}-") for item in ids)


class TestDocumentsSubsetEquivalence:
    """The current document builders return the same rows as the old text."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Connect a Neo4j store and delete this test's nodes afterwards."""
        self.store = build_test_store()
        await self.store.connect()
        self.tag = f"h1-{uuid4().hex[:10]}"
        yield
        await self.store.execute_write(
            "MATCH (n) WHERE n.id STARTS WITH $tag DETACH DELETE n",
            {"tag": self.tag},
        )
        await self.store.close()

    async def test_cited_queries_match_old_exists_queries(self) -> None:
        """Cited endpoints and ids match the old EXISTS queries for mixed chunks."""
        await _seed_evidence(self.store, self.tag)
        params = {"document_node_id": f"{self.tag}-doc", "limit": 100}

        old_endpoints = await self.store.execute_read(
            _OLD_CITED_RELATION_ENDPOINTS, params
        )
        new_endpoints = await self.store.execute_read(
            document_cited_relation_endpoints_query(), params
        )
        old_ids = await self.store.execute_read(_OLD_CITED_RELATION_IDS, params)
        new_ids = await self.store.execute_read(
            document_cited_relation_ids_query(), params
        )

        expected_endpoints = {f"{self.tag}-{name}" for name in "ABCD"}
        assert {row["id"] for row in old_endpoints} == expected_endpoints
        assert {row["id"] for row in new_endpoints} == expected_endpoints
        assert len(old_ids) == len(new_ids) == 2
        assert {row["id"] for row in new_ids} == {
            f"{self.tag}-rel-mixed",
            f"{self.tag}-rel-only_doc",
        }

    async def test_cited_queries_return_nothing_for_document_without_relations(
        self,
    ) -> None:
        """A document no relation cites yields no rows from either query."""
        await _seed_evidence(self.store, self.tag)
        params = {"document_node_id": f"{self.tag}-uncited", "limit": 100}

        assert (
            await self.store.execute_read(_OLD_CITED_RELATION_ENDPOINTS, params) == []
        )
        assert (
            await self.store.execute_read(
                document_cited_relation_endpoints_query(), params
            )
            == []
        )
        assert await self.store.execute_read(_OLD_CITED_RELATION_IDS, params) == []
        assert (
            await self.store.execute_read(document_cited_relation_ids_query(), params)
            == []
        )

    async def test_purge_matches_old_exists_query(self) -> None:
        """The purge strips this document's chunk ids the same way as the old query."""
        old_tag = f"{self.tag}-old"
        new_tag = f"{self.tag}-new"
        await _seed_evidence(self.store, old_tag)
        await _seed_evidence(self.store, new_tag)

        old_result = await self.store.execute_write(
            _OLD_PURGE_RELATION_EVIDENCE, {"document_node_id": f"{old_tag}-doc"}
        )
        new_result = await self.store.execute_write(
            purge_relation_evidence_query(),
            {"document_node_id": f"{new_tag}-doc"},
        )

        assert old_result == new_result == [{"deleted": 1}]
        for relation, expected in _EXPECTED_AFTER_PURGE.items():
            assert await _relation_state(self.store, old_tag, relation) == expected
            assert await _relation_state(self.store, new_tag, relation) == expected

    async def test_purge_without_cited_relations_deletes_nothing(self) -> None:
        """A document with no citing relations leaves the graph unchanged."""
        await _seed_evidence(self.store, self.tag)
        params = {"document_node_id": f"{self.tag}-uncited"}

        assert await self.store.execute_write(_OLD_PURGE_RELATION_EVIDENCE, params) == [
            {"deleted": 0}
        ]
        assert await self.store.execute_write(
            purge_relation_evidence_query(), params
        ) == [{"deleted": 0}]
        assert await _relation_state(self.store, self.tag, "mixed") == [
            "c1",
            "missing",
            "other",
        ]

    async def test_activation_matches_old_query_with_given_timestamp(self) -> None:
        """The activation sequence matches the old query and the timestamp is stored."""
        old_doc = f"{self.tag}-doc-old"
        new_doc = f"{self.tag}-doc-new"
        for doc in (old_doc, new_doc):
            await self.store.execute_write(
                f"CREATE (:{NODE_IDENTITY_LABEL}:Document {{id: $id}})", {"id": doc}
            )
        activated_at = datetime.now(UTC).isoformat()
        base = {
            "id": f"{self.tag}-activation",
            "document_key": f"{self.tag}-key",
            "verb": "add",
            "content_hash": "hash-1",
            "previous_content_hash": None,
            "version_id": "version-1",
            "job_id": f"{self.tag}-job",
        }

        old_rows = await self.store.execute_write(
            _OLD_RECORD_ACTIVATION,
            {**base, "id": f"{self.tag}-activation-old", "document_node_id": old_doc},
        )
        new_rows = await self.store.execute_write(
            record_activation_query(),
            {
                **base,
                "document_node_id": new_doc,
                "activated_at": activated_at,
            },
        )

        assert old_rows == new_rows == [{"activation_seq": 1}]
        stored = await self.store.execute_read(
            f"MATCH (a:{NODE_IDENTITY_LABEL}:{DOCUMENT_ACTIVATION_LABEL} "
            "{id: $id}) RETURN a.activated_at AS activated_at",
            {"id": base["id"]},
        )
        assert stored == [{"activated_at": activated_at}]

    async def test_activation_for_missing_document_writes_nothing(self) -> None:
        """No Document node means no activation row from either query."""
        params = {
            "document_node_id": f"{self.tag}-absent",
            "id": f"{self.tag}-activation",
            "document_key": f"{self.tag}-key",
            "verb": "add",
            "content_hash": "hash-1",
            "previous_content_hash": None,
            "version_id": "version-1",
            "job_id": f"{self.tag}-job",
        }

        assert await self.store.execute_write(_OLD_RECORD_ACTIVATION, params) == []
        assert (
            await self.store.execute_write(
                record_activation_query(),
                {**params, "activated_at": datetime.now(UTC).isoformat()},
            )
            == []
        )

    @pytest.mark.parametrize(
        ("lease_offset_seconds", "expected_expired"),
        [(-600, True), (600, False)],
    )
    async def test_source_status_lease_flag_matches_old_query(
        self, lease_offset_seconds: int, expected_expired: bool
    ) -> None:
        """The expiry flag matches the old query for datetime and epoch-ms leases."""
        old_key = f"{self.tag}-old-key"
        new_key = f"{self.tag}-new-key"
        created_at = datetime.now(UTC).isoformat()
        await self.store.execute_write(
            f"CREATE (:{NODE_IDENTITY_LABEL}:Document {{id: $id, document_key: $key, "
            "activation_seq: 1, current_content_hash: 'hash-1'})",
            {"id": f"{self.tag}-doc-old", "key": old_key},
        )
        await self.store.execute_write(
            f"CREATE (:{CUTOVER_JOB_LABEL} {{id: $id, document_key: $key, "
            "status: 'pending', created_at: $created_at, "
            "lease_expires_at: datetime() + duration({seconds: $offset})})",
            {
                "id": f"{self.tag}-job-old",
                "key": old_key,
                "created_at": created_at,
                "offset": lease_offset_seconds,
            },
        )
        await self.store.execute_write(
            f"CREATE (:{NODE_IDENTITY_LABEL}:Document {{id: $id, document_key: $key, "
            "activation_seq: 1, current_content_hash: 'hash-1'})",
            {"id": f"{self.tag}-doc-new", "key": new_key},
        )
        await self.store.execute_write(
            f"CREATE (:{CUTOVER_JOB_LABEL} {{id: $id, document_key: $key, "
            "status: 'pending', created_at: $created_at, "
            "lease_expires_at: timestamp() + $offset})",
            {
                "id": f"{self.tag}-job-new",
                "key": new_key,
                "created_at": created_at,
                "offset": lease_offset_seconds * 1000,
            },
        )

        old_rows = await self.store.execute_read(
            _OLD_SOURCE_STATUS, {"document_key": old_key}
        )
        new_rows = await self.store.execute_read(
            source_status_query(), {"document_key": new_key}
        )

        assert len(old_rows) == len(new_rows) == 1
        old_row, new_row = old_rows[0], new_rows[0]
        assert old_row["lease_expired"] is expected_expired
        assert new_row["lease_expired"] is expected_expired
        for column in ("document_exists", "content_hash", "activation_seq"):
            assert old_row[column] == new_row[column]
        assert new_row["job_status"] == old_row["job_status"] == "pending"
        assert new_row["job_created_at"] == created_at
        assert isinstance(new_row["lease_expires_at"], int)
