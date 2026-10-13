"""A Cutover Job never changes a committed entity before its commit, against Neo4j.

Each test runs ``run_cutover_job`` end to end against a real store. A job that
merges a mention into a committed entity changes that entity only when the
job commits, and only if the replay of its deferred writes succeeds.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). Every row a test
creates carries a unique ``probe`` value, and the test deletes those rows at
the end.
"""

import asyncio
import importlib.util
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
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
from agrag.ingestion._merge_stage import _domain_relation_records
from agrag.ingestion.merge import (
    PropertyRules,
    PropertyStrategy,
    apply_merge,
    compute_merge,
    relation_id,
)
from agrag.ingestion.settings import CutoverJobSettings
from agrag.loaders.types import ErrorPolicy


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

            async def cleanup(_: list[UUID], __: list[UUID], ___: list[UUID]) -> str:
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

            async def cleanup(_: list[UUID], __: list[UUID], ___: list[UUID]) -> str:
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

            async def cleanup(_: list[UUID], __: list[UUID], ___: list[UUID]) -> str:
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


async def _commit_named_entity(
    store: GraphStore, label: str, tag: str, name: str
) -> Entity:
    """Write one committed entity with the given name and one source chunk."""
    entity = Entity(
        id=uuid4(),
        label=label,
        name=name,
        properties={"probe": tag},
        merge_count=1,
        source_chunk_ids=[uuid4()],
    )
    await store.upsert_nodes(label, [entity.to_node_record()])
    return entity


async def _cleaned(_: list[UUID], __: list[UUID], ___: list[UUID]) -> str:
    """Stand in for the cleanup stage of a job that has no cleanup work."""
    return "cleaned"


def _relation_writer(
    *,
    store: GraphStore,
    rel_type: str,
    src: Entity,
    tgt: Entity,
    deferred: DeferredWrites,
    written: list[UUID],
) -> Callable[[UUID], Awaitable[None]]:
    """Return a pending write that adds one domain relation from a job.

    Each call appends the relation's chunk id to ``written``.
    """

    async def write(job_id: UUID) -> None:
        chunk_id = uuid4()
        records, _ = await _domain_relation_records(
            [
                ExtractedRelation(
                    chunk_id=chunk_id,
                    label=rel_type,
                    source_index=0,
                    target_index=1,
                )
            ],
            {0: src.id, 1: tgt.id},
            graph_store=store,
            pending_job_id=str(job_id),
            error_policy=ErrorPolicy.SKIP,
            failures=[],
        )
        await store.upsert_relations(records, pending_job_id=job_id, deferred=deferred)
        written.append(chunk_id)

    return write


async def _run_add_job(
    store: GraphStore,
    key: str,
    pending_write: Callable[[UUID], Awaitable[None]],
    deferred: DeferredWrites,
) -> None:
    """Run one add job to its commit."""
    await run_cutover_job(
        **_job_args(
            store,
            key,
            pending_write=pending_write,
            cleanup=_cleaned,
            deferred=deferred,
        )
    )


async def _run_first_rolls_back(
    *,
    store: GraphStore,
    key: str,
    write: Callable[[UUID], Awaitable[None]],
    deferred: DeferredWrites,
) -> None:
    """Run one add job that writes its relation and then raises."""

    async def failing(job_id: UUID) -> None:
        await write(job_id)
        raise RuntimeError("later stage failed")

    with pytest.raises(RuntimeError, match="later stage failed"):
        await _run_add_job(store, key, failing, deferred)


async def _run_while_first_is_pending(
    *,
    store: GraphStore,
    key_a: str,
    write_a: Callable[[UUID], Awaitable[None]],
    deferred_a: DeferredWrites,
    key_b: str,
    write_b: Callable[[UUID], Awaitable[None]],
    deferred_b: DeferredWrites,
) -> None:
    """Hold job A after its write, commit job B, then let job A commit."""
    written = asyncio.Event()
    release = asyncio.Event()

    async def held(job_id: UUID) -> None:
        await write_a(job_id)
        written.set()
        await release.wait()

    task_a = asyncio.create_task(_run_add_job(store, key_a, held, deferred_a))
    try:
        await asyncio.wait_for(written.wait(), timeout=30)
        await _run_add_job(store, key_b, write_b, deferred_b)
        release.set()
        await task_a
    finally:
        release.set()
        await asyncio.wait([task_a])


class TestJobsSharingARelation:
    """Two jobs that add the same relation leave one edge with both sources."""

    @pytest.mark.parametrize(
        "scenario",
        [
            "both_commit",
            "first_rolls_back",
            "second_commits_while_first_is_pending",
        ],
    )
    async def test_two_jobs_adding_the_same_relation_leave_one_edge(
        self, store: GraphStore, scenario: str
    ) -> None:
        """Two jobs that add one relation end with one edge and both chunk ids.

        A rolled back job contributes no chunk id. A job that commits while
        the other is still pending must not fail, and the other job must
        still commit afterwards.
        """
        tag = uuid4().hex
        label = validate_identifier(f"IsoPerson{tag[:12]}")
        rel_type = validate_identifier(f"ISO_REL_{tag[:10].upper()}")
        key_a, key_b = f"isolation-{tag}-a", f"isolation-{tag}-b"
        deferred_a, deferred_b = DeferredWrites(), DeferredWrites()
        written_a: list[UUID] = []
        written_b: list[UUID] = []
        try:
            src = await _commit_entity(store, label, tag)
            tgt = await _commit_named_entity(store, label, tag, "Globex")
            write_a = _relation_writer(
                store=store,
                rel_type=rel_type,
                src=src,
                tgt=tgt,
                deferred=deferred_a,
                written=written_a,
            )
            write_b = _relation_writer(
                store=store,
                rel_type=rel_type,
                src=src,
                tgt=tgt,
                deferred=deferred_b,
                written=written_b,
            )

            if scenario == "both_commit":
                await _run_add_job(store, key_a, write_a, deferred_a)
                await _run_add_job(store, key_b, write_b, deferred_b)
                expected = [*written_a, *written_b]
            elif scenario == "first_rolls_back":
                await _run_first_rolls_back(
                    store=store, key=key_a, write=write_a, deferred=deferred_a
                )
                await _run_add_job(store, key_b, write_b, deferred_b)
                expected = written_b
            else:
                await _run_while_first_is_pending(
                    store=store,
                    key_a=key_a,
                    write_a=write_a,
                    deferred_a=deferred_a,
                    key_b=key_b,
                    write_b=write_b,
                    deferred_b=deferred_b,
                )
                expected = [*written_a, *written_b]

            rows = await store.execute_read(
                f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: $src}})"
                f"-[r:{rel_type}]->"
                f"(b:{NODE_IDENTITY_LABEL} {{id: $tgt}}) "
                "RETURN r.id AS id, r.source_chunk_ids AS chunks, "
                "r._canonical_id AS canonical_id, r._pending_job_id AS tag",
                {"src": str(src.id), "tgt": str(tgt.id)},
            )
            assert len(rows) == 1
            row = rows[0]
            assert row["id"] == str(relation_id(src.id, tgt.id, rel_type))
            assert row["canonical_id"] is None
            assert row["tag"] is None
            assert sorted(row["chunks"]) == sorted(str(chunk) for chunk in expected)
        finally:
            await _cleanup(store, tag, label, key_a)
            await _cleanup(store, tag, label, key_b)
