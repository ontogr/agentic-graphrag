"""Check candidate Cypher builders against their pre-rewrite query text on Neo4j.

Each test runs the original query text and the current builder output
against the same seeded graph and compares the returned rows and the
resulting graph state. Seeded ids and keys carry a per-test tag, and the
fixture deletes every node the test created.
"""

import importlib.util
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest

from agrag.candidates import prune_candidates
from agrag.common.data_models.candidate import CANDIDATE_LABEL, EVIDENCED_BY
from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.cypher.candidate_review import delete_prunable_query, match_prunable_query
from agrag.cypher.candidate_review import list_candidates_query as review_list_query
from agrag.cypher.candidates import list_candidates_query, upsert_candidates_query
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.graphdb.base import GraphStore
from tests.integration._backend import build_test_store


pytestmark = pytest.mark.neo4j_only


neo4j_missing = importlib.util.find_spec("neo4j") is None

# Query text before the rewrite, kept verbatim for comparison.
OLD_UPSERT_CANDIDATES = (
    "UNWIND $records AS record MATCH (chunk:_Node:Chunk {id: "
    "record.chunk_id}) WHERE (chunk._pending_job_id IS NULL OR "
    "chunk._pending_job_id = record.pending_job_id) OPTIONAL MATCH "
    "(source:_Node {id: record.source_entity_id}) WHERE "
    "(source._pending_job_id IS NULL OR source._pending_job_id = "
    "record.pending_job_id) AND NONE(label IN labels(source) WHERE label IN "
    "['Candidate', 'Chunk', 'Community', 'CutoverJob', 'Document', 'Figure', "
    "'ResolvedEntity', 'Section', 'Source', 'Table', '_MergeAlias']) "
    "OPTIONAL MATCH (target:_Node {id: record.target_entity_id}) WHERE "
    "(target._pending_job_id IS NULL OR target._pending_job_id = "
    "record.pending_job_id) AND NONE(label IN labels(target) WHERE label IN "
    "['Candidate', 'Chunk', 'Community', 'CutoverJob', 'Document', 'Figure', "
    "'ResolvedEntity', 'Section', 'Source', 'Table', '_MergeAlias']) WITH "
    "record, chunk, source, target WHERE (record.source_entity_id IS NULL OR "
    "source IS NOT NULL) AND (record.target_entity_id IS NULL OR target IS "
    "NOT NULL) OPTIONAL MATCH (same_key:Candidate {key: "
    "record.properties.key}) WITH record, chunk, source, target, same_key "
    "ORDER BY same_key.id WITH record, chunk, source, target, "
    "collect(same_key) AS same_key_candidates FOREACH (candidate IN "
    "same_key_candidates | SET candidate.id = candidate.id) WITH record, "
    "chunk, source, target, same_key_candidates CALL (same_key_candidates) { "
    "UNWIND same_key_candidates AS candidate WITH candidate.id AS id MATCH "
    "(reviewed:Candidate {id: id}) RETURN count(CASE WHEN reviewed.state IN "
    "['approved', 'rejected'] AND reviewed._pending_job_id IS NULL THEN 1 "
    "END) > 0 AS blocked } WITH record, chunk, source, target, blocked "
    "FOREACH (_ IN CASE WHEN blocked THEN [] ELSE [1] END | MERGE "
    "(c:Candidate {id: record.candidate_id}) ON CREATE SET c += "
    "record.properties, c._pending_job_id = record.pending_job_id MERGE "
    "(c)-[evidence:EVIDENCED_BY {id: record.id}]->(chunk) ON CREATE SET "
    "evidence._pending_job_id = record.pending_job_id FOREACH (_ IN CASE "
    "WHEN source IS NULL THEN [] ELSE [1] END | MERGE "
    "(c)-[source_link:SOURCE {id: record.source_edge_id}]->(source) ON "
    "CREATE SET source_link._pending_job_id = record.pending_job_id) FOREACH "
    "(_ IN CASE WHEN target IS NULL THEN [] ELSE [1] END | MERGE "
    "(c)-[target_link:TARGET {id: record.target_edge_id}]->(target) ON "
    "CREATE SET target_link._pending_job_id = record.pending_job_id) ) "
    "RETURN record.id AS id"
)
OLD_LIST_CANDIDATES = (
    "MATCH (c:Candidate) WHERE (c._pending_job_id IS NULL OR "
    "c._pending_job_id = $job_id) AND ($kind IS NULL OR c.kind = $kind) AND "
    "($label IS NULL OR c.label = $label) AND ($state IS NULL OR c.state = "
    "$state) WITH c.key AS key, c.state AS state, collect(c) AS nodes, "
    "sum(c.count) AS total, max(c.confidence) AS best WHERE total >= "
    "$min_count CALL (nodes) { UNWIND nodes AS n OPTIONAL MATCH "
    "(n)-[e:EVIDENCED_BY]->(chunk:_Node) WHERE (e._pending_job_id IS NULL OR "
    "e._pending_job_id = $job_id) AND (chunk._pending_job_id IS NULL OR "
    "chunk._pending_job_id = $job_id) RETURN collect(DISTINCT chunk.id) AS "
    "chunk_ids } WITH key, state, total, best, chunk_ids, nodes, "
    "reduce(first = head(nodes), n IN nodes | CASE WHEN n.id < first.id THEN "
    "n ELSE first END) AS first RETURN key, state, first.kind AS kind, "
    "first.label AS label, first.text AS text, first.source_text AS "
    "source_text, first.source_label AS source_label, first.target_label AS "
    "target_label, first.target_text AS target_text, first.reason AS reason, "
    "first.schema_fingerprint AS schema_fingerprint, first.source_entity_id "
    "AS source_entity_id, first.target_entity_id AS target_entity_id, total "
    "AS count, best AS confidence, [n IN nodes | n.id] AS ids, chunk_ids "
    "ORDER BY total DESC, key SKIP $skip LIMIT $limit"
)
OLD_REVIEW_LIST_CANDIDATES = (
    "MATCH (c:Candidate) WHERE c._pending_job_id IS NULL AND ($kind IS NULL "
    "OR c.kind = $kind) AND ($label IS NULL OR c.label = $label) AND ($state "
    "IS NULL OR c.state = $state) WITH c.key AS key, c.state AS state, "
    "collect(c) AS nodes, sum(c.count) AS total, max(c.confidence) AS best "
    "WHERE total >= $min_count CALL (nodes) { UNWIND nodes AS n OPTIONAL "
    "MATCH (n)-[evidence:EVIDENCED_BY]->(chunk:_Node) WHERE "
    "evidence._pending_job_id IS NULL AND chunk._pending_job_id IS NULL "
    "OPTIONAL MATCH (doc:Document)-[part:HAS_PART]->(chunk) WHERE "
    "part._pending_job_id IS NULL AND doc._pending_job_id IS NULL RETURN "
    "collect(DISTINCT chunk.id) AS chunk_ids, collect(DISTINCT doc.id) AS "
    "document_ids } WITH key, state, total, best, nodes, chunk_ids, "
    "document_ids, reduce(first = head(nodes), n IN nodes | CASE WHEN n.id < "
    "first.id THEN n ELSE first END) AS first RETURN key, state, total AS "
    "count, [n IN nodes | n.id] AS ids, properties(first) AS candidate, best "
    "AS confidence, chunk_ids, size(document_ids) AS document_count ORDER BY "
    "count DESC, confidence DESC, key SKIP $skip LIMIT $limit"
)
OLD_MATCH_PRUNABLE = (
    "MATCH (c:Candidate) WHERE c._pending_job_id IS NULL WITH c.key AS key, "
    "c.state AS state, collect(c) AS nodes, sum(c.count) AS total, "
    "max(datetime(c.created_at)) AS newest WHERE state <> 'approved' AND "
    "(($rejected AND state = 'rejected') OR (state = 'pending' AND "
    "(($older_than IS NOT NULL AND newest < datetime($older_than)) OR "
    "($below_count IS NOT NULL AND total < $below_count)))) RETURN "
    "count(key) AS matched"
)
OLD_DELETE_PRUNABLE = (
    "MATCH (c:Candidate) WHERE c._pending_job_id IS NULL WITH c.key AS key, "
    "c.state AS state, collect(c) AS nodes, sum(c.count) AS total, "
    "max(datetime(c.created_at)) AS newest WHERE state <> 'approved' AND "
    "(($rejected AND state = 'rejected') OR (state = 'pending' AND "
    "(($older_than IS NOT NULL AND newest < datetime($older_than)) OR "
    "($below_count IS NOT NULL AND total < $below_count)))) UNWIND nodes AS "
    "node DETACH DELETE node WITH DISTINCT key RETURN count(key) AS deleted"
)


