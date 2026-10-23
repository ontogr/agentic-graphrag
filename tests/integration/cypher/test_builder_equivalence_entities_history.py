"""Check entity and history Cypher builders against their pre-rewrite text.

Each test runs the original query text and the current builder output
against the same seeded Neo4j graph and compares the returned rows and the
resulting graph state. Seeded ids carry a per-test tag, and the fixture
deletes every node the test created.
"""

import importlib.util
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.decision import (
    DECISION_LABEL,
    DEPENDS_ON,
    HAS_SUPPORT,
    MADE,
    SUPPORT_LABEL,
)
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY
from agrag.common.data_models.structure import HAS_PART
from agrag.common.data_models.task import (
    HISTORY_RECORD_PROPERTY,
    PROJECT_LABEL,
    TASK_LABEL,
)
from agrag.cypher.decision_review import expand_review_unit_query
from agrag.cypher.entities import (
    NODE_IDENTITY_LABEL,
    fetch_entity_neighbors_query,
    load_chunks_by_id_query,
)
from agrag.cypher.history import create_decision_query
from agrag.cypher.resolution_write import delete_entities_query
from agrag.graphdb.base import GraphStore
from tests.integration._backend import build_test_store


pytestmark = pytest.mark.neo4j_only


neo4j_missing = importlib.util.find_spec("neo4j") is None

# Query text before the rewrite, kept verbatim for comparison.
OLD_FETCH_ENTITY_NEIGHBORS = (
    "UNWIND $ids AS entity_id CALL (entity_id) { MATCH (n:_Node {id: "
    "entity_id})-[r]-(m:_Node) WHERE NOT type(r) IN $exclude_types AND "
    "n._pending_job_id IS NULL AND r._pending_job_id IS NULL AND "
    "m._pending_job_id IS NULL RETURN type(r) AS rel_type, m.name AS "
    "neighbor_name LIMIT $limit } RETURN entity_id, rel_type, neighbor_name"
)
OLD_LOAD_CHUNKS = (
    "UNWIND $ids AS id MATCH (n:_Node:Chunk {id: id}) WHERE (NOT EXISTS { "
    "MATCH (d:_Node:Document)-[p:HAS_PART]->(n) WHERE (p._pending_job_id IS "
    "NULL OR p._pending_job_id = $job_id) } OR EXISTS { MATCH "
    "(d:_Node:Document)-[p:HAS_PART]->(n) WHERE p.invalid_at IS NULL AND "
    "(p._pending_job_id IS NULL OR p._pending_job_id = $job_id) }) AND "
    "(n._pending_job_id IS NULL OR n._pending_job_id = $job_id) RETURN n"
)
OLD_CREATE_DECISION = (
    "MATCH (t:Task {id: $task_id, project_id: $project_id}) CREATE "
    "(t)-[:MADE]->(d:Decision $decision) "
    f"SET d.{HISTORY_RECORD_PROPERTY} = true WITH d UNWIND $supports AS "
    "item CREATE (d)-[:HAS_SUPPORT]->(s:DecisionSupport) SET s = item "
    f"SET s.{HISTORY_RECORD_PROPERTY} = true WITH d, "
    "s, item OPTIONAL MATCH (target:Decision {id: "
    "item.target_decision_id}) FOREACH (_ IN CASE WHEN "
    "item.target_decision_id IS NULL THEN [] ELSE [1] END | CREATE "
    "(d)-[:DEPENDS_ON]->(target)) RETURN d.id AS id"
)
OLD_EXPAND_REVIEW = (
    "MATCH (p:Project {project_id: $project_id}) MATCH (t:Task "
    "{project_id: $project_id})-[:MADE]->(parent:Decision {id: "
    "$decision_id}) CALL (parent, p) { MATCH (child:Decision {status: "
    "'active'})-[:DEPENDS_ON]->(parent) WHERE child.id > "
    "coalesce(parent.review_cursor, '') AND coalesce(child.review_epoch, -1) "
    "<> p.review_epoch WITH child ORDER BY child.id LIMIT $page_limit RETURN "
    "collect(child) AS page } WITH parent, p, page, size(page) = $page_limit "
    "AS more, page[..$child_limit] AS batch FOREACH (child IN batch | SET "
    "child.review_reason = CASE WHEN coalesce(child.review_state, 'clear') = "
    "'needs_review' THEN child.review_reason ELSE 'dependency_review' END, "
    "child.review_state = 'needs_review', child.review_pending = true, "
    "child.review_cursor = CASE WHEN coalesce(child.review_epoch, -1) <> "
    "p.review_epoch THEN null ELSE child.review_cursor END, "
    "child.review_epoch = p.review_epoch) FOREACH (_ IN CASE WHEN "
    "size(batch) > 0 THEN [1] ELSE [] END | SET parent.review_cursor = "
    "batch[-1].id, parent.review_pending = more) RETURN size(batch) AS queued"
)
OLD_DELETE_ENTITIES = (
    "UNWIND $ids AS entity_id MATCH (entity:_Node {id: entity_id}) WHERE NOT "
    "EXISTS { MATCH (chunk:_Node:Chunk)-[:MENTIONED_IN]->(entity) MATCH "
    "(document:_Node:Document)-[part:HAS_PART]->(chunk) WHERE "
    "part.invalid_at IS NULL } OPTIONAL MATCH "
    "(entity)-[mention:MENTIONED_IN]-() OPTIONAL MATCH "
    "(entity)-[membership:RESOLVED_AS]->(:ResolvedEntity) WITH entity, "
    "entity.id AS entity_id, collect(DISTINCT mention) AS mentions, "
    "collect(DISTINCT membership) AS memberships FOREACH (mention IN "
    "mentions | DELETE mention) FOREACH (membership IN memberships | DELETE "
    "membership) WITH entity, entity_id DETACH DELETE entity RETURN entity_id"
)


