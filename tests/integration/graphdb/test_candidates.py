"""Candidate writes aggregate by key and follow cutover job lifetime."""

import importlib.util
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from agrag.common.data_models.candidate import CANDIDATE_LABEL, CandidateRecord
from agrag.common.data_models.graph_record import NodeRecord
from agrag.common.data_models.structure import HAS_PART
from agrag.cypher.candidates import (
    delete_stale_candidates_query,
    list_candidates_query,
)
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.ingestion._pending_rows import clear_job_tags, rollback_job_rows


neo4j_missing = importlib.util.find_spec("neo4j") is None

pytestmark = pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")


@pytest_asyncio.fixture
async def store() -> AsyncIterator[GraphStore]:
    """Open the configured Neo4j store for one test."""
    graph_store = build_graph_store("neo4j")
    await graph_store.connect()
    await graph_store.setup_constraints()
    try:
        yield graph_store
    finally:
        await graph_store.close()


async def _chunk(store: GraphStore, chunk_id: UUID) -> None:
    """Create the chunk required by candidate evidence."""
    await store.upsert_nodes(
        "Chunk",
        [NodeRecord(id=chunk_id, labels=["Chunk"], properties={})],
    )


async def _delete_candidates(store: GraphStore, ids: list[str]) -> None:
    """Remove test candidate nodes by id."""
    await store.execute_write(
        f"MATCH (c:{CANDIDATE_LABEL}) WHERE c.id IN $ids DETACH DELETE c",
        {"ids": ids},
    )


