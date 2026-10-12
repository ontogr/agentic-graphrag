"""Tag clearing and rollback of one Cutover Job's rows, against real Neo4j.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). Every row a test
creates carries a unique ``probe`` value, and the test deletes those rows at
the end.
"""

import importlib.util
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from agrag.common.data_models.candidate import CANDIDATE_LABEL
from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL
from agrag.cypher.entities import MERGE_ALIAS_LABEL, NODE_IDENTITY_LABEL
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.ingestion._pending_rows import clear_job_tags, rollback_job_rows


neo4j_missing = importlib.util.find_spec("neo4j") is None

pytestmark = [
    pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed"),
    pytest.mark.asyncio(loop_scope="module"),
]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def store() -> AsyncIterator[GraphStore]:
    """Open one connected store for the module."""
    graph_store = build_graph_store("neo4j")
    await graph_store.connect()
    try:
        yield graph_store
    finally:
        await graph_store.close()


async def _drop(store: GraphStore, tag: str) -> None:
    """Delete every row one test created."""
    await store.execute_write("MATCH (n {probe: $tag}) DETACH DELETE n", {"tag": tag})


async def _node_tags(store: GraphStore, tag: str) -> dict[str, str | None]:
    """Map each probe node's name to its pending job id, or None."""
    rows = await store.execute_read(
        "MATCH (n {probe: $tag}) RETURN n.name AS name, n._pending_job_id AS pending",
        {"tag": tag},
    )
    return {row["name"]: row["pending"] for row in rows}


async def _relation_rows(store: GraphStore, tag: str) -> list[dict[str, Any]]:
    """Return each probe relationship's name and bookkeeping, by name."""
    return await store.execute_read(
        "MATCH ()-[r {probe: $tag}]->() RETURN r.name AS name, r.active AS active, "
        "r._pending_job_id AS pending, r._pending_created AS created, "
        "r._pending_previous_active AS previous ORDER BY name",
        {"tag": tag},
    )


async def _seed_committed_and_other_job(
    store: GraphStore, tag: str, other: UUID
) -> None:
    """Create committed nodes and rows that belong to another job."""
    await store.execute_write(
        f"CREATE (:{NODE_IDENTITY_LABEL} {{name: 'committed', probe: $tag, id: $id}}) "
        f"CREATE (:{NODE_IDENTITY_LABEL} "
        "{name: 'other', probe: $tag, id: $other_id, _pending_job_id: $other})",
        {"tag": tag, "id": str(uuid4()), "other_id": str(uuid4()), "other": str(other)},
    )
    await store.execute_write(
        "MATCH (other {name: 'other', probe: $tag}), "
        "(committed {name: 'committed', probe: $tag}) "
        "CREATE (other)-[:PendingProbeA {name: 'a-other', probe: $tag, active: true, "
        "_pending_job_id: $other}]->(committed)",
        {"tag": tag, "other": str(other)},
    )


class TestClearJobTags:
    """clear_job_tags removes one job's tags and leaves the rest alone."""

    async def test_removes_only_this_jobs_node_and_relationship_tags(
        self, store: GraphStore
    ) -> None:
        """Tags of other jobs and committed rows keep their values."""
        tag, job, other = uuid4().hex, uuid4(), uuid4()
        try:
            await _seed_committed_and_other_job(store, tag, other)
            await store.execute_write(
                f"CREATE (:{NODE_IDENTITY_LABEL} {{name: 'identity', probe: $tag, "
                "id: randomUUID(), _pending_job_id: $job}) "
                f"CREATE (:{MERGE_ALIAS_LABEL} {{name: 'alias', probe: $tag, "
                "id: randomUUID(), _pending_job_id: $job}) "
                f"CREATE (:{CANDIDATE_LABEL} {{name: 'candidate', probe: $tag, "
                "id: $candidate_id, _pending_job_id: $job})",
                {"tag": tag, "job": str(job), "candidate_id": str(uuid4())},
            )
            await store.execute_write(
                "MATCH (identity {name: 'identity', probe: $tag}), "
                "(committed {name: 'committed', probe: $tag}), "
                "(alias {name: 'alias', probe: $tag}), "
                "(candidate {name: 'candidate', probe: $tag}) "
                "CREATE (identity)-[:PendingProbeA {name: 'a-tagged', probe: $tag, "
                "active: true, _pending_job_id: $job, _pending_created: true}]->"
                "(committed) "
                "CREATE (alias)-[:PendingProbeB {name: 'b-tagged', probe: $tag, "
                "active: true, _pending_job_id: $job, _pending_created: false, "
                "_pending_previous_active: false}]->(candidate) "
                "CREATE (committed)-[:PendingProbeB {name: 'b-committed', "
                "probe: $tag, active: true}]->(candidate)",
                {"tag": tag, "job": str(job)},
            )

            async def clear(txn: GraphStoreTransaction) -> None:
                await clear_job_tags(txn, job_id=job)

            await store.run_in_transaction(clear)

            assert await _node_tags(store, tag) == {
                "alias": None,
                "candidate": None,
                "committed": None,
                "identity": None,
                "other": str(other),
            }
            assert await _relation_rows(store, tag) == [
                {
                    "name": "a-other",
                    "active": True,
                    "pending": str(other),
                    "created": None,
                    "previous": None,
                },
                {
                    "name": "a-tagged",
                    "active": True,
                    "pending": None,
                    "created": None,
                    "previous": None,
                },
                {
                    "name": "b-committed",
                    "active": True,
                    "pending": None,
                    "created": None,
                    "previous": None,
                },
                {
                    "name": "b-tagged",
                    "active": True,
                    "pending": None,
                    "created": None,
                    "previous": None,
                },
            ]
        finally:
            await _drop(store, tag)