async def _seed_chunk(store: GraphStore, chunk_id: str) -> None:
    await store.execute_write(
        f"CREATE (:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} {{id: $id}})", {"id": chunk_id}
    )


async def _seed_entity(store: GraphStore, entity_id: str) -> None:
    await store.execute_write(
        f"CREATE (:{NODE_IDENTITY_LABEL} {{id: $id, name: $id}})", {"id": entity_id}
    )


async def _seed_document_edge(
    store: GraphStore,
    *,
    chunk_id: str,
    edge_id: str,
    invalid_at: str | None = None,
    job_id: str | None = None,
) -> None:
    """Attach a chunk to a Document through one HAS_PART edge."""
    await store.execute_write(
        f"MATCH (chunk:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} {{id: $chunk_id}}) "
        f"CREATE (:{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL} {{id: $edge_id + '-doc'}})"
        f"-[part:{HAS_PART}]->(chunk) "
        "SET part.invalid_at = $invalid_at, "
        f"part.{PENDING_JOB_ID_PROPERTY} = $job_id",
        {
            "chunk_id": chunk_id,
            "edge_id": edge_id,
            "invalid_at": invalid_at,
            "job_id": job_id,
        },
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestEntitiesHistoryBuilderEquivalence:
    """Entity and history builders return the same rows and state as before."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Connect a store and remove this test's nodes afterwards."""
        self.store = build_test_store()
        await self.store.connect()
        self.tag = f"ent{uuid4().hex[:12]}"
        yield
        await self.store.execute_write(
            "MATCH (n) WHERE toString(n.id) CONTAINS $tag "
            "OR toString(n.project_id) CONTAINS $tag DETACH DELETE n",
            {"tag": self.tag},
        )
        await self.store.close()

    async def test_neighbor_sample_matches_original_rows(self) -> None:
        """Neighbor rows match the original query for each id and filter.

        The sample excludes relation types in ``$exclude_types`` and pending
        relations. An entity with no neighbors and an unknown id contribute no
        rows, and the sample is capped by ``$limit``.
        """
        tag = self.tag
        for name in ("a", "b", "c", "d", "e"):
            await _seed_entity(self.store, f"{tag}-{name}")
        await self.store.execute_write(
            f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: $a}}), "
            f"(b:{NODE_IDENTITY_LABEL} {{id: $b}}), "
            f"(c:{NODE_IDENTITY_LABEL} {{id: $c}}), "
            f"(e:{NODE_IDENTITY_LABEL} {{id: $e}}) "
            "CREATE (a)-[:KNOWS]->(b) "
            "CREATE (a)-[:KNOWS]->(e) "
            "CREATE (a)-[:EXCLUDED_REL]->(b) "
            f"CREATE (a)-[:WORKS_AT {{{PENDING_JOB_ID_PROPERTY}: 'other-job'}}]->(c)",
            {
                "a": f"{tag}-a",
                "b": f"{tag}-b",
                "c": f"{tag}-c",
                "e": f"{tag}-e",
            },
        )
        ids = [f"{tag}-a", f"{tag}-d", f"{tag}-missing"]
        cases = [
            {"ids": ids, "exclude_types": ["EXCLUDED_REL"], "limit": 10},
            {"ids": ids, "exclude_types": [], "limit": 1},
        ]
        full_old = await self.store.execute_read(OLD_FETCH_ENTITY_NEIGHBORS, cases[0])
        full_new = await self.store.execute_read(
            fetch_entity_neighbors_query(), cases[0]
        )
        as_tuples = sorted(
            (row["entity_id"], row["rel_type"], row["neighbor_name"])
            for row in full_new
        )
        assert as_tuples == sorted(
            (row["entity_id"], row["rel_type"], row["neighbor_name"])
            for row in full_old
        )
        assert as_tuples == [
            (f"{tag}-a", "KNOWS", f"{tag}-b"),
            (f"{tag}-a", "KNOWS", f"{tag}-e"),
        ]

        capped_old = await self.store.execute_read(OLD_FETCH_ENTITY_NEIGHBORS, cases[1])
        capped_new = await self.store.execute_read(
            fetch_entity_neighbors_query(), cases[1]
        )
        assert len(capped_new) == len(capped_old) == 1

    @pytest.mark.parametrize(
        ("job_id", "expected"),
        [
            (
                None,
                {"none", "valid", "otherjob", "myjob", "myjob-invalid"},
            ),
            (
                "job-x",
                {"none", "valid", "otherjob", "myjob"},
            ),
        ],
        ids=["committed_only", "job_scoped"],
    )
    async def test_chunk_load_matches_original_rows(
        self, job_id: str | None, expected: set[str]
    ) -> None:
        """Chunk rows follow the original HAS_PART rule in each visibility mode.

        A chunk with no document, one with a valid committed edge, and one
        whose only edge belongs to another job are returned. A chunk whose
        only edge is invalid is rejected. A chunk with an edge owned by the
        queried job is returned only when that edge is valid.
        """
        tag = self.tag
        chunks = {
            "none": None,
            "valid": {"invalid_at": None, "job_id": None},
            "invalid": {"invalid_at": "2026-01-01T00:00:00+00:00", "job_id": None},
            "otherjob": {"invalid_at": None, "job_id": "job-y"},
            "myjob": {"invalid_at": None, "job_id": "job-x"},
            "myjob-invalid": {
                "invalid_at": "2026-01-01T00:00:00+00:00",
                "job_id": "job-x",
            },
        }
        for name, edge in chunks.items():
            chunk_id = f"{tag}-{name}"
            await _seed_chunk(self.store, chunk_id)
            if edge is not None:
                await _seed_document_edge(
                    self.store,
                    chunk_id=chunk_id,
                    edge_id=f"{tag}-{name}",
                    invalid_at=edge["invalid_at"],
                    job_id=edge["job_id"],
                )
        params = {
            "ids": [f"{tag}-{name}" for name in chunks] + [f"{tag}-missing"],
            "job_id": job_id,
        }
        old_rows = await self.store.execute_read(OLD_LOAD_CHUNKS, params)
        new_rows = await self.store.execute_read(load_chunks_by_id_query(), params)

        assert sorted(row["n"]["id"] for row in new_rows) == sorted(
            row["n"]["id"] for row in old_rows
        )
        assert {row["n"]["id"] for row in new_rows} == {
            f"{tag}-{name}" for name in expected
        }

    async def test_decision_create_matches_original_state(self) -> None:
        """A decision created by the builder has the same stored state as before.

        Each run creates a decision under a task, with one support and one
        dependency on an existing decision. The stored decision, support, and
        dependency must match between the original text and the builder.
        """
        outcomes = {}
        for variant, query in (
            ("old", OLD_CREATE_DECISION),
            ("new", create_decision_query()),
        ):
            tag = f"{self.tag}-{variant}"
            decision_id = f"{tag}-decision"
            target_id = f"{tag}-target"
            await self.store.execute_write(
                f"CREATE (:{PROJECT_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
                "project_id: $project}) "
                f"CREATE (t:{TASK_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
                "id: $task, project_id: $project}) "
                f"CREATE (:{DECISION_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
                "id: $target, project_id: $project})",
                {"project": tag, "task": f"{tag}-task", "target": target_id},
            )
            rows = await self.store.execute_write(
                query,
                {
                    "task_id": f"{tag}-task",
                    "project_id": tag,
                    "decision": {
                        "id": decision_id,
                        "project_id": tag,
                        "status": "active",
                        "choice": "use a",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    },
                    "supports": [
                        {
                            "kind": "document",
                            "ordinal": 0,
                            "current": True,
                            "evidence_id": f"{tag}-ev",
                            "target_decision_id": target_id,
                        }
                    ],
                },
            )
            stored = await self.store.execute_read(
                f"MATCH (d:{DECISION_LABEL} {{id: $id}}) "
                f"OPTIONAL MATCH (d)-[:{HAS_SUPPORT}]->(s:{SUPPORT_LABEL}) "
                f"OPTIONAL MATCH (d)-[:{DEPENDS_ON}]->(t) "
                "RETURN properties(d) AS decision, "
                "collect(DISTINCT properties(s)) AS supports, "
                "collect(DISTINCT t.id) AS dependencies",
                {"id": decision_id},
            )
            decision = dict(stored[0]["decision"])
            decision.pop("id")
            decision.pop("project_id")
            outcomes[variant] = {
                "returned": [row["id"].removeprefix(tag) for row in rows],
                "decision": decision,
                "supports": [
                    {
                        key: value.removeprefix(tag)
                        if isinstance(value, str)
                        else value
                        for key, value in support.items()
                    }
                    for support in stored[0]["supports"]
                ],
                "dependencies": [
                    dep.removeprefix(tag) for dep in stored[0]["dependencies"]
                ],
            }
        assert outcomes["old"] == outcomes["new"]
        assert outcomes["new"]["returned"] == ["-decision"]
        assert outcomes["new"]["dependencies"] == ["-target"]

    async def test_review_expansion_flags_same_children_as_original(self) -> None:
        """Expansion flags the same bounded page of children as before.

        A parent has five dependents. One is superseded and one already carries
        the project's review epoch, so neither is flagged. Of the rest, the
        page limit allows three and the child limit flags two, which leaves the
        parent cursor on the second child and pending for more.
        """
        outcomes = {}
        for variant, query in (
            ("old", OLD_EXPAND_REVIEW),
            ("new", expand_review_unit_query()),
        ):
            tag = f"{self.tag}-{variant}"
            project = tag
            await self.store.execute_write(
                f"CREATE (p:{PROJECT_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
                "project_id: $project, review_epoch: 3}) "
                f"CREATE (t:{TASK_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
                "project_id: $project}) "
                f"CREATE (t)-[:{MADE}]->(:{DECISION_LABEL} "
                f"{{{HISTORY_RECORD_PROPERTY}: true, id: $parent, "
                "project_id: $project, status: 'active'})",
                {"project": project, "parent": f"{tag}-parent"},
            )
            children = {
                "c00": "active",
                "c01": "active",
                "c02": "active",
                "c03": "superseded",
                "c04": "active",
            }
            for name, status in children.items():
                epoch = 3 if name == "c04" else None
                await self.store.execute_write(
                    f"MATCH (parent:{DECISION_LABEL} {{id: $parent}}) "
                    f"CREATE (child:{DECISION_LABEL} "
                    f"{{{HISTORY_RECORD_PROPERTY}: true, id: $child, "
                    "project_id: $project, status: $status, review_epoch: $epoch}) "
                    f"CREATE (child)-[:{DEPENDS_ON}]->(parent)",
                    {
                        "parent": f"{tag}-parent",
                        "child": f"{tag}-{name}",
                        "project": project,
                        "status": status,
                        "epoch": epoch,
                    },
                )
            await self.store.execute_write(
                query,
                {
                    "project_id": project,
                    "decision_id": f"{tag}-parent",
                    "page_limit": 3,
                    "child_limit": 2,
                },
            )
            rows = await self.store.execute_read(
                f"MATCH (d:{DECISION_LABEL}) WHERE d.project_id = $project "
                "RETURN d.id AS id, d.review_state AS state, "
                "d.review_pending AS pending, d.review_cursor AS cursor "
                "ORDER BY id",
                {"project": project},
            )
            outcomes[variant] = [
                {
                    "id": row["id"].removeprefix(tag),
                    "state": row["state"],
                    "pending": row["pending"],
                    "cursor": (row["cursor"] or "").removeprefix(tag),
                }
                for row in rows
            ]
        assert outcomes["old"] == outcomes["new"]
        flagged = {row["id"]: row["state"] for row in outcomes["new"]}
        assert flagged["-c00"] == "needs_review"
        assert flagged["-c01"] == "needs_review"
        assert flagged["-c02"] is None

    async def test_delete_entities_removes_only_unevidenced_entities(self) -> None:
        """Entities without a valid chunk and document edge are deleted.

        An orphan entity, one whose only chunk has an invalid HAS_PART edge,
        and one whose chunk has no document are removed. An entity with a
        valid edge is kept, and an unknown id yields no row.
        """
        cases = {
            "orphan": None,
            "kept": {"invalid_at": None, "document": True},
            "invalid": {"invalid_at": "2026-01-01T00:00:00+00:00", "document": True},
            "nodoc": {"invalid_at": None, "document": False},
        }
        outcomes = {}
        for variant, query in (
            ("old", OLD_DELETE_ENTITIES),
            ("new", delete_entities_query()),
        ):
            tag = f"{self.tag}-{variant}"
            for name, case in cases.items():
                entity_id = f"{tag}-{name}"
                await _seed_entity(self.store, entity_id)
                if case is None:
                    continue
                chunk_id = f"{tag}-{name}-chunk"
                await _seed_chunk(self.store, chunk_id)
                await self.store.execute_write(
                    f"MATCH (e:{NODE_IDENTITY_LABEL} {{id: $entity}}), "
                    f"(c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} {{id: $chunk}}) "
                    "CREATE (c)-[:MENTIONED_IN]->(e)",
                    {"entity": entity_id, "chunk": chunk_id},
                )
                if case["document"]:
                    await _seed_document_edge(
                        self.store,
                        chunk_id=chunk_id,
                        edge_id=f"{tag}-{name}",
                        invalid_at=case["invalid_at"],
                    )
            ids = [f"{tag}-{name}" for name in cases] + [f"{tag}-missing"]
            rows = await self.store.execute_write(query, {"ids": ids})
            remaining = await self.store.execute_read(
                f"MATCH (e:{NODE_IDENTITY_LABEL}) WHERE e.id IN $ids "
                "RETURN e.id AS id ORDER BY id",
                {"ids": ids},
            )
            outcomes[variant] = (
                sorted(row["entity_id"].removeprefix(tag) for row in rows),
                [row["id"].removeprefix(tag) for row in remaining],
            )
        assert outcomes["old"] == outcomes["new"]
        deleted, remaining_ids = outcomes["new"]
        assert deleted == ["-invalid", "-nodoc", "-orphan"]
        assert remaining_ids == ["-kept"]