class TestCandidateStore:
    """Candidate store behavior against Neo4j."""

    @staticmethod
    async def test_count_is_immutable_and_same_key_counts_aggregate(
        store: GraphStore,
    ) -> None:
        """Separate writes retain their counts and list as one total."""
        chunks = [uuid4(), uuid4()]
        records = [
            CandidateRecord(
                kind="entity",
                label="Contract",
                text="Master Agreement",
                confidence=0.4,
                reason="entity_band",
                chunk_id=chunks[0],
                count=2,
            ),
            CandidateRecord(
                kind="entity",
                label="Contract",
                text="Master Agreement",
                confidence=0.8,
                reason="entity_band",
                chunk_id=chunks[1],
                count=3,
            ),
        ]
        try:
            for chunk in chunks:
                await _chunk(store, chunk)
            for record in records:
                assert (await store.upsert_candidates([record])).written == 1

            await store.upsert_candidates([records[0].model_copy(update={"count": 99})])
            rows = await store.execute_read(
                list_candidates_query(),
                {
                    "job_id": None,
                    "kind": "entity",
                    "label": "Contract",
                    "state": None,
                    "min_count": 1,
                    "skip": 0,
                    "limit": 10,
                },
            )

            assert len(rows) == 1
            assert rows[0]["count"] == 5
            assert rows[0]["confidence"] == 0.8
            assert set(rows[0]["chunk_ids"]) == {str(chunk) for chunk in chunks}
        finally:
            await _delete_candidates(store, [str(record.id) for record in records])
            await store.execute_write(
                "MATCH (n:Chunk) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(chunk) for chunk in chunks]},
            )

    @staticmethod
    async def test_missing_chunk_is_reported_without_a_candidate(
        store: GraphStore,
    ) -> None:
        """A candidate with no evidence chunk is not written."""
        record = CandidateRecord(
            kind="entity",
            label="Contract",
            text="Master Agreement",
            confidence=0.4,
            reason="entity_band",
            chunk_id=uuid4(),
        )

        result = await store.upsert_candidates([record])

        assert result.written == 0
        assert [failure.error_type for failure in result.failures] == [
            "MissingEndpoint"
        ]
        assert (
            await store.execute_read(
                f"MATCH (c:{CANDIDATE_LABEL} {{id: $id}}) RETURN c.id AS id",
                {"id": str(record.id)},
            )
            == []
        )

    @staticmethod
    async def test_job_commit_makes_candidate_visible_and_rollback_removes_it(
        store: GraphStore,
    ) -> None:
        """Committed tagged rows stay; rolled-back tagged rows disappear."""
        committed_chunk, rollback_chunk = uuid4(), uuid4()
        commit_job, rollback_job = uuid4(), uuid4()
        records = [
            CandidateRecord(
                kind="entity",
                label="Contract",
                text=f"Deal-{uuid4()}",
                confidence=0.4,
                reason="entity_band",
                chunk_id=committed_chunk,
            ),
            CandidateRecord(
                kind="entity",
                label="Contract",
                text=f"Deal-{uuid4()}",
                confidence=0.4,
                reason="entity_band",
                chunk_id=rollback_chunk,
            ),
        ]
        try:
            await _chunk(store, committed_chunk)
            await _chunk(store, rollback_chunk)
            await store.upsert_candidates([records[0]], pending_job_id=commit_job)
            await store.upsert_candidates([records[1]], pending_job_id=rollback_job)

            tagged = await store.execute_read(
                f"MATCH (c:{CANDIDATE_LABEL}) WHERE c.id IN $ids "
                "RETURN count(c) AS count",
                {"ids": [str(record.id) for record in records]},
            )
            assert tagged == [{"count": 2}]

            async def clear(txn: GraphStoreTransaction) -> None:
                await clear_job_tags(txn, job_id=commit_job)

            await store.run_in_transaction(clear)
            visible = await store.execute_read(
                list_candidates_query(),
                {
                    "job_id": None,
                    "kind": None,
                    "label": None,
                    "state": None,
                    "min_count": 1,
                    "skip": 0,
                    "limit": 10,
                },
            )
            visible_ids = {item for row in visible for item in row["ids"]}
            assert str(records[0].id) in visible_ids
            assert str(records[1].id) not in visible_ids

            lease_token = str(uuid4())
            await store.execute_write(
                "CREATE (:CutoverJob {id: $job_id, status: 'rolling_back', "
                "lease_token: $lease_token, "
                "lease_expires_at: datetime() + duration({seconds: 300})})",
                {"job_id": str(rollback_job), "lease_token": lease_token},
            )
            assert await rollback_job_rows(
                store, job_id=rollback_job, token=UUID(lease_token)
            )
            remaining = await store.execute_read(
                f"MATCH (c:{CANDIDATE_LABEL}) WHERE c.id IN $ids RETURN c.id AS id",
                {"ids": [str(record.id) for record in records]},
            )
            assert remaining == [{"id": str(records[0].id)}]
        finally:
            await _delete_candidates(store, [str(record.id) for record in records])
            await store.execute_write(
                "MATCH (n:Chunk) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(committed_chunk), str(rollback_chunk)]},
            )

    @staticmethod
    async def test_reviewed_keys_stay_blocked_and_stale_delete_keeps_reviewed(
        store: GraphStore,
    ) -> None:
        """A reviewed candidate blocks recapture and survives stale cleanup."""
        chunk_id, document_id = uuid4(), uuid4()
        record = CandidateRecord(
            kind="entity",
            label="Contract",
            text=f"Deal-{uuid4()}",
            confidence=0.4,
            reason="entity_band",
            chunk_id=chunk_id,
        )
        recapture = record.model_copy(update={"state": "pending", "id": uuid4()})
        pending_other = record.model_copy(
            update={"text": f"Other-{uuid4()}", "id": uuid4()}
        )
        try:
            await _chunk(store, chunk_id)
            await store.execute_write(
                f"CREATE (d:{NODE_IDENTITY_LABEL}:Document {{id: $document_id}}) "
                f"WITH d MATCH (chunk:{NODE_IDENTITY_LABEL}:Chunk {{id: $chunk_id}}) "
                f"CREATE (d)-[:{HAS_PART}]->(chunk)",
                {"document_id": str(document_id), "chunk_id": str(chunk_id)},
            )
            await store.upsert_candidates([record])
            await store.execute_write(
                f"MATCH (c:{CANDIDATE_LABEL} {{id: $id}}) SET c.state = 'rejected'",
                {"id": str(record.id)},
            )

            blocked = await store.blocked_candidate_keys([record.key])
            recaptured = await store.upsert_candidates([recapture])
            other_written = await store.upsert_candidates([pending_other])
            assert other_written.written == 1
            stale = await store.execute_write(
                delete_stale_candidates_query(), {"document_node_id": str(document_id)}
            )
            state = await store.execute_read(
                f"MATCH (c:{CANDIDATE_LABEL} {{id: $id}}) RETURN c.state AS state",
                {"id": str(record.id)},
            )
            remaining = await store.execute_read(
                f"MATCH (c:{CANDIDATE_LABEL} {{id: $id}}) RETURN c.id AS id",
                {"id": str(pending_other.id)},
            )

            assert blocked == {record.key}
            assert recaptured.written == 0
            assert [failure.error_type for failure in recaptured.failures] == [
                "ReviewedKeyBlocked"
            ]
            assert stale == [{"removed": 1}]
            assert remaining == []
            assert state == [{"state": "rejected"}]
        finally:
            await _delete_candidates(
                store,
                [str(record.id), str(recapture.id), str(pending_other.id)],
            )
            await store.execute_write(
                "MATCH (n) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(chunk_id), str(document_id)]},
            )