class TestRollbackJobRows:
    """rollback_job_rows undoes one job's writes under its lease fence."""

    async def test_deletes_created_rows_restores_reactivated_and_drops_job(
        self, store: GraphStore
    ) -> None:
        """A rolled-back job leaves committed and other-job rows as they were."""
        tag, job, other, token = uuid4().hex, uuid4(), uuid4(), uuid4()
        try:
            await _seed_committed_and_other_job(store, tag, other)
            await store.execute_write(
                f"CREATE (:{NODE_IDENTITY_LABEL} {{name: 'identity', probe: $tag, "
                "id: $identity_id, _pending_job_id: $job}) "
                f"CREATE (:{MERGE_ALIAS_LABEL} {{name: 'alias', probe: $tag, "
                "id: randomUUID(), _pending_job_id: $job}) "
                f"CREATE (:{CANDIDATE_LABEL} {{name: 'candidate', probe: $tag, "
                "id: $candidate_id, _pending_job_id: $job}) "
                f"CREATE (:{CUTOVER_JOB_LABEL} {{name: 'job', probe: $tag, id: $job, "
                "document_key: $key, status: 'rolling_back', lease_token: $token})",
                {
                    "tag": tag,
                    "job": str(job),
                    "identity_id": str(uuid4()),
                    "candidate_id": str(uuid4()),
                    "key": f"probe-{tag}",
                    "token": str(token),
                },
            )
            await store.execute_write(
                "MATCH (committed {name: 'committed', probe: $tag}), "
                "(other {name: 'other', probe: $tag}) "
                "CREATE (committed)-[:PendingProbeA {name: 'a-created', probe: $tag, "
                "active: true, _pending_job_id: $job, _pending_created: true}]->"
                "(other) "
                "CREATE (committed)-[:PendingProbeB {name: 'b-reactivated', "
                "probe: $tag, active: true, _pending_job_id: $job, "
                "_pending_created: false, _pending_previous_active: false}]->"
                "(other)",
                {"tag": tag, "job": str(job)},
            )

            rolled_back = await rollback_job_rows(store, job_id=job, token=token)

            assert rolled_back is True
            assert await _node_tags(store, tag) == {
                "committed": None,
                "other": str(other),
            }
            assert await _relation_rows(store, tag) == [
                {
                    "name": "a-other",
                    "active": True,
                    "pending": str(other),
                    "created": None,
                    "previous": None,
                },
                {
                    "name": "b-reactivated",
                    "active": False,
                    "pending": None,
                    "created": None,
                    "previous": None,
                },
            ]
        finally:
            await _drop(store, tag)

    @pytest.mark.parametrize(
        ("status", "presents_job_token"),
        [("rolling_back", False), ("pending", True)],
        ids=["wrong_token", "not_rolling_back"],
    )
    async def test_returns_false_and_changes_nothing_without_the_fence(
        self, store: GraphStore, status: str, presents_job_token: bool
    ) -> None:
        """A rollback whose token or status does not match deletes nothing."""
        tag, job, token = uuid4().hex, uuid4(), uuid4()
        presented = token if presents_job_token else uuid4()
        try:
            await store.execute_write(
                f"CREATE (:{NODE_IDENTITY_LABEL} {{name: 'identity', probe: $tag, "
                "id: $identity_id, _pending_job_id: $job}) "
                f"CREATE (:{NODE_IDENTITY_LABEL} {{name: 'committed', probe: $tag, "
                "id: $committed_id}) "
                f"CREATE (:{CUTOVER_JOB_LABEL} {{name: 'job', probe: $tag, id: $job, "
                "document_key: $key, status: $status, lease_token: $token})",
                {
                    "tag": tag,
                    "job": str(job),
                    "identity_id": str(uuid4()),
                    "committed_id": str(uuid4()),
                    "key": f"probe-{tag}",
                    "status": status,
                    "token": str(token),
                },
            )

            rolled_back = await rollback_job_rows(store, job_id=job, token=presented)

            assert rolled_back is False
            assert await _node_tags(store, tag) == {
                "committed": None,
                "identity": str(job),
                "job": None,
            }
        finally:
            await _drop(store, tag)
