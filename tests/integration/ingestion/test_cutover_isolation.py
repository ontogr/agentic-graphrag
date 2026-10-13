"""A Cutover Job never changes a committed entity before its commit, against Neo4j.

Each test runs ``run_cutover_job`` end to end against a real store. A job that
merges a mention into a committed entity changes that entity only when the
job commits, and only if the replay of its deferred writes succeeds.

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

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.graph_record import DeferredWrites
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.cypher.entities import (
    MERGE_ALIAS_LABEL,
    NODE_IDENTITY_LABEL,
    validate_identifier,
)
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.graphdb.errors import GraphStoreWriteConflictError
from agrag.ingestion._cutover import run_cutover_job
from agrag.ingestion.merge import (
    PropertyRules,
    PropertyStrategy,
    apply_merge,
    compute_merge,
)
from agrag.ingestion.settings import CutoverJobSettings


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


def _schema(label: str) -> GraphSchema:
    """Build the smallest schema that declares the probe entity label."""
    return GraphSchema(
        name="cutover-isolation-probe",
        version="1",
        entities=[EntityType(label=label, description="Probe entity.")],
        relations=[],
    )


async def _commit_entity(store: GraphStore, label: str, tag: str) -> Entity:
    """Write one committed entity with one source chunk and no description."""
    entity = Entity(
        id=uuid4(),
        label=label,
        name="Acme",
        properties={"probe": tag, "sector": "water"},
        merge_count=1,
        source_chunk_ids=[uuid4()],
    )
    await store.upsert_nodes(label, [entity.to_node_record()])
    return entity


async def _merge_mention(
    store: GraphStore,
    schema: GraphSchema,
    entity: Entity,
    job_id: UUID,
    deferred: DeferredWrites,
) -> UUID:
    """Fold one mention of the entity into it, as a job's pending write does.

    The mention brings a description the entity lacks and a sector that
    replaces the committed one. Returns the mention's chunk id.
    """
    chunk_id = uuid4()
    plan, _ = await compute_merge(
        existing_entities=[entity],
        mentions=[
            ExtractedEntity(
                chunk_id=chunk_id,
                label=entity.label,
                text="Acme",
                char_start=0,
                char_end=4,
                properties={"description": "Pump maker", "sector": "energy"},
            )
        ],
        schema=schema,
        rules=PropertyRules(default=PropertyStrategy.KEEP_LAST),
        job_id=job_id,
    )
    await apply_merge(
        plan,
        graph_store=store,
        schema=schema,
        pending_job_id=str(job_id),
        deferred=deferred,
    )
    return chunk_id


async def _snapshot(store: GraphStore, node_id: UUID) -> dict[str, Any]:
    """Return the committed fields a merge changes, from one entity node."""
    rows = await store.execute_read(
        f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: $id}}) "
        "RETURN n.name AS name, n.description AS description, n.sector AS sector, "
        "n.source_chunk_ids AS source_chunk_ids, n.merge_count AS merge_count, "
        "n._pending_job_id AS pending_job_id",
        {"id": str(node_id)},
    )
    assert len(rows) == 1
    row = rows[0]
    return {**row, "source_chunk_ids": sorted(row["source_chunk_ids"])}


async def _job_rows(store: GraphStore, key: str) -> list[dict[str, Any]]:
    """Return the cutover job nodes for one document key."""
    return await store.execute_read(
        "MATCH (job:CutoverJob {document_key: $key}) RETURN job.status AS status",
        {"key": key},
    )


async def _cleanup(store: GraphStore, tag: str, label: str, key: str) -> None:
    """Delete every row one test created, including its job and alias rows."""
    await store.execute_write(
        "MATCH (job:CutoverJob {document_key: $key}) DETACH DELETE job",
        {"key": key},
    )
    await store.execute_write("MATCH (n {probe: $tag}) DETACH DELETE n", {"tag": tag})
    await store.execute_write(
        f"MATCH (a:{MERGE_ALIAS_LABEL}) WHERE a.merge_key STARTS WITH $prefix DELETE a",
        {"prefix": f"{label}:"},
    )


def _job_args(
    store: GraphStore,
    key: str,
    *,
    pending_write: Any,
    cleanup: Any,
    deferred: DeferredWrites,
) -> dict[str, Any]:
    """Build the keyword arguments of one add job over a committed entity."""
    return {
        "verb": "add",
        "document_key": key,
        "affected_entity_ids": [],
        "graph_store": store,
        "vector_store": None,
        "vector_collections": [],
        "settings": CutoverJobSettings(),
        "pending_write": pending_write,
        "cleanup": cleanup,
        "deferred": deferred,
    }


class TestCutoverJobLeavesCommittedEntities:
    """A merge into a committed entity is applied at commit or not at all."""

    async def test_failed_job_leaves_a_merged_entity_as_it_was(
        self, store: GraphStore
    ) -> None:
        """A job that merges into a committed entity and then raises changes nothing."""
        tag = uuid4().hex
        label = validate_identifier(f"IsoPerson{tag[:12]}")
        key = f"isolation-{tag}"
        schema = _schema(label)
        deferred = DeferredWrites()
        try:
            entity = await _commit_entity(store, label, tag)
            before = await _snapshot(store, entity.id)

            async def pending(job_id: UUID) -> None:
                await _merge_mention(store, schema, entity, job_id, deferred)
                raise RuntimeError("later stage failed")

            async def cleanup(_: list[UUID], __: list[UUID]) -> str:
                return "cleaned"

            with pytest.raises(RuntimeError, match="later stage failed"):
                await run_cutover_job(
                    **_job_args(
                        store,
                        key,
                        pending_write=pending,
                        cleanup=cleanup,
                        deferred=deferred,
                    )
                )

            assert await _snapshot(store, entity.id) == before
        finally:
            await _cleanup(store, tag, label, key)

    async def test_successful_job_applies_the_merge_at_commit(
        self, store: GraphStore
    ) -> None:
        """A committed job leaves the merged description, sources and count."""
        tag = uuid4().hex
        label = validate_identifier(f"IsoPerson{tag[:12]}")
        key = f"isolation-{tag}"
        schema = _schema(label)
        deferred = DeferredWrites()
        try:
            entity = await _commit_entity(store, label, tag)
            before = await _snapshot(store, entity.id)
            mentioned: list[UUID] = []

            async def pending(job_id: UUID) -> None:
                mentioned.append(
                    await _merge_mention(store, schema, entity, job_id, deferred)
                )

            async def cleanup(_: list[UUID], __: list[UUID]) -> str:
                return "cleaned"

            await run_cutover_job(
                **_job_args(
                    store,
                    key,
                    pending_write=pending,
                    cleanup=cleanup,
                    deferred=deferred,
                )
            )

            assert before["description"] is None
            assert await _snapshot(store, entity.id) == {
                "name": "Acme",
                "description": "Pump maker",
                "sector": "energy",
                "source_chunk_ids": sorted(
                    [*before["source_chunk_ids"], str(mentioned[0])]
                ),
                "merge_count": 2,
                "pending_job_id": None,
            }
        finally:
            await _cleanup(store, tag, label, key)

    async def test_failed_replay_rolls_the_job_back_and_keeps_the_committed_row(
        self, store: GraphStore
    ) -> None:
        """Another job tagging the merged row makes the commit replay fail."""
        tag, other = uuid4().hex, uuid4()
        label = validate_identifier(f"IsoPerson{tag[:12]}")
        key = f"isolation-{tag}"
        schema = _schema(label)
        deferred = DeferredWrites()
        try:
            entity = await _commit_entity(store, label, tag)
            before = await _snapshot(store, entity.id)

            async def pending(job_id: UUID) -> None:
                await _merge_mention(store, schema, entity, job_id, deferred)
                await store.execute_write(
                    f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: $id}}) "
                    "SET n._pending_job_id = $other",
                    {"id": str(entity.id), "other": str(other)},
                )

            async def cleanup(_: list[UUID], __: list[UUID]) -> str:
                return "cleaned"

            with pytest.raises(GraphStoreWriteConflictError):
                await run_cutover_job(
                    **_job_args(
                        store,
                        key,
                        pending_write=pending,
                        cleanup=cleanup,
                        deferred=deferred,
                    )
                )

            assert await _snapshot(store, entity.id) == {
                **before,
                "pending_job_id": str(other),
            }
            assert await _job_rows(store, key) == []
        finally:
            await _cleanup(store, tag, label, key)
