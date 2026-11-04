"""Concurrent adds and updates that name one entity, against a real graph store.

Runs against the Docker Compose instance from ``docker/docker-compose.ci.yml``.
Each add resolves against committed data only, so the tests hold the commits
back until both adds have reached the point where they meet. Name variants
meet after the commits, when each job resolves what it created. One exact name
meets earlier, when both jobs claim it while pending.
"""

import asyncio
import hashlib
import importlib.util
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Any
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.graphdb.errors import GraphStoreAliasConflictError
from agrag.ingestion import _cutover, _ingest, _merge_stage
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.settings import CutoverJobSettings
from agrag.loaders.types import ErrorPolicy
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration._backend import build_test_store


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _SuffixEmbedder(Embedder):
    """Gives this run's texts one vector and every other text an orthogonal one."""

    model = "suffix"

    def __init__(self, suffix: str) -> None:
        """Remember which suffix marks this run's own texts."""
        self._suffix = suffix

    async def dimensions(self) -> int:
        """Return the dimension of the shared instance's vector indexes."""
        return FAKE_EMBEDDING_DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the run vector for own texts, the foreign one otherwise."""
        return [
            [1.0, 0.0, 0.0, 0.0] if self._suffix in text else [0.0, 1.0, 0.0, 0.0]
            for text in texts
        ]


class _NameByKeywordExtractor(Extractor):
    """Mentions one configured Person name for each keyword in a chunk."""

    def __init__(self, names_by_keyword: dict[str, str]) -> None:
        """Remember which name each keyword produces."""
        self._names_by_keyword = names_by_keyword

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Mention every configured name whose keyword is in the chunk."""
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    chunk_id=chunk.id,  # type: ignore[arg-type]
                    label="Person",
                    text=name,
                    char_start=0,
                    char_end=len(name),
                )
                for keyword, name in self._names_by_keyword.items()
                if keyword in chunk.text.lower()
            ],
            relations=[],
            extractor_name="probe",
        )


def _document(key: str, text: str) -> Document:
    """Build a prose Document carrying an explicit stable key."""
    return Document(
        text=text,
        title="concurrent",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(text),
        line_count=text.count("\n") + 1,
    )