async def _seed_chunk(store: GraphStore, chunk_id: str) -> None:
    await store.execute_write(
        f"CREATE (:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} {{id: $id}})",
        {"id": chunk_id},
    )


async def _seed_entity(store: GraphStore, entity_id: str) -> None:
    await store.execute_write(
        f"CREATE (:{NODE_IDENTITY_LABEL} {{id: $id, name: $id}})", {"id": entity_id}
    )


async def _seed_candidate(
    store: GraphStore,
    *,
    candidate_id: str,
    key: str,
    chunk_id: str,
    state: str = "pending",
    count: int = 1,
    kind: str = "relation",
    created_at: str,
) -> None:
    await store.execute_write(
        f"MATCH (chunk:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} {{id: $chunk_id}}) "
        f"CREATE (c:{CANDIDATE_LABEL}) "
        "SET c += {id: $id, key: $key, state: $state, count: $count, "
        "kind: $kind, label: 'WORKS_FOR', confidence: 0.5, reason: 'r', "
        "schema_fingerprint: 'fp', text: 'a', created_at: $created_at} "
        f"CREATE (c)-[:{EVIDENCED_BY} {{id: $id + '-ev'}}]->(chunk)",
        {
            "chunk_id": chunk_id,
            "id": candidate_id,
            "key": key,
            "state": state,
            "count": count,
            "kind": kind,
            "created_at": created_at,
        },
    )


