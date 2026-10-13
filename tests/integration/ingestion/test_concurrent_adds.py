"""Concurrent adds that name one entity differently, against a real Neo4j.

Runs against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml``. Each add resolves against committed data
only, so the test holds both commits back until both adds have resolved. The
pair only meets after the commits, when each job resolves what it created.
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
from agrag.graphdb import build_graph_store
from agrag.ingestion import _cutover
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _SuffixEmbedder(Embedder):
    """Gives this run's texts one vector and every other text an orthogonal one."""

    model = "suffix"

    def __init__(self, suffix: str) -> None:
        """Remember which suffix marks this run's own texts."""
        self._suffix = suffix

    async def dimensions(self) -> int:
        """Return the dimension of the shared instance's vector indexes."""
        return 4

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
        store = build_graph_store("neo4j")
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
