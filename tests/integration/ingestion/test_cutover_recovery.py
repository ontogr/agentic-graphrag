"""Rollback fencing and interrupted rollback recovery against real Neo4j.

Set NEO4J_URI to an isolated test database. Each case removes only its own
probe rows and writes a JSON snapshot to pytest's temporary directory.
"""

import importlib.util
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from agrag.cypher.cutover_job_write import begin_rollback_query, rollback_job_query
from agrag.graphdb import build_graph_store
from agrag.ingestion._cutover import run_cutover_job
from agrag.ingestion._resume import resume_incomplete_jobs
from agrag.ingestion.settings import CutoverJobSettings


@pytest.mark.skipif(
    importlib.util.find_spec("neo4j") is None, reason="neo4j extra not installed"
)
class TestCutoverRecovery:
    """A destructive rollback requires the current token and rollback state."""

    async def test_applied_commit_with_lost_acknowledgement_finishes_cleanup(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A server commit followed by a driver error retains its closed-edge count."""
        from neo4j import AsyncSession  # noqa: PLC0415

        store = build_graph_store("neo4j")
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

        async def cleanup(_: list[UUID], __: list[UUID]) -> str:
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
                vector_store=None,
                vector_collections=[],
                settings=CutoverJobSettings(),
                pending_write=pending,
                cleanup=cleanup,
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
        store = build_graph_store("neo4j")
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
        store = build_graph_store("neo4j")
        await store.connect()
        job, token, probe = str(uuid4()), str(uuid4()), uuid4().hex
        try:
            await store.execute_write(
                "CREATE (:CutoverJob {id: $job, document_key: $probe, "
                "status: 'rolling_back', lease_token: $token, probe: $probe, "
                "lease_expires_at: datetime() + duration({seconds: $seconds})}) "
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
