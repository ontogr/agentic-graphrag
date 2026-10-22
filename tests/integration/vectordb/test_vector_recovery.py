"""Vector cleanup and replay across Cutover Job recovery."""

import json
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

import agrag.ingestion._cutover as cutover_module
from agrag.common.data_models.graph_record import DeferredWrites
from agrag.common.data_models.stage_failure import StageFailure
from agrag.common.data_models.vector_record import (
    Distance,
    VectorKind,
    VectorRecord,
    VectorTarget,
    VectorWork,
)
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion._cutover import run_cutover_job
from agrag.ingestion._document_lifecycle import DocumentChange
from agrag.ingestion._resume import resume_incomplete_jobs
from agrag.ingestion.settings import CutoverJobSettings
from agrag.ingestion.vector_sync import VectorSync
from tests.integration._backend import build_test_store
from tests.integration._fake_vector_store import FakeVectorStore


class _FixedEmbedder(Embedder):
    """Return stable three-dimensional chunk embeddings."""

    model = "vector-recovery-test"

    async def dimensions(self) -> int:
        """Return the vector collection dimension."""
        return 3

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one stable vector per input string."""
        return [[1.0, 0.0, 0.0] for _ in texts]


async def _prepare_vector_store() -> FakeVectorStore:
    """Create the chunk collection used by the recovery cases."""
    vector_store = FakeVectorStore(collection_prefix=f"recovery-{uuid4().hex[:8]}")
    await vector_store.initialize()
    await vector_store.ensure_collection(
        VectorKind.CHUNK, dimensions=3, distance=Distance.COSINE
    )
    return vector_store


def _chunk_properties(
    *, chunk_id: UUID, document_id: UUID, text: str, job_id: UUID | None = None
) -> dict[str, object]:
    """Return the stored fields required to read and sync a Chunk."""
    properties: dict[str, object] = {
        "id": str(chunk_id),
        "document_id": str(document_id),
        "content_hash": "a" * 64,
        "index": 0,
        "text": text,
        "provenance": json.dumps(
            {"kind": "text", "char_start": 0, "char_end": len(text)}
        ),
        "heading_path": [],
        "content_kind": "text",
    }
    if job_id is not None:
        properties["_pending_job_id"] = str(job_id)
    return properties


async def _create_chunk(
    graph_store: GraphStore,
    *,
    chunk_id: UUID,
    document_id: UUID,
    text: str,
    job_id: UUID | None = None,
) -> None:
    """Create one graph chunk, optionally owned by a pending job."""
    await graph_store.execute_write(
        "CREATE (chunk:_Node:Chunk) SET chunk = $properties",
        {
            "properties": _chunk_properties(
                chunk_id=chunk_id,
                document_id=document_id,
                text=text,
                job_id=job_id,
            )
        },
    )


async def _no_pending_write(_job_id: UUID) -> None:
    """Represent a purge job with no pending graph writes."""


async def _delete_probe(
    graph_store: GraphStore, *, document_key: str, node_ids: Sequence[UUID]
) -> None:
    """Remove one test's job, document activation and graph nodes."""
    await graph_store.execute_write(
        "MATCH (activation:DocumentActivation {document_key: $document_key}) "
        "DETACH DELETE activation",
        {"document_key": document_key},
    )
    await graph_store.execute_write(
        "MATCH (job:CutoverJob {document_key: $document_key}) DETACH DELETE job",
        {"document_key": document_key},
    )
    if node_ids:
        await graph_store.execute_write(
            "MATCH (node:_Node) WHERE node.id IN $ids DETACH DELETE node",
            {"ids": [str(node_id) for node_id in node_ids]},
        )


