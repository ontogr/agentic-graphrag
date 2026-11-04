"""Concurrent adds that name one entity, against a real graph store.

Runs against the Docker Compose instance from ``docker/docker-compose.ci.yml``.
Each add resolves against committed data only, so the tests hold the commits
back until both adds have reached the point where they meet. Name variants
meet after the commits, when each job resolves what it created. One exact name
meets earlier, when both jobs claim it while pending.
"""

import asyncio
import hashlib
import importlib.util
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
from agrag.ingestion import _cutover, _merge_stage
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
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
            await asyncio.gather(
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
        monkeypatch.setattr(
            _cutover, "_commit_pending_writes", commit_after_both_claimed
        )
        try:
            await asyncio.gather(
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
                "MATCH (a:_MergeAlias {merge_key: $merge_key}) DETACH DELETE a",
                {"merge_key": f"Person:{name.casefold()}"},
            )
            await store.close()
