"""Crash-recovery integration tests for Cutover Jobs, against real Neo4j.

Each test kills a simulated worker at one of the two points that matter —
after its pending writes but before the atomic commit, and after the commit
but before its cleanup phase finished — then reopens a fresh ``Graph`` on the
same database and asserts the resume hook converges the graph either to
as-if-never-happened or to as-if-completed.

Run against the Docker Compose Neo4j instance from ``docker/docker-compose.ci.yml``
(``make dev-services-up``). The ``skipif`` only guards the missing extra; with
the extra installed the tests expect a reachable Neo4j at the default
``NEO4J_URI``.
"""

import hashlib
import importlib.util
import unicodedata
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

import pytest

import agrag.ingestion.graph as graph_module
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import GENERIC, GraphSchema
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.settings import CutoverJobSettings


neo4j_missing = importlib.util.find_spec("neo4j") is None

_INCOMPLETE_JOB_STATUSES = ["pending", "committed", "cleaning"]


class _FixedEmbedder(Embedder):
    """Deterministic embedder for crash-recovery tests."""

    model = "fixed"

    async def dimensions(self) -> int:
        """Return a small fixed dimension."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector for every text."""
        return [[0.1] * 4 for _ in texts]


class _KeywordExtractor(Extractor):
    """Extractor emitting one distinctive Person mention per matching chunk."""

    def __init__(self, name: str) -> None:
        """Remember the unique probe name to mention."""
        self._name = name

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Mention the probe person when the chunk carries the keyword."""
        if "crashprobe" not in chunk.text.lower():
            return ExtractionResult(entities=[], relations=[], extractor_name="keyword")
        mention = ExtractedEntity(
            chunk_id=chunk.id,  # type: ignore[arg-type]
            label="Person",
            text=self._name,
            char_start=0,
            char_end=len(self._name),
        )
        return ExtractionResult(
            entities=[mention], relations=[], extractor_name="keyword"
        )


class _NoopExtractor(Extractor):
    """Extractor emitting no entities, for purely additive crash tests."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return no entities or relations for any chunk."""
        return ExtractionResult(entities=[], relations=[], extractor_name="noop")


def _content_hash(text: str) -> str:
    """Hash text the same way the inline walk and update() do."""
    return hashlib.sha256(
        unicodedata.normalize("NFKC", text).encode("utf-8")
    ).hexdigest()


def _document(key: str, text: str) -> Document:
    """Build a prose Document carrying an explicit stable key."""
    normalized = unicodedata.normalize("NFKC", text)
    return Document(
        text=normalized,
        title="crash",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=_content_hash(normalized),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(normalized),
        line_count=normalized.count("\n") + 1,
    )


async def _open_graph(
    store: GraphStore, extractor: Extractor, *, lease_ttl_seconds: int = 60
) -> Graph:
    """Open a graph on an already-connected store."""
    return await Graph.open(
        schema=GENERIC,
        graph_store=store,
        embedder=_FixedEmbedder(),
        extractor=extractor,
        cutover_settings=CutoverJobSettings(lease_ttl_seconds=lease_ttl_seconds),
    )


def _kill_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make a failing pending write abandon its job instead of rolling back.

    A real crash takes the rollback path with it: the process is gone
    before it can undo its own tagged writes, which is exactly the state
    the resume hook exists to clean up.
    """

    async def _no_rollback(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(
        "agrag.ingestion._cutover._rollback",
        _no_rollback,
        raising=True,
    )


def _die_after_pending_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kill the worker once its pending writes have landed."""
    real_ingest = graph_module.ingest_chunks

    async def _die(*args: object, **kwargs: object) -> object:
        await real_ingest(*args, **kwargs)
        raise RuntimeError("worker died before commit")

    monkeypatch.setattr(graph_module, "ingest_chunks", _die)