class TestVectorRecovery:
    """Committed vector work survives a failed cleanup and graph reopen."""

    async def test_resume_replays_persisted_vector_target_after_cleanup_failure(
        self,
    ) -> None:
        """A fresh resume syncs a target recorded before cleanup failed."""
        document_key = f"vector-recovery://target-{uuid4().hex}"
        document_id, chunk_id = uuid4(), uuid4()
        vector_store = await _prepare_vector_store()
        graph_store = build_test_store()
        await graph_store.connect()
        reopened_store: GraphStore | None = None
        try:
            await _create_chunk(
                graph_store,
                chunk_id=chunk_id,
                document_id=document_id,
                text="recovered vector target",
            )
            deferred = DeferredWrites(
                vector_targets=[VectorTarget(kind=VectorKind.CHUNK, id=chunk_id)]
            )

            async def pending_write(_job_id: UUID) -> None:
                return None

            async def fail_cleanup(
                _affected: list[UUID],
                _seeds: list[UUID],
                _created: list[UUID],
                vector_work: VectorWork,
            ) -> None:
                assert vector_work.targets == [
                    VectorTarget(kind=VectorKind.CHUNK, id=chunk_id)
                ]
                raise RuntimeError("injected cleanup failure")

            with pytest.raises(RuntimeError, match="injected cleanup failure"):
                await run_cutover_job(
                    verb="add",
                    document_key=document_key,
                    affected_entity_ids=[],
                    graph_store=graph_store,
                    settings=CutoverJobSettings(),
                    pending_write=pending_write,
                    cleanup=fail_cleanup,
                    deferred=deferred,
                )

            job_rows = await graph_store.execute_read(
                "MATCH (job:CutoverJob {document_key: $document_key}) "
                "RETURN job.id AS id, job.status AS status, "
                "job.commit_plan AS commit_plan",
                {"document_key": document_key},
            )
            assert len(job_rows) == 1
            job_id = str(job_rows[0]["id"])
            assert job_rows[0]["status"] == "cleaning"
            plan = json.loads(job_rows[0]["commit_plan"])
            assert plan["vector_targets"] == [{"kind": "chunks", "id": str(chunk_id)}]
            assert await vector_store.list_ids(VectorKind.CHUNK) == []

            reopened_store = build_test_store()
            await reopened_store.connect()
            await graph_store.execute_write(
                "MATCH (job:CutoverJob {document_key: $document_key}) "
                "SET job.lease_expires_at = timestamp() - 3600000",
                {"document_key": document_key},
            )
            vector_sync = VectorSync(
                store=vector_store,
                embedder=_FixedEmbedder(),
                graph_store=reopened_store,
            )

            async def resume_cleanup(
                _affected: list[UUID],
                _seeds: list[UUID],
                _created: list[UUID],
                vector_work: VectorWork,
            ) -> list[StageFailure]:
                return await vector_sync.sync_committed(vector_work.targets)

            assert await resume_incomplete_jobs(
                reopened_store, roll_forward=resume_cleanup
            ) == [job_id]
            assert await vector_store.list_ids(VectorKind.CHUNK) == [chunk_id]
            final_rows = await reopened_store.execute_read(
                "MATCH (job:CutoverJob {document_key: $document_key}) "
                "RETURN job.status AS status",
                {"document_key": document_key},
            )
            assert final_rows == [{"status": "done"}]
            assert (
                await resume_incomplete_jobs(
                    reopened_store, roll_forward=resume_cleanup
                )
                == []
            )
        finally:
            if reopened_store is not None:
                await reopened_store.close()
            await _delete_probe(
                graph_store, document_key=document_key, node_ids=[chunk_id]
            )
            await graph_store.close()
            await vector_store.close()

    async def test_resume_rollback_removes_job_tagged_external_vectors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rollback removes vectors for graph nodes abandoned before commit."""
        document_key = f"vector-recovery://rollback-{uuid4().hex}"
        document_id, chunk_id = uuid4(), uuid4()
        vector_store = await _prepare_vector_store()
        graph_store = build_test_store()
        await graph_store.connect()
        reopened_store: GraphStore | None = None
        try:
            vector_sync = VectorSync(
                store=vector_store,
                embedder=_FixedEmbedder(),
                graph_store=graph_store,
            )

            async def abandon_rollback(*_args: object, **_kwargs: object) -> None:
                return None

            monkeypatch.setattr(cutover_module, "_rollback", abandon_rollback)

            async def write_then_crash(job_id: UUID) -> None:
                await _create_chunk(
                    graph_store,
                    chunk_id=chunk_id,
                    document_id=document_id,
                    text="abandoned pending vector",
                    job_id=job_id,
                )
                await vector_store.upsert(
                    VectorKind.CHUNK,
                    [
                        VectorRecord(
                            id=chunk_id,
                            vector=[1.0, 0.0, 0.0],
                            labels=["Chunk"],
                            text="abandoned pending vector",
                        )
                    ],
                )
                raise RuntimeError("injected worker crash")

            async def unused_cleanup(
                _affected: list[UUID],
                _seeds: list[UUID],
                _created: list[UUID],
                _vector_work: VectorWork,
            ) -> None:
                return None

            with pytest.raises(RuntimeError, match="injected worker crash"):
                await run_cutover_job(
                    verb="add",
                    document_key=document_key,
                    affected_entity_ids=[],
                    graph_store=graph_store,
                    settings=CutoverJobSettings(),
                    pending_write=write_then_crash,
                    cleanup=unused_cleanup,
                    deferred=DeferredWrites(),
                    vector_sync=vector_sync,
                )

            job_rows = await graph_store.execute_read(
                "MATCH (job:CutoverJob {document_key: $document_key}) "
                "RETURN job.id AS id, job.status AS status",
                {"document_key": document_key},
            )
            assert len(job_rows) == 1
            job_id = str(job_rows[0]["id"])
            assert job_rows[0]["status"] == "pending"
            assert await vector_store.list_ids(VectorKind.CHUNK) == [chunk_id]

            reopened_store = build_test_store()
            await reopened_store.connect()
            await graph_store.execute_write(
                "MATCH (job:CutoverJob {document_key: $document_key}) "
                "SET job.lease_expires_at = timestamp() - 3600000",
                {"document_key": document_key},
            )
            reopened_sync = VectorSync(
                store=vector_store,
                embedder=_FixedEmbedder(),
                graph_store=reopened_store,
            )
            assert await resume_incomplete_jobs(
                reopened_store, vector_sync=reopened_sync
            ) == [job_id]
            assert await vector_store.list_ids(VectorKind.CHUNK) == []
            remaining = await reopened_store.execute_read(
                "MATCH (node:_Node {id: $chunk_id}) RETURN count(node) AS count",
                {"chunk_id": str(chunk_id)},
            )
            assert remaining == [{"count": 0}]
        finally:
            if reopened_store is not None:
                await reopened_store.close()
            await _delete_probe(
                graph_store, document_key=document_key, node_ids=[chunk_id]
            )
            await graph_store.close()
            await vector_store.close()

    async def test_purge_deletes_chunk_vectors_captured_before_commit(self) -> None:
        """Purge captures the old chunk id and deletes its absent vector."""
        document_key = f"vector-recovery://purge-{uuid4().hex}"
        document_id, chunk_id = uuid4(), uuid4()
        vector_store = await _prepare_vector_store()
        graph_store = build_test_store()
        await graph_store.connect()
        try:
            await graph_store.execute_write(
                "CREATE (document:_Node:Document {id: $document_id, "
                "document_key: $document_key})",
                {"document_id": str(document_id), "document_key": document_key},
            )
            await _create_chunk(
                graph_store,
                chunk_id=chunk_id,
                document_id=document_id,
                text="chunk removed by purge",
            )
            await graph_store.execute_write(
                "MATCH (document:_Node:Document {id: $document_id}) "
                "MATCH (chunk:_Node:Chunk {id: $chunk_id}) "
                "CREATE (document)-[:HAS_PART]->(chunk)",
                {"document_id": str(document_id), "chunk_id": str(chunk_id)},
            )
            await vector_store.upsert(
                VectorKind.CHUNK,
                [
                    VectorRecord(
                        id=chunk_id,
                        vector=[1.0, 0.0, 0.0],
                        labels=["Chunk"],
                        text="chunk removed by purge",
                    )
                ],
            )
            vector_sync = VectorSync(
                store=vector_store,
                embedder=_FixedEmbedder(),
                graph_store=graph_store,
            )
            captured: list[VectorTarget] = []

            async def cleanup(
                _affected: list[UUID],
                _seeds: list[UUID],
                _created: list[UUID],
                vector_work: VectorWork,
            ) -> None:
                captured.extend(vector_work.deletes)
                for kind in {target.kind for target in vector_work.deletes}:
                    await vector_sync.delete_absent(
                        kind,
                        [
                            target.id
                            for target in vector_work.deletes
                            if target.kind is kind
                        ],
                    )

            await run_cutover_job(
                verb="purge_document",
                document_key=document_key,
                affected_entity_ids=[],
                graph_store=graph_store,
                settings=CutoverJobSettings(),
                pending_write=_no_pending_write,
                cleanup=cleanup,
                deferred=DeferredWrites(),
                close_document_node_id=document_id,
                change=DocumentChange(
                    document_node_id=document_id,
                    document_key=document_key,
                    verb="purge",
                    content_hash=None,
                    previous_content_hash=None,
                    version_id=None,
                ),
                vector_sync=vector_sync,
            )

            assert captured == [VectorTarget(kind=VectorKind.CHUNK, id=chunk_id)]
            assert await vector_store.list_ids(VectorKind.CHUNK) == []
            remaining = await graph_store.execute_read(
                "MATCH (chunk:_Node:Chunk {id: $chunk_id}) "
                "RETURN count(chunk) AS count",
                {"chunk_id": str(chunk_id)},
            )
            assert remaining == [{"count": 0}]
        finally:
            await _delete_probe(
                graph_store,
                document_key=document_key,
                node_ids=[document_id, chunk_id],
            )
            await graph_store.close()
            await vector_store.close()
