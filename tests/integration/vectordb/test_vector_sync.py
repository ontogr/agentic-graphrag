"""Integration coverage for graph-owned vector synchronization."""

from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import DeferredWrites
from agrag.common.data_models.vector_record import (
    Distance,
    VectorKind,
    VectorRecord,
    VectorTarget,
)
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.graphdb.errors import GraphStoreFenceError
from agrag.ingestion._deferred import replay_deferred
from agrag.ingestion.vector_sync import VectorSync
from tests.integration._backend import build_test_store
from tests.integration._cutover_job import create_live_job
from tests.integration._fake_vector_store import FakeVectorStore
from tests.integration._vector_backend import build_vector_store, selected_vector_stores


_ENTITY_LABEL = "VectorSyncProbe"


class _DescriptionEmbedder(Embedder):
    """Map the probe descriptions to distinct, stable vectors."""

    model = "vector-sync-test"

    async def dimensions(self) -> int:
        """Return the two-dimensional test vector size."""
        return 2

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Encode the updated description separately from the old one."""
        return [
            [0.0, 1.0] if "updated description" in text else [1.0, 0.0]
            for text in texts
        ]


def _entity(entity_id: UUID, description: str) -> Entity:
    """Build one persisted probe entity."""
    return Entity(
        id=entity_id,
        label=_ENTITY_LABEL,
        name="Orchid",
        properties={"description": description},
    )


def _vector_item(entity: Entity) -> tuple[UUID, list[str], str, dict[str, str]]:
    """Build the guarded vector input for one entity."""
    description = entity.properties.get("description")
    return (
        entity.id,
        [_ENTITY_LABEL],
        entity.embedding_text,
        {
            "expected_name": entity.name,
            "expected_description": str(description) if description else "",
        },
    )


async def _remove_entity(graph_store: GraphStore, entity_id: UUID) -> None:
    """Remove one test entity by its stable graph identity."""
    await graph_store.execute_write(
        f"MATCH (node:{NODE_IDENTITY_LABEL} {{id: $id}}) DETACH DELETE node",
        {"id": str(entity_id)},
    )


class TestVectorSync:
    """External vectors follow committed graph state and preserve live nodes."""

    async def test_repair_adds_missing_vector_without_replacing_existing_record(
        self,
    ) -> None:
        """Repair fills an absent id and leaves a present vector untouched."""
        graph_store = build_test_store()
        vector_store = FakeVectorStore(collection_prefix=uuid4().hex[:8])
        existing_id = uuid4()
        missing_id = uuid4()
        sync = VectorSync(
            store=vector_store,
            embedder=_DescriptionEmbedder(),
            graph_store=graph_store,
        )
        await graph_store.connect()
        try:
            await vector_store.ensure_collection(
                VectorKind.ENTITY,
                dimensions=2,
                distance=Distance.COSINE,
            )
            await graph_store.upsert_nodes(
                _ENTITY_LABEL,
                [
                    _entity(existing_id, "updated description").to_node_record(),
                    _entity(missing_id, "original description").to_node_record(),
                ],
            )
            await vector_store.upsert(
                VectorKind.ENTITY,
                [
                    VectorRecord(
                        id=existing_id,
                        vector=[0.0, -1.0],
                        labels=[_ENTITY_LABEL],
                        text="previous vector",
                    )
                ],
            )

            result = await sync.repair(kinds=[VectorKind.ENTITY])

            counts = result.kinds[VectorKind.ENTITY]
            assert counts.missing >= 1
            assert counts.upserted >= 1
            existing_hit = await vector_store.search(
                VectorKind.ENTITY,
                [0.0, -1.0],
                limit=1,
                labels=[_ENTITY_LABEL],
            )
            missing_hit = await vector_store.search(
                VectorKind.ENTITY,
                [1.0, 0.0],
                limit=1,
                labels=[_ENTITY_LABEL],
            )
            assert existing_hit[0].id == existing_id
            assert existing_hit[0].score == 1.0
            assert missing_hit[0].id == missing_id
            assert missing_hit[0].score == 1.0
        finally:
            await _remove_entity(graph_store, existing_id)
            await _remove_entity(graph_store, missing_id)
            await vector_store.close()
            await graph_store.close()

    @pytest.mark.parametrize("store_name", selected_vector_stores())
    @pytest.mark.parametrize(
        ("prune", "missing_int", "orphan_int"),
        [
            pytest.param(True, 2**128 - 1, 2**128 - 2, id="prune-graph-tail"),
            pytest.param(True, 2**128 - 2, 2**128 - 1, id="prune-store-tail"),
            pytest.param(False, 2**128 - 1, 2**128 - 2, id="keep-orphan-below-head"),
        ],
    )
    async def test_repair_merges_both_id_streams_to_the_end(
        self, store_name: str, prune: bool, missing_int: int, orphan_int: int
    ) -> None:
        """Repair restores a graph-only id and handles a store-only id.

        In each case one stream ends before the other, so the merge must drain
        the remaining ids of whichever side is left. With pruning off, a
        store-only id below the last graph id is kept, and it must not stop the
        merge before the graph-only id is restored.
        """
        graph_store = build_test_store()
        vector_store = build_vector_store(
            store_name, collection_prefix=f"repair_{uuid4().hex}"
        )
        sync = VectorSync(
            store=vector_store,
            embedder=_DescriptionEmbedder(),
            graph_store=graph_store,
        )
        present_ids = [uuid4() for _ in range(1049)]
        missing_id = UUID(int=missing_int)
        orphan_id = UUID(int=orphan_int)
        entity_ids = [*present_ids, missing_id]
        await graph_store.connect()
        await vector_store.initialize()
        try:
            await vector_store.ensure_collection(
                VectorKind.ENTITY,
                dimensions=2,
                distance=Distance.COSINE,
            )
            await graph_store.upsert_nodes(
                _ENTITY_LABEL,
                [
                    _entity(entity_id, "original description").to_node_record()
                    for entity_id in entity_ids
                ],
            )
            await vector_store.upsert(
                VectorKind.ENTITY,
                [
                    VectorRecord(
                        id=item_id,
                        vector=[1.0, 0.0],
                        labels=[_ENTITY_LABEL],
                        text="original description",
                    )
                    for item_id in [*present_ids, orphan_id]
                ],
            )

            result = await sync.repair(kinds=[VectorKind.ENTITY], prune=prune)

            counts = result.kinds[VectorKind.ENTITY]
            assert counts.missing >= 1
            assert counts.pruned == (1 if prune else 0)
            store_ids: list[UUID] = []
            after: UUID | None = None
            while True:
                page = await vector_store.list_ids(
                    VectorKind.ENTITY, after=after, limit=500
                )
                if not page:
                    break
                store_ids.extend(page)
                after = page[-1]
            assert {*present_ids, missing_id} <= set(store_ids)
            assert (orphan_id in store_ids) is not prune
            expected_tail = [missing_id] if prune else sorted([orphan_id, missing_id])
            assert (
                await vector_store.list_ids(
                    VectorKind.ENTITY, after=UUID(int=2**128 - 3), limit=10
                )
                == expected_tail
            )
        finally:
            await graph_store.execute_write(
                f"UNWIND $ids AS id MATCH (node:{NODE_IDENTITY_LABEL} {{id: id}}) "
                "DETACH DELETE node",
                {"ids": [str(entity_id) for entity_id in entity_ids]},
            )
            await vector_store.delete_collection(VectorKind.ENTITY)
            await vector_store.close()
            await graph_store.close()

    async def test_job_syncs_a_deferred_entity_description_after_commit(self) -> None:
        """A committed entity is queued despite the pre-commit text mismatch."""
        graph_store = build_test_store()
        vector_store = FakeVectorStore(collection_prefix=uuid4().hex[:8])
        entity_id = uuid4()
        job_key = f"vector-sync-{entity_id}"
        old_entity = _entity(entity_id, "original description")
        updated_entity = _entity(entity_id, "updated description")
        deferred = DeferredWrites()
        sync = VectorSync(
            store=vector_store,
            embedder=_DescriptionEmbedder(),
            graph_store=graph_store,
        )
        await graph_store.connect()
        try:
            await vector_store.ensure_collection(
                VectorKind.ENTITY,
                dimensions=2,
                distance=Distance.COSINE,
            )
            await graph_store.upsert_nodes(
                _ENTITY_LABEL,
                [old_entity.to_node_record()],
            )
            await sync.upsert_owned(
                VectorKind.ENTITY,
                [_vector_item(old_entity)],
                job_id=None,
                deferred=None,
            )

            job_id = await create_live_job(graph_store, job_key)
            await graph_store.upsert_nodes(
                _ENTITY_LABEL,
                [updated_entity.to_node_record()],
                pending_job_id=job_id,
                deferred=deferred,
            )
            assert deferred.entries

            written = await sync.upsert_owned(
                VectorKind.ENTITY,
                [_vector_item(updated_entity)],
                job_id=job_id,
                deferred=deferred,
            )

            assert written == []
            assert deferred.vector_targets == [
                VectorTarget(kind=VectorKind.ENTITY, id=entity_id)
            ]
            graph_rows = await graph_store.execute_read(
                f"MATCH (node:{NODE_IDENTITY_LABEL} {{id: $id}}) "
                "RETURN node.description AS description",
                {"id": str(entity_id)},
            )
            assert graph_rows == [{"description": "original description"}]
            before_commit = await vector_store.search(
                VectorKind.ENTITY,
                [1.0, 0.0],
                limit=1,
            )
            assert before_commit[0].id == entity_id
            assert before_commit[0].score == 1.0

            async def commit(txn: GraphStoreTransaction) -> None:
                await replay_deferred(txn, deferred)

            await graph_store.run_in_transaction(commit)
            failures = await sync.sync_committed(deferred.vector_targets)

            assert failures == []
            after_commit = await vector_store.search(
                VectorKind.ENTITY,
                [0.0, 1.0],
                limit=1,
            )
            assert after_commit[0].id == entity_id
            assert after_commit[0].score == 1.0
        finally:
            await _remove_entity(graph_store, entity_id)
            await graph_store.execute_write(
                "MATCH (job:CutoverJob {document_key: $key}) DELETE job",
                {"key": job_key},
            )
            await vector_store.close()
            await graph_store.close()

    async def test_job_that_lost_its_lease_writes_no_owned_vector(self) -> None:
        """A job claimed by recovery stores no vector for the rows it still tags.

        The claim leaves the job's tagged node in place until the rollback, so
        the ownership check alone would still let the vector through.
        """
        graph_store = build_test_store()
        vector_store = FakeVectorStore(collection_prefix=uuid4().hex[:8])
        entity = _entity(uuid4(), "original description")
        job_key = f"vector-sync-lost-{entity.id}"
        sync = VectorSync(
            store=vector_store,
            embedder=_DescriptionEmbedder(),
            graph_store=graph_store,
        )
        await graph_store.connect()
        try:
            await vector_store.ensure_collection(
                VectorKind.ENTITY,
                dimensions=2,
                distance=Distance.COSINE,
            )
            job_id = await create_live_job(graph_store, job_key)
            await graph_store.upsert_nodes(
                _ENTITY_LABEL,
                [entity.to_node_record()],
                pending_job_id=job_id,
                deferred=DeferredWrites(),
            )
            await graph_store.execute_write(
                "MATCH (job:CutoverJob {id: $id}) SET job.status = 'rolling_back'",
                {"id": str(job_id)},
            )

            with pytest.raises(GraphStoreFenceError):
                await sync.upsert_owned(
                    VectorKind.ENTITY,
                    [_vector_item(entity)],
                    job_id=job_id,
                    deferred=DeferredWrites(),
                )

            assert await vector_store.list_ids(VectorKind.ENTITY) == []
        finally:
            await _remove_entity(graph_store, entity.id)
            await graph_store.execute_write(
                "MATCH (job:CutoverJob {document_key: $key}) DELETE job",
                {"key": job_key},
            )
            await vector_store.close()
            await graph_store.close()

    async def test_delete_absent_keeps_vectors_for_existing_graph_nodes(self) -> None:
        """A stale-vector cleanup removes only ids absent from the graph."""
        graph_store = build_test_store()
        vector_store = FakeVectorStore(collection_prefix=uuid4().hex[:8])
        existing_id = uuid4()
        absent_id = uuid4()
        sync = VectorSync(
            store=vector_store,
            embedder=_DescriptionEmbedder(),
            graph_store=graph_store,
        )
        await graph_store.connect()
        try:
            await vector_store.ensure_collection(
                VectorKind.ENTITY,
                dimensions=2,
                distance=Distance.COSINE,
            )
            existing = _entity(existing_id, "original description")
            await graph_store.upsert_nodes(
                _ENTITY_LABEL,
                [existing.to_node_record()],
            )
            await vector_store.upsert(
                VectorKind.ENTITY,
                [
                    VectorRecord(
                        id=entity_id,
                        vector=[1.0, 0.0],
                        labels=[_ENTITY_LABEL],
                        text="original description",
                    )
                    for entity_id in (existing_id, absent_id)
                ],
            )

            await sync.delete_absent(
                VectorKind.ENTITY,
                [existing_id, absent_id],
            )

            assert await vector_store.list_ids(VectorKind.ENTITY) == [existing_id]
        finally:
            await _remove_entity(graph_store, existing_id)
            await vector_store.close()
            await graph_store.close()