async def _graph_state(store: GraphStore, key: str) -> dict[str, Any]:
    """Return one document's Document and Chunk nodes, plus their PART_OF edges.

    Scoped to a single document key rather than the whole store: these
    tests run alongside others against the same shared Neo4j instance, so
    an unscoped snapshot would race against unrelated concurrent writes.
    Every test using this helper uses ``_NoopExtractor``, so no entity or
    resolution nodes ever exist for these documents and this scope loses
    no coverage.
    """
    nodes = await store.execute_read(
        "OPTIONAL MATCH (d:Document {document_key: $key}) "
        "OPTIONAL MATCH (d)-[:PART_OF]->(c:Chunk) "
        "WITH collect(DISTINCT d) + collect(DISTINCT c) AS ns "
        "UNWIND ns AS n WITH DISTINCT n WHERE n IS NOT NULL "
        "RETURN n.id AS id, labels(n) AS labels, properties(n) AS properties "
        "ORDER BY n.id",
        {"key": key},
    )
    relations = await store.execute_read(
        "MATCH (d:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
        "RETURN d.id AS start_id, c.id AS end_id, type(r) AS type, "
        "properties(r) AS properties ORDER BY d.id, c.id",
        {"key": key},
    )
    return {"nodes": nodes, "relations": relations}


async def _tagged_rows(store: GraphStore, job_id: str) -> tuple[int, int]:
    """Return how many nodes and edges carry one job's pending tag."""
    nodes = await store.execute_read(
        "MATCH (n) WHERE n._pending_job_id = $job_id RETURN count(n) AS n",
        {"job_id": job_id},
    )
    relations = await store.execute_read(
        "MATCH ()-[r]->() WHERE r._pending_job_id = $job_id RETURN count(r) AS n",
        {"job_id": job_id},
    )
    return int(nodes[0]["n"]), int(relations[0]["n"])


async def _job_status(store: GraphStore, key: str) -> str | None:
    """Return one document's job status, or None when no job node remains."""
    rows = await store.execute_read(
        "MATCH (job:CutoverJob {document_key: $key}) RETURN job.status AS status",
        {"key": key},
    )
    return str(rows[0]["status"]) if rows else None


async def _age_lease(store: GraphStore, key: str) -> None:
    """Push a job's lease into the past, as a dead worker's would be."""
    await store.execute_write(
        "MATCH (job:CutoverJob {document_key: $key}) "
        "SET job.lease_expires_at = datetime() - duration('PT1H')",
        {"key": key},
    )


async def _open_chunk_ids(store: GraphStore, key: str) -> set[str]:
    """Return the ids of the chunks the document's current version holds."""
    rows = await store.execute_read(
        "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
        "WHERE r.invalid_at IS NULL RETURN collect(c.id) AS ids",
        {"key": key},
    )
    return {str(chunk_id) for chunk_id in (rows[0]["ids"] if rows else [])}


async def _probe_count(store: GraphStore, name: str) -> int:
    """Return how many live entities carry one probe name."""
    rows = await store.execute_read(
        "MATCH (e:Person {name: $name}) RETURN count(e) AS n", {"name": name}
    )
    return int(rows[0]["n"])