def _hold_commits_until_two_jobs_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold every commit until two jobs have each tried to claim their names.

    Both jobs are then pending when the second claim runs, so one of them meets
    the other's pending alias.
    """
    claimed_job_ids: set[str | None] = set()
    both_claimed = asyncio.Event()
    claim: Callable[..., Awaitable[None]] = _merge_stage.apply_merge
    commit: Callable[..., Awaitable[int]] = _cutover._commit_pending_writes

    async def record_claim(*args: Any, **kwargs: Any) -> None:
        try:
            await claim(*args, **kwargs)
        finally:
            claimed_job_ids.add(kwargs["pending_job_id"])
            if len(claimed_job_ids) >= 2:
                both_claimed.set()

    async def commit_after_both_claimed(**kwargs: Any) -> int:
        await asyncio.wait_for(both_claimed.wait(), timeout=120)
        return await commit(**kwargs)

    monkeypatch.setattr(_merge_stage, "apply_merge", record_claim)
    monkeypatch.setattr(_cutover, "_commit_pending_writes", commit_after_both_claimed)


def _hold_first_claimant_commit(
    monkeypatch: pytest.MonkeyPatch, release: asyncio.Event
) -> asyncio.Event:
    """Hold the commit of the job that first claims its name, until ``release``.

    Every other commit runs at once. The returned event is set when the first
    claim succeeds, so a test can start a conflicting add while the owner is
    still pending.
    """
    owner_job_ids: list[str] = []
    claimed = asyncio.Event()
    claim: Callable[..., Awaitable[None]] = _merge_stage.apply_merge
    commit: Callable[..., Awaitable[int]] = _cutover._commit_pending_writes

    async def record_first_claim(*args: Any, **kwargs: Any) -> None:
        await claim(*args, **kwargs)
        if not owner_job_ids:
            owner_job_ids.append(str(kwargs["pending_job_id"]))
            claimed.set()

    async def hold_owner_commit(**kwargs: Any) -> int:
        if owner_job_ids and str(kwargs["job_id"]) == owner_job_ids[0]:
            await asyncio.wait_for(release.wait(), timeout=120)
        return await commit(**kwargs)

    monkeypatch.setattr(_merge_stage, "apply_merge", record_first_claim)
    monkeypatch.setattr(_cutover, "_commit_pending_writes", hold_owner_commit)
    return claimed


async def _run_adds(*adds: Awaitable[Any]) -> None:
    """Run adds together. If one raises, cancel and await the rest first."""
    tasks = [asyncio.ensure_future(add) for add in adds]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _delete_run(store: GraphStore, *, keys: list[str], name: str) -> None:
    """Delete what one same-name run wrote, then close the store."""
    ids = [
        str(row["id"])
        for row in await store.execute_read(
            "MATCH (e:Person {name: $name}) RETURN e.id AS id", {"name": name}
        )
    ]
    await store.execute_write(
        "MATCH (d:Document) WHERE d.document_key IN $keys "
        "OPTIONAL MATCH (d)-[:HAS_PART]->(c:Chunk) "
        "DETACH DELETE d, c",
        {"keys": keys},
    )
    await store.execute_write(
        "MATCH (e:Person {name: $name}) DETACH DELETE e", {"name": name}
    )
    await store.execute_write(
        "MATCH (node:ResolvedEntity) "
        "WHERE any(member_id IN node.member_ids WHERE member_id IN $ids) "
        "DETACH DELETE node",
        {"ids": ids or ["none"]},
    )
    await store.execute_write(
        "MATCH (a:_MergeAlias {merge_key: $merge_key}) DETACH DELETE a",
        {"merge_key": f"Person:{name.casefold()}"},
    )
    await store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestConcurrentAdds:
    """Two adds that overlap in time and name one entity differently."""

    @staticmethod
    async def test_name_variants_end_in_one_resolved_entity(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Both adds resolve before either commits, yet the variants are linked."""
        store = build_test_store()
        await store.connect()
        suffix = uuid4().hex[:8]
        first_name, second_name = (
            f"Concurrent Quasar {suffix}",
            f"Concurrent Quasars {suffix}",
        )
        first_key, second_key = (
            f"concurrent://{suffix}-one",
            f"concurrent://{suffix}-two",
        )
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_SuffixEmbedder(suffix),
            extractor=_NameByKeywordExtractor(
                {"firstdoc": first_name, "seconddoc": second_name}
            ),
        )
        barrier = asyncio.Barrier(2)
        commit: Callable[..., Awaitable[int]] = _cutover._commit_pending_writes

        async def commit_after_both_resolved(**kwargs: Any) -> int:
            await asyncio.wait_for(barrier.wait(), timeout=120)
            return await commit(**kwargs)

        monkeypatch.setattr(
            _cutover, "_commit_pending_writes", commit_after_both_resolved
        )
        names = [first_name, second_name]
        try:
            await _run_adds(
                graph.add(documents=[_document(first_key, "firstdoc alpha. " * 40)]),
                graph.add(documents=[_document(second_key, "seconddoc beta. " * 40)]),
            )
            entities = await store.execute_read(
                "MATCH (e:Person) WHERE e.name IN $names RETURN e.id AS id",
                {"names": names},
            )
            assert len(entities) == 2
            matches = await store.execute_read(
                "MATCH (a:Person)-[match:MATCHES]->(b:Person) "
                "WHERE a.name IN $names AND b.name IN $names "
                "RETURN match.active AS active",
                {"names": names},
            )
            assert matches == [{"active": True}]
            resolved = await store.execute_read(
                "MATCH (a:Person {name: $first})-[:RESOLVED_AS]->(r:ResolvedEntity) "
                "MATCH (b:Person {name: $second})-[:RESOLVED_AS]->(r) "
                "RETURN size(r.member_ids) AS members",
                {"first": first_name, "second": second_name},
            )
            assert resolved == [{"members": 2}]
        finally:
            ids = [
                str(row["id"])
                for row in await store.execute_read(
                    "MATCH (e:Person) WHERE e.name IN $names RETURN e.id AS id",
                    {"names": names},
                )
            ]
            await store.execute_write(
                "MATCH (d:Document) WHERE d.document_key IN $keys "
                "OPTIONAL MATCH (d)-[:HAS_PART]->(c:Chunk) "
                "DETACH DELETE d, c",
                {"keys": [first_key, second_key]},
            )
            await store.execute_write(
                "MATCH (e:Person) WHERE e.name IN $names DETACH DELETE e",
                {"names": names},
            )
            await store.execute_write(
                "MATCH (node:ResolvedEntity) "
                "WHERE any(member_id IN node.member_ids WHERE member_id IN $ids) "
                "DETACH DELETE node",
                {"ids": ids or ["none"]},
            )
            await store.execute_write(
                "MATCH (a:_MergeAlias) WHERE a.merge_key IN $merge_keys "
                "DETACH DELETE a",
                {"merge_keys": [f"Person:{name.casefold()}" for name in names]},
            )
            await store.close()

    @staticmethod
    async def test_same_new_name_ends_in_one_entity(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The add that loses a name to a pending add merges onto it later."""
        store = build_test_store()
        await store.connect()
        suffix = uuid4().hex[:8]
        name = f"Concurrent Pulsar {suffix}"
        keys = [f"concurrent://{suffix}-one", f"concurrent://{suffix}-two"]
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_SuffixEmbedder(suffix),
            extractor=_NameByKeywordExtractor({"firstdoc": name, "seconddoc": name}),
        )
        _hold_commits_until_two_jobs_claim(monkeypatch)
        try:
            await _run_adds(
                graph.add(documents=[_document(keys[0], "firstdoc alpha. " * 40)]),
                graph.add(documents=[_document(keys[1], "seconddoc beta. " * 40)]),
            )
            entities = await store.execute_read(
                "MATCH (e:Person {name: $name}) RETURN e.id AS id", {"name": name}
            )
            assert len(entities) == 1
            mentioning_documents = await store.execute_read(
                "MATCH (d:Document)-[:HAS_PART]->(:Chunk)-[:MENTIONED_IN]->"
                "(:Person {name: $name}) "
                "RETURN DISTINCT d.document_key AS key",
                {"name": name},
            )
            assert sorted(row["key"] for row in mentioning_documents) == keys
        finally:
            await _delete_run(store, keys=keys, name=name)

    @staticmethod
    async def test_same_new_name_in_concurrent_updates_ends_in_one_entity(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Two updates that add one new name end with both documents on one entity."""
        store = build_test_store()
        await store.connect()
        suffix = uuid4().hex[:8]
        name = f"Concurrent Magnetar {suffix}"
        keys = [f"concurrent://{suffix}-one", f"concurrent://{suffix}-two"]
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_SuffixEmbedder(suffix),
            extractor=_NameByKeywordExtractor({"firstdoc": name, "seconddoc": name}),
        )
        try:
            for key in keys:
                await graph.add(documents=[_document(key, "plain words. " * 40)])
            _hold_commits_until_two_jobs_claim(monkeypatch)

            await _run_adds(
                graph.update(
                    keys[0], document=_document(keys[0], "firstdoc alpha. " * 40)
                ),
                graph.update(
                    keys[1], document=_document(keys[1], "seconddoc beta. " * 40)
                ),
            )

            entities = await store.execute_read(
                "MATCH (e:Person {name: $name}) RETURN e.id AS id", {"name": name}
            )
            assert len(entities) == 1
            mentioning_documents = await store.execute_read(
                "MATCH (d:Document)-[:HAS_PART]->(:Chunk)-[:MENTIONED_IN]->"
                "(:Person {name: $name}) "
                "RETURN DISTINCT d.document_key AS key",
                {"name": name},
            )
            assert sorted(row["key"] for row in mentioning_documents) == keys
        finally:
            await _delete_run(store, keys=keys, name=name)

    @staticmethod
    @pytest.mark.parametrize(
        "error_policy", [ErrorPolicy.RAISE, ErrorPolicy.SKIP, ErrorPolicy.QUARANTINE]
    )
    async def test_same_new_name_fails_the_losing_add_when_owner_outlasts_window(
        monkeypatch: pytest.MonkeyPatch, error_policy: ErrorPolicy
    ) -> None:
        """The losing add raises under RAISE and reports its document otherwise.

        The document is not written, and the owner's entity is untouched.
        """
        store = build_test_store()
        await store.connect()
        suffix = uuid4().hex[:8]
        name = f"Concurrent Nebula {suffix}"
        keys = [f"concurrent://{suffix}-one", f"concurrent://{suffix}-two"]
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_SuffixEmbedder(suffix),
            extractor=_NameByKeywordExtractor({"firstdoc": name, "seconddoc": name}),
        )
        loser_finished = asyncio.Event()
        commit: Callable[..., Awaitable[int]] = _cutover._commit_pending_writes

        async def commit_after_loser_finished(**kwargs: Any) -> int:
            await asyncio.wait_for(loser_finished.wait(), timeout=120)
            return await commit(**kwargs)

        monkeypatch.setattr(
            _cutover, "_commit_pending_writes", commit_after_loser_finished
        )
        monkeypatch.setattr(_ingest, "_ALIAS_RETRY_WINDOW_SECONDS", 2)
        started = time.monotonic()
        adds = {
            asyncio.create_task(
                graph.add(
                    documents=[_document(key, f"{keyword} text. " * 40)],
                    error_policy=error_policy,
                )
            ): key
            for key, keyword in zip(keys, ["firstdoc", "seconddoc"], strict=True)
        }
        try:
            done, pending = await asyncio.wait(
                adds, timeout=120, return_when=asyncio.FIRST_COMPLETED
            )
            assert done, "neither add finished while the owner was held pending"
            assert time.monotonic() - started >= _ingest._ALIAS_RETRY_WINDOW_SECONDS, (
                "the losing add gave up before the retry window ran out"
            )
            loser = done.pop()
            loser_finished.set()
            winner = pending.pop()
            await asyncio.wait_for(winner, timeout=120)

            if error_policy is ErrorPolicy.RAISE:
                with pytest.raises(GraphStoreAliasConflictError):
                    loser.result()
            else:
                failures = loser.result().storage.failures
                assert [failure.item_id for failure in failures] == [adds[loser]]
                assert [failure.error_type for failure in failures] == [
                    GraphStoreAliasConflictError.__name__
                ]
            stored = await store.execute_read(
                "MATCH (d:Document) WHERE d.document_key IN $keys "
                "RETURN d.document_key AS key",
                {"keys": keys},
            )
            assert [row["key"] for row in stored] == [adds[winner]]
            entities = await store.execute_read(
                "MATCH (e:Person {name: $name}) RETURN e.id AS id", {"name": name}
            )
            assert len(entities) == 1
        finally:
            loser_finished.set()
            await asyncio.gather(*adds, return_exceptions=True)
            await _delete_run(store, keys=keys, name=name)

    @staticmethod
    async def test_loser_does_not_retry_over_a_document_that_changed_while_waiting(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A retry does not overwrite a version another writer committed meanwhile."""
        store = build_test_store()
        await store.connect()
        suffix = uuid4().hex[:8]
        name = f"Concurrent Pulsar {suffix}"
        owner_key = f"concurrent://{suffix}-one"
        loser_key = f"concurrent://{suffix}-two"
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_SuffixEmbedder(suffix),
            extractor=_NameByKeywordExtractor({"firstdoc": name, "seconddoc": name}),
        )
        conflict_seen = asyncio.Event()
        owner_may_commit = asyncio.Event()
        check_owner: Callable[..., Awaitable[bool]] = _ingest._any_job_pending

        async def note_conflict(*args: Any, **kwargs: Any) -> bool:
            conflict_seen.set()
            return await check_owner(*args, **kwargs)

        _hold_first_claimant_commit(monkeypatch, owner_may_commit)
        monkeypatch.setattr(_ingest, "_any_job_pending", note_conflict)
        third_text = "thirdwriter text. " * 40

        async def write_third_version() -> None:
            await asyncio.wait_for(conflict_seen.wait(), timeout=120)
            try:
                await graph.add(documents=[_document(loser_key, third_text)])
            finally:
                owner_may_commit.set()

        owner = graph.add(documents=[_document(owner_key, "firstdoc alpha. " * 40)])
        loser = graph.add(documents=[_document(loser_key, "seconddoc beta. " * 40)])
        try:
            outcomes = await asyncio.gather(
                owner, loser, write_third_version(), return_exceptions=True
            )
            assert isinstance(outcomes[1], GraphStoreAliasConflictError)
            stored = await store.execute_read(
                "MATCH (d:Document {document_key: $key}) "
                "RETURN d.current_content_hash AS hash",
                {"key": loser_key},
            )
            assert [row["hash"] for row in stored] == [
                _document(loser_key, third_text).content_hash
            ]
            entities = await store.execute_read(
                "MATCH (e:Person {name: $name}) RETURN e.id AS id", {"name": name}
            )
            assert len(entities) == 1
        finally:
            owner_may_commit.set()
            await _delete_run(store, keys=[owner_key, loser_key], name=name)

    @staticmethod
    async def test_expired_owner_does_not_block_a_conflicting_add(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A conflict whose owner lease has expired fails without the full window.

        The owner's worker stops renewing its lease and its commit stays held.
        Once the lease runs out the owner no longer counts as pending, so the
        losing add raises well before the retry window ends.
        """
        store = build_test_store()
        await store.connect()
        suffix = uuid4().hex[:8]
        name = f"Concurrent Comet {suffix}"
        owner_key = f"concurrent://{suffix}-one"
        loser_key = f"concurrent://{suffix}-two"
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_SuffixEmbedder(suffix),
            extractor=_NameByKeywordExtractor({"firstdoc": name, "seconddoc": name}),
            cutover_settings=CutoverJobSettings(lease_ttl_seconds=3),
        )
        release_owner = asyncio.Event()
        owner_claimed = _hold_first_claimant_commit(monkeypatch, release_owner)
        monkeypatch.setattr(_ingest, "_ALIAS_RETRY_WINDOW_SECONDS", 20)

        async def renewal_never_extends(**kwargs: Any) -> None:
            await kwargs["stop_event"].wait()
            kwargs["stopped_event"].set()

        monkeypatch.setattr(_cutover, "_renew_periodically", renewal_never_extends)
        owner = asyncio.ensure_future(
            graph.add(documents=[_document(owner_key, "firstdoc alpha. " * 40)])
        )
        try:
            await asyncio.wait_for(owner_claimed.wait(), timeout=120)
            started = time.monotonic()
            with pytest.raises(GraphStoreAliasConflictError):
                await graph.add(
                    documents=[_document(loser_key, "seconddoc beta. " * 40)]
                )
            assert time.monotonic() - started < 15
            stored = await store.execute_read(
                "MATCH (d:Document {document_key: $key}) RETURN d.document_key AS key",
                {"key": loser_key},
            )
            assert stored == []
        finally:
            release_owner.set()
            await asyncio.gather(owner, return_exceptions=True)
            await _delete_run(store, keys=[owner_key, loser_key], name=name)

    @staticmethod
    async def test_update_after_window_reports_the_document_under_skip(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An update that loses a name past the window reports it and keeps its hash.

        The document keeps the content it had before the update, and the failure
        names the document under SKIP.
        """
        store = build_test_store()
        await store.connect()
        suffix = uuid4().hex[:8]
        name = f"Concurrent Quasar {suffix}"
        doc_key = f"concurrent://{suffix}-one"
        owner_key = f"concurrent://{suffix}-two"
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_SuffixEmbedder(suffix),
            extractor=_NameByKeywordExtractor({"firstdoc": name, "seconddoc": name}),
        )
        release_owner = asyncio.Event()
        owner: asyncio.Future[Any] | None = None
        try:
            await graph.add(documents=[_document(doc_key, "plain words. " * 40)])
            before = await store.execute_read(
                "MATCH (d:Document {document_key: $key}) "
                "RETURN d.current_content_hash AS hash",
                {"key": doc_key},
            )
            owner_claimed = _hold_first_claimant_commit(monkeypatch, release_owner)
            monkeypatch.setattr(_ingest, "_ALIAS_RETRY_WINDOW_SECONDS", 2)
            owner = asyncio.ensure_future(
                graph.add(documents=[_document(owner_key, "firstdoc alpha. " * 40)])
            )
            await asyncio.wait_for(owner_claimed.wait(), timeout=120)

            result = await graph.update(
                doc_key, text="seconddoc beta. " * 40, error_policy=ErrorPolicy.SKIP
            )

            failures = result.add_result.storage.failures
            assert [failure.item_id for failure in failures] == [doc_key]
            assert [failure.error_type for failure in failures] == [
                GraphStoreAliasConflictError.__name__
            ]
            assert result.new_content_hash is None
            after = await store.execute_read(
                "MATCH (d:Document {document_key: $key}) "
                "RETURN d.current_content_hash AS hash",
                {"key": doc_key},
            )
            assert after == before
        finally:
            release_owner.set()
            if owner is not None:
                await asyncio.gather(owner, return_exceptions=True)
            await _delete_run(store, keys=[doc_key, owner_key], name=name)
