"""A job never changes a committed row before its commit, against real Neo4j.

Each write a job makes over a committed row is held in a ``DeferredWrites``
list and applied by ``replay_deferred`` inside the commit transaction. These
tests read committed values before and after the replay.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). Every node a test
creates carries a unique ``probe`` value, and the test deletes those rows at
the end.
"""

import importlib.util
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.graph_record import (
    DeferredWrites,
    NodeRecord,
    RelationRecord,
)
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.cypher.entities import (
    MERGE_ALIAS_LABEL,
    NODE_IDENTITY_LABEL,
    set_embedding_query,
    validate_identifier,
)
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.graphdb.errors import GraphStoreWriteConflictError
from agrag.ingestion._deferred import replay_deferred, write_or_defer
from agrag.ingestion.merge import apply_merge, compute_merge
from agrag.ingestion.resolved_entities import (
    MatchDecision,
    deactivate_match_and_rebuild,
    matches_id,
    write_matches_and_rebuild,
)
from tests.integration._backend import build_test_store


neo4j_missing = importlib.util.find_spec("neo4j") is None

pytestmark = [
    pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed"),
    pytest.mark.asyncio(loop_scope="module"),
]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def store() -> AsyncIterator[GraphStore]:
    """Open one connected store for the module."""
    graph_store = build_test_store()
    await graph_store.connect()
    try:
        yield graph_store
    finally:
        await graph_store.close()


def _label(tag: str) -> str:
    """Return a unique entity label for one test."""
    return validate_identifier(f"IsoPerson{tag[:12]}")


def _schema(label: str) -> GraphSchema:
    """Build the smallest schema that declares the probe entity label."""
    return GraphSchema(
        name="pending-isolation-probe",
        version="1",
        entities=[EntityType(label=label, description="Probe entity.")],
        relations=[],
    )


async def _props(store: GraphStore, node_id: UUID) -> dict[str, Any]:
    """Return the committed properties of one node, by id."""
    rows = await store.execute_read(
        f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: $id}}) RETURN properties(n) AS props",
        {"id": str(node_id)},
    )
    assert len(rows) == 1
    return dict(rows[0]["props"])


async def _replay(store: GraphStore, deferred: DeferredWrites) -> None:
    """Apply a job's deferred writes in one commit transaction, as a job does."""

    async def replay(txn: GraphStoreTransaction) -> None:
        await replay_deferred(txn, deferred)

    await store.run_in_transaction(replay)


async def _drop(store: GraphStore, tag: str, label: str) -> None:
    """Delete every row one test created, and the derived rows they own."""
    await store.execute_write(
        f"MATCH (:{NODE_IDENTITY_LABEL} {{probe: $tag}})-[:RESOLVED_AS]->"
        "(r:ResolvedEntity) DETACH DELETE r",
        {"tag": tag},
    )
    await store.execute_write("MATCH (n {probe: $tag}) DETACH DELETE n", {"tag": tag})
    await store.execute_write(
        f"MATCH (a:{MERGE_ALIAS_LABEL}) WHERE a.merge_key STARTS WITH $prefix DELETE a",
        {"prefix": f"{label}:"},
    )


async def _commit_entity(
    store: GraphStore,
    label: str,
    tag: str,
    *,
    chunk_id: UUID,
    embedding: list[float] | None = None,
) -> Entity:
    """Write one committed entity with one source chunk and no description."""
    entity = Entity(
        id=uuid4(),
        label=label,
        name="Acme",
        properties={"probe": tag, "sector": "water"},
        merge_count=1,
        source_chunk_ids=[chunk_id],
        embedding=embedding,
    )
    await store.upsert_nodes(label, [entity.to_node_record()])
    return entity