async def _cleanup(store: GraphStore, key: str, probe_name: str | None) -> None:
    """Delete everything one test's document key could have written."""
    await store.execute_write(
        "MATCH (job:CutoverJob {document_key: $key}) DETACH DELETE job",
        {"key": key},
    )
    await store.execute_write(
        "MATCH (d:Document {document_key: $key}) "
        "OPTIONAL MATCH (d)-[:PART_OF]->(c:Chunk) "
        "DETACH DELETE d, c",
        {"key": key},
    )
    if probe_name is not None:
        await store.execute_write(
            "MATCH (e:Person {name: $name}) DETACH DELETE e",
            {"name": probe_name},
        )
        await store.execute_write(
            "MATCH (a:_AgragMergeAlias {merge_key: $merge_key}) DETACH DELETE a",
            {"merge_key": f"Person:{probe_name.strip().casefold()}"},
        )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestCrashBeforeCommit:
    """A worker that dies before its commit leaves nothing behind."""

    async def test_add_rolls_back_to_the_prior_graph(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An interrupted add is deleted on the next open, leaving the graph intact.

        The abandoned add is purely additive — a new document, its chunks,
        and its edges — so rolling it back has to restore the graph exactly
        as it stood before the call.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        existing_key = f"crash://kept-{uuid4().hex}"
        crashed_key = f"crash://lost-{uuid4().hex}"
        try:
            graph = await _open_graph(store, _NoopExtractor())
            await graph.add(
                documents=[_document(existing_key, "crash kept version. " * 60)]
            )
            before = await _graph_state(store, existing_key)

            _kill_recovery(monkeypatch)
            _die_after_pending_writes(monkeypatch)
            with pytest.raises(RuntimeError, match="worker died before commit"):
                await graph.add(
                    documents=[_document(crashed_key, "crash lost version. " * 60)]
                )

            job_id = await store.execute_read(
                "MATCH (job:CutoverJob {document_key: $key}) "
                "RETURN job.id AS id, job.status AS status",
                {"key": crashed_key},
            )
            assert job_id and job_id[0]["status"] == "pending"
            tagged_nodes, tagged_relations = await _tagged_rows(
                store, str(job_id[0]["id"])
            )
            assert tagged_nodes > 0
            assert tagged_relations > 0

            await _age_lease(store, crashed_key)
            recovered_store = build_graph_store("neo4j")
            await recovered_store.connect()
            try:
                await Graph.open(
                    schema=GENERIC,
                    graph_store=recovered_store,
                    embedder=_FixedEmbedder(),
                    extractor=_NoopExtractor(),
                )

                assert await _tagged_rows(store, str(job_id[0]["id"])) == (0, 0)
                assert await _job_status(store, crashed_key) is None
                assert await _graph_state(store, existing_key) == before
            finally:
                await recovered_store.close()
        finally:
            await _cleanup(store, existing_key, None)
            await _cleanup(store, crashed_key, None)
            await store.close()

    async def test_update_rolls_back_without_touching_the_superseded_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An interrupted update leaves the current version and its entity.

        The job wrote new chunks and a new PART_OF version, and also wrote
        over the existing Document node. Rollback may only delete what the
        job created: the Document node and the entity the current version
        mentions both predate the call and must survive it.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        probe_name = f"Zzxqy Crashprobe {uuid4().hex[:8]}"
        key = f"crash://update-{uuid4().hex}"
        first_text = "crashprobe alpha version one. " * 60
        second_text = "crashprobe beta version two, materially different. " * 60
        try:
            graph = await _open_graph(store, _KeywordExtractor(probe_name))
            first = await graph.add(
                documents=[_document(key, first_text)], return_chunks=True
            )
            current_ids = await _open_chunk_ids(store, key)
            assert current_ids == {str(chunk.id) for chunk in first.chunks}
            assert await _probe_count(store, probe_name) == 1

            _kill_recovery(monkeypatch)
            _die_after_pending_writes(monkeypatch)
            with pytest.raises(RuntimeError, match="worker died before commit"):
                await graph.update(key, text=second_text)

            rows = await store.execute_read(
                "MATCH (job:CutoverJob {document_key: $key}) RETURN job.id AS id",
                {"key": key},
            )
            assert rows
            job_id = str(rows[0]["id"])
            assert sum(await _tagged_rows(store, job_id)) > 0

            await _age_lease(store, key)
            recovered_store = build_graph_store("neo4j")
            await recovered_store.connect()
            try:
                await Graph.open(
                    schema=GENERIC,
                    graph_store=recovered_store,
                    embedder=_FixedEmbedder(),
                    extractor=_KeywordExtractor(probe_name),
                )

                assert await _tagged_rows(store, job_id) == (0, 0)
                assert await _job_status(store, key) is None
                rows = await store.execute_read(
                    "MATCH (d:Document {document_key: $key}) "
                    "RETURN count(d) AS n, collect(d.current_content_hash) AS hashes",
                    {"key": key},
                )
                assert rows[0]["n"] == 1
                assert await _open_chunk_ids(store, key) == current_ids
                assert await _probe_count(store, probe_name) == 1
            finally:
                await recovered_store.close()
        finally:
            await _cleanup(store, key, probe_name)
            await store.close()

    async def test_a_live_lease_is_not_recovered(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A running worker's job survives another process opening the graph.

        A pending job whose lease has not lapsed may belong to a worker that
        is still running, so recovery leaves it alone rather than deleting
        the writes underneath it.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        key = f"crash://live-{uuid4().hex}"
        try:
            graph = await _open_graph(store, _NoopExtractor())
            _kill_recovery(monkeypatch)
            _die_after_pending_writes(monkeypatch)
            with pytest.raises(RuntimeError, match="worker died before commit"):
                await graph.add(documents=[_document(key, "crash live job. " * 60)])

            rows = await store.execute_read(
                "MATCH (job:CutoverJob {document_key: $key}) RETURN job.id AS id",
                {"key": key},
            )
            assert rows
            job_id = str(rows[0]["id"])

            recovered_store = build_graph_store("neo4j")
            await recovered_store.connect()
            try:
                await Graph.open(
                    schema=GENERIC,
                    graph_store=recovered_store,
                    embedder=_FixedEmbedder(),
                    extractor=_NoopExtractor(),
                )

                assert await _job_status(store, key) == "pending"
                assert sum(await _tagged_rows(store, job_id)) > 0
            finally:
                await recovered_store.close()
        finally:
            await _cleanup(store, key, None)
            await store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestCrashAfterCommit:
    """A worker that dies after its commit finishes its cleanup on reopen."""

    async def test_roll_forward_finishes_cleanup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Roll-forward prunes the abandoned snapshot, matching a clean run.

        The commit already made the new version current, so recovery runs the
        cleanup phase the dead worker never reached: the entity the
        superseded version alone mentioned is pruned, and the job reaches its
        terminal state. An uninterrupted run of the same update is the
        control.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        control_probe = f"Zzxqy Crashprobe {uuid4().hex[:8]}"
        crashed_probe = f"Zzxqy Crashprobe {uuid4().hex[:8]}"
        control_key = f"crash://control-{uuid4().hex}"
        crashed_key = f"crash://rollforward-{uuid4().hex}"
        first_text = "crashprobe alpha version one. " * 60
        second_text = "replacement beta version two, materially different. " * 60
        try:
            graph = await _open_graph(store, _KeywordExtractor(control_probe))
            await graph.add(documents=[_document(control_key, first_text)])
            control = await graph.update(control_key, text=second_text)
            assert control.no_op is False

            graph = await _open_graph(store, _KeywordExtractor(crashed_probe))
            await graph.add(documents=[_document(crashed_key, first_text)])

            real_prune = Graph._prune_document_entities

            async def _die_in_cleanup(self: Graph, candidates: list[Any]) -> None:
                del self, candidates
                raise RuntimeError("cleanup died after commit")

            monkeypatch.setattr(Graph, "_prune_document_entities", _die_in_cleanup)
            with pytest.raises(RuntimeError, match="cleanup died after commit"):
                await graph.update(crashed_key, text=second_text)
            monkeypatch.setattr(Graph, "_prune_document_entities", real_prune)

            assert await _job_status(store, crashed_key) == "cleaning"
            assert await _probe_count(store, crashed_probe) == 1
            await _age_lease(store, crashed_key)

            recovered_store = build_graph_store("neo4j")
            await recovered_store.connect()
            try:
                await Graph.open(
                    schema=GENERIC,
                    graph_store=recovered_store,
                    embedder=_FixedEmbedder(),
                    extractor=_KeywordExtractor(crashed_probe),
                )

                assert await _job_status(store, crashed_key) == "done"
                assert await _probe_count(store, crashed_probe) == 0
                assert await _probe_count(store, control_probe) == 0
                assert len(await _open_chunk_ids(store, crashed_key)) == len(
                    await _open_chunk_ids(store, control_key)
                )
            finally:
                await recovered_store.close()
        finally:
            await _cleanup(store, control_key, control_probe)
            await _cleanup(store, crashed_key, crashed_probe)
            await store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestRecoveryIsIdempotent:
    """Recovery may run repeatedly, as a crash during recovery would cause."""

    async def test_reopening_twice_changes_nothing_the_second_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A second open finds no incomplete job and leaves the graph alone."""
        store = build_graph_store("neo4j")
        await store.connect()
        key = f"crash://twice-{uuid4().hex}"
        try:
            graph = await _open_graph(store, _NoopExtractor())
            _kill_recovery(monkeypatch)
            _die_after_pending_writes(monkeypatch)
            with pytest.raises(RuntimeError, match="worker died before commit"):
                await graph.add(documents=[_document(key, "crash twice. " * 60)])
            await _age_lease(store, key)

            first_store = build_graph_store("neo4j")
            await first_store.connect()
            try:
                await Graph.open(
                    schema=GENERIC,
                    graph_store=first_store,
                    embedder=_FixedEmbedder(),
                    extractor=_NoopExtractor(),
                )
            finally:
                await first_store.close()
            after_first = await _graph_state(store, key)

            second_store = build_graph_store("neo4j")
            await second_store.connect()
            try:
                await Graph.open(
                    schema=GENERIC,
                    graph_store=second_store,
                    embedder=_FixedEmbedder(),
                    extractor=_NoopExtractor(),
                )
                assert await _graph_state(store, key) == after_first
                assert await _job_status(store, key) is None
            finally:
                await second_store.close()
        finally:
            await _cleanup(store, key, None)
            await store.close()
