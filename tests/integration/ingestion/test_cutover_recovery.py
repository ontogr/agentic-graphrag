"""Rollback fencing, crash recovery, and commit retries on a real graph store.

Run against the backend named by AGRAG_TEST_BACKENDS. Set NEO4J_URI or
FALKORDB_URL to an isolated test database. Each case removes only its own
probe rows and writes a JSON snapshot to pytest's temporary directory.
"""

import importlib.util
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import DeferredWrites
from agrag.common.data_models.stage_failure import StageFailure
from agrag.common.data_models.vector_record import VectorWork
from agrag.cypher.cutover_job_write import begin_rollback_query, rollback_job_query
from agrag.graphdb.base import GraphStoreTransaction
from agrag.graphdb.errors import (
    GraphStoreConstraintViolationError,
    GraphStoreWriteConflictError,
)
from agrag.ingestion._cutover import CommitPlan, apply_plan_after_fold, run_cutover_job
from agrag.ingestion._resume import resume_incomplete_jobs
from agrag.ingestion.settings import CutoverJobSettings
from tests.integration._backend import build_test_store, selected_backend


@pytest.mark.skipif(
    importlib.util.find_spec("neo4j") is None, reason="neo4j extra not installed"
)
class TestCutoverRecovery:
    """A destructive rollback requires the current token and rollback state."""

    @pytest.mark.neo4j_only
    async def test_applied_commit_with_lost_acknowledgement_finishes_cleanup(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A server commit followed by a driver error retains its closed-edge count."""
        from neo4j import AsyncSession  # noqa: PLC0415

        store = build_test_store()
        await store.connect()
        probe, document = uuid4().hex, uuid4()
        execute_write = AsyncSession.execute_write
        lost_acknowledgement = False

        async def lose_acknowledgement(
            session: AsyncSession, work: Any, *args: Any, **kwargs: Any
        ) -> Any:
            nonlocal lost_acknowledgement
            result = await execute_write(session, work, *args, **kwargs)
            # The commit callback returns a count; ordinary writes return rows.
            if isinstance(result, int) and not lost_acknowledgement:
                lost_acknowledgement = True
                raise RuntimeError("connection lost after server commit")
            return result

        async def pending(job_id: UUID) -> str:
            await store.execute_write(
                "CREATE (:_MergeAlias {probe: $probe, id: randomUUID(), "
                "_pending_job_id: $job})",
                {"probe": probe, "job": str(job_id)},
            )
            return "pending"

        async def cleanup(
            _: list[UUID],
            __: list[UUID],
            ___: list[UUID],
            _vector_work: VectorWork,
        ) -> str:
            return "cleaned"

        try:
            await store.execute_write(
                "CREATE (d:_Node:Document {id: $document, probe: $probe}) "
                "CREATE (c:_Node:Chunk {id: $chunk, probe: $probe}) "
                "CREATE (d)-[:HAS_PART]->(c)",
                {"document": str(document), "chunk": str(uuid4()), "probe": probe},
            )
            monkeypatch.setattr(AsyncSession, "execute_write", lose_acknowledgement)

            result = await run_cutover_job(
                verb="update",
                document_key=probe,
                affected_entity_ids=[],
                graph_store=store,
                settings=CutoverJobSettings(),
                pending_write=pending,
                cleanup=cleanup,
                deferred=DeferredWrites(),
                close_document_node_id=document,
            )

            assert lost_acknowledgement
            assert result == ("pending", "cleaned", 1)
            rows = await store.execute_read(
                "MATCH (j:CutoverJob {document_key: $probe}) "
                "MATCH (n:_MergeAlias {probe: $probe}) "
                "RETURN j.status AS status, j.parts_closed AS parts_closed, "
                "n._pending_job_id AS pending_job",
                {"probe": probe},
            )
            assert rows == [{"status": "done", "parts_closed": 1, "pending_job": None}]
            (tmp_path / "ambiguous-commit.json").write_text(json.dumps(rows))
        finally:
            await store.execute_write(
                "MATCH (n) WHERE n.probe = $probe OR n.document_key = $probe "
                "DETACH DELETE n",
                {"probe": probe},
            )
            await store.close()

    @pytest.mark.parametrize(
        ("status", "owns_token"),
        [("committed", True), ("pending", False), ("rolling_back", False)],
    )
    async def test_rollback_preserves_rows_outside_its_fence(
        self, status: str, owns_token: bool, tmp_path: Path
    ) -> None:
        """Neither rollback step deletes committed or another worker's data."""
        store = build_test_store()
        await store.connect()
        job, token, probe = str(uuid4()), str(uuid4()), uuid4().hex
        params = {"job_id": job, "lease_token": token if owns_token else str(uuid4())}
        try:
            await store.execute_write(
                "CREATE (:CutoverJob {id: $job, document_key: $probe, "
                "status: $status, lease_token: $token, probe: $probe}) "
                "CREATE (:_MergeAlias {probe: $probe, id: randomUUID(), "
                "_pending_job_id: $job})",
                {"job": job, "probe": probe, "status": status, "token": token},
            )

            assert await store.execute_write(begin_rollback_query(), params) == []
            assert await store.execute_write(rollback_job_query(), params) == []
            rows = await store.execute_read(
                "MATCH (j:CutoverJob {id: $job}) "
                "MATCH (n:_MergeAlias {probe: $probe}) "
                "RETURN j.status AS status, j.lease_token AS token, "
                "n._pending_job_id AS pending_job",
                {"job": job, "probe": probe},
            )
            assert rows == [{"status": status, "token": token, "pending_job": job}]
            (tmp_path / "fenced-rollback.json").write_text(json.dumps(rows))
        finally:
            await store.execute_write(
                "MATCH (n {probe: $probe}) DETACH DELETE n", {"probe": probe}
            )
            await store.close()

    @pytest.mark.parametrize("expired", [False, True])
    async def test_recovery_finishes_only_expired_rolling_back_jobs(
        self, expired: bool, tmp_path: Path
    ) -> None:
        """Recovery resumes deletion after a crash, but leaves a live worker alone."""
        store = build_test_store()
        await store.connect()
        job, token, probe = str(uuid4()), str(uuid4()), uuid4().hex
        try:
            await store.execute_write(
                "CREATE (:CutoverJob {id: $job, document_key: $probe, "
                "status: 'rolling_back', lease_token: $token, probe: $probe, "
                "lease_expires_at: timestamp() + $seconds * 1000}) "
                "CREATE (:_MergeAlias {probe: $probe, id: randomUUID(), "
                "_pending_job_id: $job})",
                {
                    "job": job,
                    "token": token,
                    "probe": probe,
                    "seconds": -60 if expired else 300,
                },
            )

            handled = await resume_incomplete_jobs(store)
            rows = await store.execute_read(
                "MATCH (n {probe: $probe}) RETURN count(n) AS remaining",
                {"probe": probe},
            )
            assert handled == ([job] if expired else [])
            assert rows == [{"remaining": 0 if expired else 2}]
            assert await resume_incomplete_jobs(store) == []
            (tmp_path / "rollback-recovery.json").write_text(
                json.dumps({"handled": handled, "rows": rows})
            )
        finally:
            await store.execute_write(
                "MATCH (n {probe: $probe}) DETACH DELETE n", {"probe": probe}
            )
            await store.close()

    async def test_new_run_rolls_back_expired_pending_job_before_claiming(
        self,
    ) -> None:
        """A new run rolls back a dead pending job and reclaims its merge keys."""
        store = build_test_store()
        await store.connect()
        dead_job, probe = str(uuid4()), uuid4().hex
        merge_key = f"probe:{probe}"

        async def pending(job_id: UUID) -> str:
            await store.execute_write(
                "CREATE (:_MergeAlias {probe: $probe, merge_key: $merge_key, "
                "id: randomUUID(), _pending_job_id: $job})",
                {"probe": probe, "merge_key": merge_key, "job": str(job_id)},
            )
            return "pending"

        async def cleanup(
            _: list[UUID],
            __: list[UUID],
            ___: list[UUID],
            _vector_work: VectorWork,
        ) -> str:
            return "cleaned"

        try:
            await store.execute_write(
                f"CREATE (:{CUTOVER_JOB_LABEL} {{id: $job, document_key: $probe, "
                "status: 'pending', verb: 'add', lease_token: $token, "
                "lease_expires_at: timestamp() - 60000, "
                "affected_entity_ids: [], probe: $probe}) "
                "CREATE (:_MergeAlias {probe: $probe, merge_key: $merge_key, "
                "id: randomUUID(), _pending_job_id: $job}) "
                "CREATE (:Chunk:_Node {probe: $probe, id: randomUUID(), "
                "_pending_job_id: $job})",
                {
                    "job": dead_job,
                    "token": str(uuid4()),
                    "probe": probe,
                    "merge_key": merge_key,
                },
            )

            result = await run_cutover_job(
                verb="add",
                document_key=probe,
                affected_entity_ids=[],
                graph_store=store,
                settings=CutoverJobSettings(),
                pending_write=pending,
                cleanup=cleanup,
                deferred=DeferredWrites(),
            )

            assert result[:2] == ("pending", "cleaned")
            jobs = await store.execute_read(
                f"MATCH (j:{CUTOVER_JOB_LABEL} {{document_key: $probe}}) "
                "RETURN j.id AS id, j.status AS status",
                {"probe": probe},
            )
            assert [row["status"] for row in jobs] == ["done"]
            assert jobs[0]["id"] != dead_job
            leftovers = await store.execute_read(
                "MATCH (n {probe: $probe}) WHERE n._pending_job_id = $job "
                "RETURN count(n) AS remaining",
                {"probe": probe, "job": dead_job},
            )
            assert leftovers == [{"remaining": 0}]
            aliases = await store.execute_read(
                "MATCH (n:_MergeAlias {probe: $probe}) "
                "RETURN n.merge_key AS merge_key, n._pending_job_id AS pending_job",
                {"probe": probe},
            )
            assert aliases == [{"merge_key": merge_key, "pending_job": None}]
        finally:
            await store.execute_write(
                "MATCH (n) WHERE n.probe = $probe OR n.document_key = $probe "
                "DETACH DELETE n",
                {"probe": probe},
            )
            await store.close()

    async def test_recovery_passes_recorded_seeds_and_created_entities_to_cleanup(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A commit that died before its flip hands its recorded lists to cleanup."""
        store = build_test_store()
        await store.connect()
        probe, created = uuid4().hex, uuid4()
        low, high = sorted((uuid4(), uuid4()), key=str)
        components = [
            (
                [],
                [
                    Entity(id=high, label="Person", name="high"),
                    Entity(id=low, label="Person", name="low"),
                ],
            )
        ]
        recorded: list[tuple[list[UUID], list[UUID], list[UUID]]] = []

        async def pending(job_id: UUID) -> str:
            return "pending"

        async def cleanup(
            _: list[UUID],
            __: list[UUID],
            ___: list[UUID],
            _vector_work: VectorWork,
        ) -> str:
            return "cleaned"

        async def roll_forward(
            affected: list[UUID],
            seeds: list[UUID],
            created_ids: list[UUID],
            _vector_work: VectorWork,
        ) -> list[StageFailure]:
            # Other jobs in the shared database stay in cleaning for their own open.
            if created not in created_ids:
                return [
                    StageFailure(
                        item_id=str(created),
                        error_type="SkippedJob",
                        error_message="belongs to another test",
                    )
                ]
            recorded.append((affected, seeds, created_ids))
            return []

        async def fail_before_flip(*args: object, **kwargs: object) -> None:
            raise RuntimeError("worker failed during commit")

        try:
            monkeypatch.setattr(
                "agrag.ingestion._cutover.clear_job_tags", fail_before_flip
            )
            with pytest.raises(RuntimeError, match="worker failed during commit"):
                await run_cutover_job(
                    verb="add",
                    document_key=probe,
                    affected_entity_ids=[],
                    graph_store=store,
                    settings=CutoverJobSettings(),
                    pending_write=pending,
                    cleanup=cleanup,
                    deferred=DeferredWrites(),
                    components=components,
                    created_entity_ids=[created],
                )
            monkeypatch.undo()
            if selected_backend() != "neo4j":
                # The lease is still live, so no other worker can claim the job
                # before this read. The row must hold the lists that recovery
                # passes on.
                stored = await store.execute_read(
                    f"MATCH (job:{CUTOVER_JOB_LABEL} {{document_key: $probe}}) "
                    "RETURN job.component_seed_ids AS seeds, "
                    "job.created_entity_ids AS created",
                    {"probe": probe},
                )
                assert stored == [{"seeds": [str(low)], "created": [str(created)]}]
            await store.execute_write(
                f"MATCH (job:{CUTOVER_JOB_LABEL} {{document_key: $probe}}) "
                "SET job.lease_expires_at = timestamp() - 60000",
                {"probe": probe},
            )

            await resume_incomplete_jobs(store, roll_forward=roll_forward)

            if selected_backend() == "neo4j":
                # A Neo4j commit rolls back with its mark, so there is no
                # commit left for recovery to finish.
                assert recorded == []
            else:
                assert recorded == [([], [low], [created])]
            cleanup_inputs = [
                {
                    "seeds": [str(seed) for seed in seeds],
                    "created": [str(entity) for entity in created_ids],
                }
                for _, seeds, created_ids in recorded
            ]
            (tmp_path / "recovered-cleanup.json").write_text(json.dumps(cleanup_inputs))
        finally:
            await store.execute_write(
                "MATCH (n) WHERE n.probe = $probe OR n.document_key = $probe "
                "DETACH DELETE n",
                {"probe": probe},
            )
            await store.close()

    async def test_replay_not_repeated_when_commit_retries(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A retried commit resumes after its replayed write instead of repeating it."""
        store = build_test_store()
        await store.connect()
        probe = uuid4().hex
        failed = False

        async def fail_once_after_replay(
            txn: GraphStoreTransaction, *, job_id: UUID, plan: CommitPlan
        ) -> int:
            nonlocal failed
            if not failed:
                failed = True
                raise GraphStoreConstraintViolationError("injected after replay")
            return await apply_plan_after_fold(txn, job_id=job_id, plan=plan)

        async def pending(job_id: UUID) -> str:
            return "pending"

        async def cleanup(
            _: list[UUID],
            __: list[UUID],
            ___: list[UUID],
            _vector_work: VectorWork,
        ) -> str:
            return "cleaned"

        # The increment accumulates, so a repeated replay step shows as a count
        # above one.
        deferred = DeferredWrites(
            entries=[
                (
                    "MATCH (n:_Probe {probe: $probe}) "
                    "SET n.hits = coalesce(n.hits, 0) + 1 RETURN n.probe AS probe",
                    {"probe": probe},
                )
            ]
        )
        try:
            await store.execute_write(
                "CREATE (:_Probe {probe: $probe, hits: 0})", {"probe": probe}
            )
            monkeypatch.setattr(
                "agrag.ingestion._cutover.apply_plan_after_fold", fail_once_after_replay
            )

            await run_cutover_job(
                verb="add",
                document_key=probe,
                affected_entity_ids=[],
                graph_store=store,
                settings=CutoverJobSettings(),
                pending_write=pending,
                cleanup=cleanup,
                deferred=deferred,
            )

            assert failed
            rows = await store.execute_read(
                "MATCH (n:_Probe {probe: $probe}) RETURN n.hits AS hits",
                {"probe": probe},
            )
            assert rows == [{"hits": 1}]
            (tmp_path / "replay-retry.json").write_text(json.dumps(rows))
        finally:
            await store.execute_write(
                "MATCH (n) WHERE n.probe = $probe OR n.document_key = $probe "
                "DETACH DELETE n",
                {"probe": probe},
            )
            await store.close()

    @pytest.mark.neo4j_only
    async def test_write_conflict_retry_completes_commit(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A write conflict during replay is retried under the lease until it lands."""
        store = build_test_store()
        await store.connect()
        probe = uuid4().hex
        conflicted = False

        # The replayed write sets a flag, so repeating it after the conflict
        # leaves the same graph as the uncrashed run.
        def conflict_once(_rows: Sequence[Mapping[str, Any]]) -> None:
            nonlocal conflicted
            if not conflicted:
                conflicted = True
                raise GraphStoreWriteConflictError("injected conflict during replay")

        async def pending(job_id: UUID) -> str:
            return "pending"

        async def cleanup(
            _: list[UUID],
            __: list[UUID],
            ___: list[UUID],
            _vector_work: VectorWork,
        ) -> str:
            return "cleaned"

        deferred = DeferredWrites(
            entries=[
                (
                    "MATCH (n:_Probe {probe: $probe}) "
                    "SET n.replayed = true RETURN n.probe AS probe",
                    {"probe": probe},
                )
            ]
        )
        try:
            await store.execute_write(
                "CREATE (:_Probe {probe: $probe, replayed: false})", {"probe": probe}
            )
            monkeypatch.setattr(
                "agrag.ingestion._deferred._require_written", conflict_once
            )

            result = await run_cutover_job(
                verb="add",
                document_key=probe,
                affected_entity_ids=[],
                graph_store=store,
                settings=CutoverJobSettings(),
                pending_write=pending,
                cleanup=cleanup,
                deferred=deferred,
            )

            assert conflicted
            assert result[:2] == ("pending", "cleaned")
            jobs = await store.execute_read(
                f"MATCH (j:{CUTOVER_JOB_LABEL} {{document_key: $probe}}) "
                "RETURN j.status AS status",
                {"probe": probe},
            )
            assert jobs == [{"status": "done"}]
            rows = await store.execute_read(
                "MATCH (n:_Probe {probe: $probe}) RETURN n.replayed AS replayed",
                {"probe": probe},
            )
            assert rows == [{"replayed": True}]
            (tmp_path / "write-conflict-retry.json").write_text(
                json.dumps({"job": jobs, "replayed": rows})
            )
        finally:
            await store.execute_write(
                "MATCH (n) WHERE n.probe = $probe OR n.document_key = $probe "
                "DETACH DELETE n",
                {"probe": probe},
            )
            await store.close()