class TestJobsNeverChangeCommittedRows:
    """A job's writes over committed rows stay out of the row until commit."""

    async def test_node_properties_change_only_at_replay(
        self, store: GraphStore
    ) -> None:
        """A node upsert from a job applies its property at commit, not before."""
        tag, job, node_id = uuid4().hex, uuid4(), uuid4()
        label = _label(tag)
        deferred = DeferredWrites()
        try:
            await store.upsert_nodes(
                label,
                [
                    NodeRecord(
                        id=node_id,
                        labels=[label],
                        properties={"v": "old", "probe": tag},
                    )
                ],
            )

            await store.upsert_nodes(
                label,
                [
                    NodeRecord(
                        id=node_id,
                        labels=[label],
                        properties={"v": "new", "probe": tag},
                    )
                ],
                pending_job_id=job,
                deferred=deferred,
            )

            assert (await _props(store, node_id))["v"] == "old"
            assert len(deferred) == 1

            await _replay(store, deferred)

            assert (await _props(store, node_id))["v"] == "new"
        finally:
            await _drop(store, tag, label)

    async def test_survivor_accumulators_change_only_at_replay(
        self, store: GraphStore
    ) -> None:
        """source_chunk_ids and merge_count of a merged entity move at commit."""
        tag, job = uuid4().hex, uuid4()
        label = _label(tag)
        schema = _schema(label)
        first_chunk, second_chunk = uuid4(), uuid4()
        deferred = DeferredWrites()
        try:
            entity = await _commit_entity(store, label, tag, chunk_id=first_chunk)
            plan, _ = await compute_merge(
                existing_entities=[entity],
                mentions=[
                    ExtractedEntity(
                        chunk_id=second_chunk,
                        label=label,
                        text="Acme",
                        char_start=0,
                        char_end=4,
                    )
                ],
                schema=schema,
                job_id=job,
            )

            await apply_merge(
                plan,
                graph_store=store,
                schema=schema,
                pending_job_id=str(job),
                deferred=deferred,
            )

            before = await _props(store, entity.id)
            assert before["source_chunk_ids"] == [str(first_chunk)]
            assert before["merge_count"] == 1

            await _replay(store, deferred)

            after = await _props(store, entity.id)
            assert sorted(after["source_chunk_ids"]) == sorted(
                [str(first_chunk), str(second_chunk)]
            )
            assert after["merge_count"] == 2
        finally:
            await _drop(store, tag, label)

    async def test_relation_evidence_changes_only_at_replay(
        self, store: GraphStore
    ) -> None:
        """Evidence a job adds to a committed relationship lands at commit."""
        tag, job, rel_id = uuid4().hex, uuid4(), uuid4()
        label = _label(tag)
        rel_type = validate_identifier(f"IsoKnows{tag[:12]}")
        first_chunk, second_chunk = uuid4(), uuid4()
        start, end = uuid4(), uuid4()
        deferred = DeferredWrites()
        try:
            await store.upsert_nodes(
                label,
                [
                    NodeRecord(id=start, labels=[label], properties={"probe": tag}),
                    NodeRecord(id=end, labels=[label], properties={"probe": tag}),
                ],
            )
            await store.upsert_relations(
                [
                    RelationRecord(
                        id=rel_id,
                        type=rel_type,
                        start_id=start,
                        end_id=end,
                        properties={"source_chunk_ids": [str(first_chunk)]},
                    )
                ]
            )

            await store.upsert_relations(
                [
                    RelationRecord(
                        id=rel_id,
                        type=rel_type,
                        start_id=start,
                        end_id=end,
                        properties={"source_chunk_ids": [str(second_chunk)]},
                    )
                ],
                pending_job_id=job,
                deferred=deferred,
            )

            assert await _evidence(store, rel_type, rel_id) == [str(first_chunk)]

            await _replay(store, deferred)

            assert sorted(await _evidence(store, rel_type, rel_id)) == sorted(
                [str(first_chunk), str(second_chunk)]
            )
        finally:
            await _drop(store, tag, label)

    async def test_reconfirmed_match_stays_inactive_and_untagged_until_replay(
        self, store: GraphStore
    ) -> None:
        """A job that re-confirms a deactivated match reactivates it at commit."""
        tag, job = uuid4().hex, uuid4()
        label = _label(tag)
        schema = _schema(label)
        first, second = (
            Entity(id=uuid4(), label=label, name=name, properties={"probe": tag})
            for name in ("Ada", "Ada Lovelace")
        )
        match = matches_id(first.id, second.id)
        decision = MatchDecision(
            entity_a_id=first.id,
            entity_b_id=second.id,
            comparator="FuzzyMatch",
            score=0.98,
            decided_at=datetime.now(UTC),
        )
        deferred = DeferredWrites()
        try:
            await store.upsert_nodes(
                label, [first.to_node_record(), second.to_node_record()]
            )
            await write_matches_and_rebuild(
                [decision],
                graph_store=store,
                schema=schema,
                members=[first, second],
            )
            await deactivate_match_and_rebuild(match, graph_store=store, schema=schema)

            await write_matches_and_rebuild(
                [decision],
                graph_store=store,
                schema=schema,
                members=[first, second],
                pending_job_id=str(job),
                deferred=deferred,
            )

            assert await _match_state(store, match) == {
                "active": False,
                "pending": None,
            }

            await _replay(store, deferred)

            assert (await _match_state(store, match))["active"] is True
        finally:
            await _drop(store, tag, label)

    async def test_embedding_is_applied_after_the_text_at_replay(
        self, store: GraphStore
    ) -> None:
        """A vector computed from a job's new description lands after that text."""
        tag, job = uuid4().hex, uuid4()
        label = _label(tag)
        schema = _schema(label)
        chunk = uuid4()
        deferred = DeferredWrites()
        try:
            entity = await _commit_entity(
                store, label, tag, chunk_id=chunk, embedding=[0.1, 0.2, 0.3]
            )
            plan, _ = await compute_merge(
                existing_entities=[entity],
                mentions=[
                    ExtractedEntity(
                        chunk_id=uuid4(),
                        label=label,
                        text="Acme",
                        char_start=0,
                        char_end=4,
                        properties={"description": "Pump maker"},
                    )
                ],
                schema=schema,
                job_id=job,
            )
            await apply_merge(
                plan,
                graph_store=store,
                schema=schema,
                pending_job_id=str(job),
                deferred=deferred,
            )
            await write_or_defer(
                store,
                set_embedding_query("embedding"),
                [
                    {
                        "id": str(entity.id),
                        "vector": [0.4, 0.5, 0.6],
                        "expected_name": "Acme",
                        "expected_description": "Pump maker",
                        "pending_job_id": str(job),
                    }
                ],
                deferred=deferred,
            )

            before = await _props(store, entity.id)
            assert before["embedding"] == pytest.approx([0.1, 0.2, 0.3], abs=1e-6)
            assert "description" not in before

            await _replay(store, deferred)

            after = await _props(store, entity.id)
            assert after["description"] == "Pump maker"
            assert after["embedding"] == pytest.approx([0.4, 0.5, 0.6], abs=1e-6)
        finally:
            await _drop(store, tag, label)

    async def test_replay_fails_when_another_job_tagged_the_row(
        self, store: GraphStore
    ) -> None:
        """A deferred write whose row another job now owns cannot be replayed."""
        tag, owner, job = uuid4().hex, uuid4(), uuid4()
        label = _label(tag)
        node_id = uuid4()
        deferred = DeferredWrites()
        try:
            await store.upsert_nodes(
                label,
                [
                    NodeRecord(
                        id=node_id,
                        labels=[label],
                        properties={"v": "owner", "probe": tag},
                    )
                ],
                pending_job_id=owner,
                deferred=DeferredWrites(),
            )
            await store.upsert_nodes(
                label,
                [
                    NodeRecord(
                        id=node_id,
                        labels=[label],
                        properties={"v": "job", "probe": tag},
                    )
                ],
                pending_job_id=job,
                deferred=deferred,
            )
            unchanged = await _props(store, node_id)

            with pytest.raises(GraphStoreWriteConflictError):
                await _replay(store, deferred)

            assert await _props(store, node_id) == unchanged
            assert unchanged["v"] == "owner"
            assert unchanged["_pending_job_id"] == str(owner)
        finally:
            await _drop(store, tag, label)

    async def test_write_without_a_job_over_another_jobs_row_fails(
        self, store: GraphStore
    ) -> None:
        """A maintenance write reports a conflict instead of changing a pending row."""
        tag, owner = uuid4().hex, uuid4()
        label = _label(tag)
        node_id = uuid4()
        try:
            await store.upsert_nodes(
                label,
                [
                    NodeRecord(
                        id=node_id,
                        labels=[label],
                        properties={"v": "owner", "probe": tag},
                    )
                ],
                pending_job_id=owner,
                deferred=DeferredWrites(),
            )
            before = await _props(store, node_id)

            result = await store.upsert_nodes(
                label,
                [
                    NodeRecord(
                        id=node_id,
                        labels=[label],
                        properties={"v": "maintenance", "probe": tag},
                    )
                ],
            )

            assert result.written == 0
            assert [failure.error_type for failure in result.failures] == [
                "PendingRowConflict"
            ]
            assert await _props(store, node_id) == before
        finally:
            await _drop(store, tag, label)


async def _evidence(store: GraphStore, rel_type: str, rel_id: UUID) -> list[str]:
    """Return the source chunk ids one relationship holds, from committed rows."""
    rows = await store.execute_read(
        f"MATCH ()-[r:{rel_type} {{id: $id}}]->() RETURN r.source_chunk_ids AS ids",
        {"id": str(rel_id)},
    )
    assert len(rows) == 1
    return list(rows[0]["ids"])


async def _match_state(store: GraphStore, match: UUID) -> dict[str, Any]:
    """Return the active flag and pending tag of one MATCHES edge."""
    rows = await store.execute_read(
        "MATCH ()-[r:MATCHES {id: $id}]-() "
        "RETURN DISTINCT r.active AS active, r._pending_job_id AS pending",
        {"id": str(match)},
    )
    assert len(rows) == 1
    return {"active": rows[0]["active"], "pending": rows[0]["pending"]}