async def _names_by_id(
    store: GraphStore, query: str, params: dict[str, Any], ids: dict[str, str]
) -> list[str]:
    rows = await store.execute_write(query, params)
    return sorted(ids[row["id"]] for row in rows)


def _normalize_list_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        item = dict(row)
        item["ids"] = sorted(item["ids"])
        item["chunk_ids"] = sorted(item["chunk_ids"])
        normalized.append(item)
    return normalized


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestCandidateBuilderEquivalence:
    """Candidate builders return the same rows and state as the original text."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Connect a store and remove this test's nodes afterwards."""
        self.store = build_test_store()
        await self.store.connect()
        self.tag = f"cand{uuid4().hex[:12]}"
        yield
        await self.store.execute_write(
            "MATCH (n) WHERE toString(n.id) CONTAINS $tag "
            "OR toString(n.key) CONTAINS $tag DETACH DELETE n",
            {"tag": self.tag},
        )
        await self.store.close()

    async def test_upsert_writes_only_unblocked_resolved_records(self) -> None:
        """Blocked keys still echo the record, and unresolved records return nothing.

        A reviewed same-key candidate suppresses the new write, and a record
        whose source entity is missing does not return a row. Both the original
        text and the builder must agree on the returned ids and on how many
        candidates each key holds afterwards.
        """
        tag = self.tag
        chunk_id = f"{tag}-chunk"
        source_id = f"{tag}-source"
        await _seed_chunk(self.store, chunk_id)
        await _seed_entity(self.store, source_id)
        await _seed_candidate(
            self.store,
            candidate_id=f"{tag}-reviewed",
            key=f"{tag}-blocked-old",
            chunk_id=chunk_id,
            state="approved",
            created_at="2026-01-01T00:00:00+00:00",
        )
        await _seed_candidate(
            self.store,
            candidate_id=f"{tag}-reviewed-new",
            key=f"{tag}-blocked-new",
            chunk_id=chunk_id,
            state="approved",
            created_at="2026-01-01T00:00:00+00:00",
        )

        results = {}
        for variant, query in (
            ("old", OLD_UPSERT_CANDIDATES),
            ("new", upsert_candidates_query()),
        ):
            names: dict[str, str] = {}
            records = []
            for name, key, source in (
                ("free", f"{tag}-free-{variant}", source_id),
                ("blocked", f"{tag}-blocked-{variant}", source_id),
                ("unresolved", f"{tag}-unresolved-{variant}", f"{tag}-missing"),
            ):
                record_id = str(uuid4())
                names[record_id] = name
                records.append(
                    {
                        "id": record_id,
                        "candidate_id": f"{tag}-cand-{variant}-{name}",
                        "chunk_id": chunk_id,
                        "properties": {
                            "key": key,
                            "kind": "relation",
                            "label": "WORKS_FOR",
                            "count": 1,
                            "confidence": 0.9,
                            "state": "pending",
                            "reason": "r",
                            "schema_fingerprint": "fp",
                            "text": name,
                        },
                        "source_entity_id": source,
                        "source_edge_id": str(uuid4()),
                        "target_entity_id": None,
                        "target_edge_id": None,
                        "pending_job_id": None,
                    }
                )
            params = {"records": records}
            results[variant] = await _names_by_id(self.store, query, params, names)
            written = await self.store.execute_read(
                f"MATCH (c:{CANDIDATE_LABEL}) WHERE c.key IN $keys "
                "AND c.state = 'pending' RETURN c.key AS key ORDER BY key",
                {"keys": [f"{tag}-free-{variant}", f"{tag}-blocked-{variant}"]},
            )
            results[f"{variant}_written"] = [row["key"] for row in written]

        assert results["old"] == results["new"] == ["blocked", "free"]
        assert results["old_written"] == [f"{tag}-free-old"]
        assert results["new_written"] == [f"{tag}-free-new"]

    @pytest.mark.parametrize("min_count", [1, 6])
    @pytest.mark.parametrize(
        ("old_query", "new_query"),
        [
            (OLD_LIST_CANDIDATES, list_candidates_query()),
            (OLD_REVIEW_LIST_CANDIDATES, review_list_query()),
        ],
        ids=["candidates", "candidate_review"],
    )
    async def test_list_groups_match_original_rows(
        self, old_query: str, new_query: str, min_count: int
    ) -> None:
        """Grouped candidate rows match the original text, including the empty case.

        Two candidates share a key and each has evidence on one chunk. With
        ``min_count`` above their summed count, both queries return nothing.
        """
        tag = self.tag
        kind = f"{tag}-kind"
        chunk_id = f"{tag}-chunk"
        await _seed_chunk(self.store, chunk_id)
        for index, count in enumerate((2, 3)):
            await _seed_candidate(
                self.store,
                candidate_id=f"{tag}-cand-{index}",
                key=f"{tag}-key",
                chunk_id=chunk_id,
                count=count,
                kind=kind,
                created_at="2026-01-01T00:00:00+00:00",
            )
        params = {
            "kind": kind,
            "label": None,
            "state": None,
            "min_count": min_count,
            "skip": 0,
            "limit": 10,
            "job_id": None,
        }
        old_rows = await self.store.execute_read(old_query, params)
        new_rows = await self.store.execute_read(new_query, params)

        assert _normalize_list_rows(new_rows) == _normalize_list_rows(old_rows)
        assert len(new_rows) == (1 if min_count == 1 else 0)

    @pytest.mark.parametrize(
        "params",
        [
            {"rejected": True, "older_than": None, "below_count": None},
            {
                "rejected": False,
                "older_than": "2024-03-01T10:00:00.250000+00:00",
                "below_count": None,
            },
            {"rejected": False, "older_than": None, "below_count": 2},
        ],
        ids=["rejected", "older_than", "below_count"],
    )
    async def test_prune_match_counts_match_original_text(
        self, params: dict[str, Any]
    ) -> None:
        """Prune counts match the original text for each criterion and format.

        Groups cover a rejected candidate, an old pending candidate, a pending
        candidate whose fractional and whole-second timestamps mix, a fresh
        pending candidate, and an approved candidate that is never pruned.
        """
        tag = self.tag
        chunk_id = f"{tag}-chunk"
        await _seed_chunk(self.store, chunk_id)
        fresh = datetime.now(UTC).isoformat()
        seeds = [
            ("rej", "rejected", 1, "2026-01-01T00:00:00+00:00"),
            ("old", "pending", 1, "2020-01-01T00:00:00+00:00"),
            ("mix-a", "pending", 1, "2024-03-01T10:00:00.500000+00:00"),
            ("mix-b", "pending", 1, "2024-03-01T10:00:00+00:00"),
            ("fresh", "pending", 5, fresh),
            ("approved", "approved", 1, "2020-01-01T00:00:00+00:00"),
        ]
        for name, state, count, created_at in seeds:
            await _seed_candidate(
                self.store,
                candidate_id=f"{tag}-{name}",
                key=f"{tag}-{name}",
                chunk_id=chunk_id,
                state=state,
                count=count,
                created_at=created_at,
            )
        old_rows = await self.store.execute_read(OLD_MATCH_PRUNABLE, params)
        new_rows = await self.store.execute_read(match_prunable_query(), params)

        assert new_rows == old_rows
        assert new_rows[0]["matched"] >= 1

    async def test_delete_prunable_removes_same_groups_as_original_text(self) -> None:
        """The delete builder removes the groups the original text removes.

        Each run seeds its own old pending group and a fresh one, then deletes
        with an ``older_than`` cutoff that only the old group passes. Both runs
        must report one deleted group and keep the fresh group.
        """
        cutoff = "2024-03-01T10:00:00.250000+00:00"
        outcomes = {}
        for variant, query in (
            ("old", OLD_DELETE_PRUNABLE),
            ("new", delete_prunable_query()),
        ):
            tag = f"{self.tag}-{variant}"
            chunk_id = f"{tag}-chunk"
            await _seed_chunk(self.store, chunk_id)
            for name, created_at in (
                ("old", "2020-01-01T00:00:00+00:00"),
                ("fresh", datetime.now(UTC).isoformat()),
            ):
                await _seed_candidate(
                    self.store,
                    candidate_id=f"{tag}-{name}",
                    key=f"{tag}-{name}",
                    chunk_id=chunk_id,
                    created_at=created_at,
                )
            rows = await self.store.execute_write(
                query,
                {"rejected": False, "older_than": cutoff, "below_count": None},
            )
            remaining = await self.store.execute_read(
                f"MATCH (c:{CANDIDATE_LABEL}) WHERE c.key IN $keys "
                "RETURN c.key AS key ORDER BY key",
                {"keys": [f"{tag}-old", f"{tag}-fresh"]},
            )
            outcomes[variant] = (
                rows[0]["deleted"],
                [r["key"].removeprefix(tag) for r in remaining],
            )

        assert outcomes["old"] == outcomes["new"]
        assert outcomes["new"][0] == 1
        assert outcomes["new"][1] == ["-fresh"]

    async def test_prune_older_than_compares_utc_stored_timestamps(self) -> None:
        """A cutoff given in another UTC offset selects the same groups.

        Stored ``created_at`` values are UTC ISO strings. The cutoff is built
        from an aware time in UTC+05:00, so its wall-clock digits differ from
        the stored digits. One group is one hour older than the cutoff and one
        is one hour newer. Only the older group must be counted.
        """
        tag = self.tag
        chunk_id = f"{tag}-chunk"
        await _seed_chunk(self.store, chunk_id)
        reference = datetime.now(UTC)
        local_now = reference.astimezone(timezone(timedelta(hours=5)))
        cutoff_age = timedelta(days=5)

        before = await prune_candidates(
            self.store, pending_older_than_days=5, now=local_now
        )
        await _seed_candidate(
            self.store,
            candidate_id=f"{tag}-older",
            key=f"{tag}-older",
            chunk_id=chunk_id,
            created_at=(reference - cutoff_age - timedelta(hours=1)).isoformat(),
        )
        await _seed_candidate(
            self.store,
            candidate_id=f"{tag}-newer",
            key=f"{tag}-newer",
            chunk_id=chunk_id,
            created_at=(reference - cutoff_age + timedelta(hours=1)).isoformat(),
        )
        after = await prune_candidates(
            self.store, pending_older_than_days=5, now=local_now
        )

        assert after.matched - before.matched == 1
