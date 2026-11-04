"""End-to-end entity-resolution flow against a real Neo4j instance.

Batch 2's mention joins batch 1's established cluster, then consolidate()
dry-runs and applies over seeded duplicates. Runs against the Docker
Compose Neo4j instance from ``docker/docker-compose.ci.yml``. Fuzzy
fast-path pairs only: the zero embedder keeps every non-fuzzy pair in
the discard zone so no LLM tier is involved.
"""

import hashlib
import importlib.util
import unicodedata
from collections.abc import Sequence
from types import ModuleType
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.embedding.base import Embedder
from agrag.graphdb.errors import GraphStoreFenceError
from agrag.ingestion import _ingest_pipeline, _merge_stage, resolved_entities
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.resolved_entities import ResolvedEntityWriteError
from agrag.loaders.types import ErrorPolicy
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration._backend import build_test_store


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _ZeroEmbedder(Embedder):
    """Zero-vector embedder: every embedding similarity discards.

    Dimension 4 matches the shared instance's existing vector indexes.
    Only the fuzzy fast path can merge, which is exactly what the
    consolidate test below exercises.
    """

    model = "zero"

    async def dimensions(self) -> int:
        """Return a small fixed dimension."""
        return FAKE_EMBEDDING_DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a zero vector for every text."""
        return [[0.0] * FAKE_EMBEDDING_DIMENSIONS for _ in texts]


class _SuffixEmbedder(Embedder):
    """Suffix-gated embedder isolating one run on a shared instance.

    Texts carrying this run's suffix share one basis vector; every
    other text shares the orthogonal one. Retrieval therefore ranks
    this run's own entities first, and the similarity tier only ever
    hard-merges within the run: foreign candidates always score 0.0
    and discard. Dimension 4 matches the existing vector indexes.
    """

    model = "suffix"

    def __init__(self, suffix: str) -> None:
        """Remember which suffix marks this run's own mentions."""
        self._suffix = suffix

    async def dimensions(self) -> int:
        """Return a small fixed dimension."""
        return FAKE_EMBEDDING_DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the run vector for own texts, the foreign one otherwise."""
        return [
            [1.0, 0.0, 0.0, 0.0] if self._suffix in text else [0.0, 1.0, 0.0, 0.0]
            for text in texts
        ]


class _ProbeExtractor(Extractor):
    """Extractor emitting configured Person mentions keyed by keyword."""

    def __init__(self, mentions_by_keyword: dict[str, list[str]]) -> None:
        """Remember which names each chunk keyword produces."""
        self._mentions_by_keyword = mentions_by_keyword

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Mention every configured name whose keyword is in the chunk."""
        lowered = chunk.text.lower()
        names = [
            name
            for keyword, keywords_names in self._mentions_by_keyword.items()
            if keyword in lowered
            for name in keywords_names
        ]
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    chunk_id=chunk.id,  # type: ignore[arg-type]
                    label="Person",
                    text=name,
                    char_start=0,
                    char_end=len(name),
                )
                for name in names
            ],
            relations=[],
            extractor_name="probe",
        )


def _document(key: str, text: str) -> Document:
    """Build a prose Document carrying an explicit stable key."""
    normalized = unicodedata.normalize("NFKC", text)
    return Document(
        text=normalized,
        title="e2e",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(normalized),
        line_count=normalized.count("\n") + 1,
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestEntityResolutionEndToEnd:
    """Two-batch join plus consolidate dry-run/apply on a real database."""

    async def test_second_batch_joins_established_cluster(self) -> None:
        """Batch 2's fuzzy variant extends batch 1's cluster to 3 members.

        ``first``/``second`` clear the fuzzy fast path (0.9744); ``third``
        clears it against ``first`` (0.9744) but not ``second`` (0.95), so
        the zone rules give exactly three edges: two ``fuzzy_fast_path``
        and one ``embedding`` (the suffix embedder scores own-run pairs
        1.0). No pair involving a foreign entity may gain an edge.
        """
        store = build_test_store()
        await store.connect()
        suffix = uuid4().hex[:8]
        first, second, third = (
            f"E2e Quasar {suffix}",
            f"E2e Quasars {suffix}",
            f"E2e Quasarr {suffix}",
        )
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_SuffixEmbedder(suffix),
            extractor=_ProbeExtractor(
                {"batchone": [first, second], "batchtwo": [third]}
            ),
        )
        first_key, second_key = f"e2e://{suffix}-one", f"e2e://{suffix}-two"
        try:
            await graph.add(documents=[_document(first_key, "batchone alpha. " * 60)])
            rows = await store.execute_read(
                "MATCH (a:Person)-[match:MATCHES]->(b:Person) "
                "WHERE a.name IN $names AND b.name IN $names "
                "RETURN a.name AS a, b.name AS b",
                {"names": [first, second, third]},
            )
            assert {frozenset((row["a"], row["b"])) for row in rows} == {
                frozenset((first, second))
            }
            await graph.add(documents=[_document(second_key, "batchtwo beta. " * 60)])
            rows = await store.execute_read(
                "MATCH (e:Person) WHERE e.name IN $names "
                "RETURN e.id AS id, e.name AS name",
                {"names": [first, second, third]},
            )
            assert {row["name"] for row in rows} == {first, second, third}
            rows = await store.execute_read(
                "MATCH (a:Person)-[match:MATCHES]->(b:Person) "
                "WHERE a.name IN $names AND b.name IN $names "
                "RETURN a.name AS a, b.name AS b, "
                "match.comparator AS comparator, match.active AS active",
                {"names": [first, second, third]},
            )
            pairs = {frozenset((row["a"], row["b"])): row for row in rows}
            assert set(pairs) == {
                frozenset((first, second)),
                frozenset((first, third)),
                frozenset((second, third)),
            }
            assert pairs[frozenset((first, second))]["comparator"] == "fuzzy_fast_path"
            assert pairs[frozenset((first, third))]["comparator"] == "fuzzy_fast_path"
            assert pairs[frozenset((second, third))]["comparator"] == "embedding"
            assert all(row["active"] is True for row in pairs.values())
            rows = await store.execute_read(
                "MATCH (resolved:ResolvedEntity) "
                "WHERE ALL(member_id IN resolved.member_ids "
                "WHERE member_id IN $ids) "
                "AND size(resolved.member_ids) = 3 "
                "RETURN resolved.member_ids AS members",
                {
                    "ids": [
                        row["id"]
                        for row in await store.execute_read(
                            "MATCH (e:Person) WHERE e.name IN $names RETURN e.id AS id",
                            {"names": [first, second, third]},
                        )
                    ]
                },
            )
            assert len(rows) == 1
        finally:
            id_rows = await store.execute_read(
                "MATCH (e:Person) WHERE e.name IN $names RETURN e.id AS id",
                {"names": [first, second, third]},
            )
            await store.execute_write(
                "MATCH (d:Document) WHERE d.document_key IN $keys "
                "OPTIONAL MATCH (d)-[:HAS_PART]->(c:Chunk) "
                "DETACH DELETE d, c",
                {"keys": [first_key, second_key]},
            )
            await store.execute_write(
                "MATCH (e:Person) WHERE e.name IN $names DETACH DELETE e",
                {"names": [first, second, third]},
            )
            await store.execute_write(
                "MATCH (node:ResolvedEntity) "
                "WHERE any(member_id IN node.member_ids "
                "WHERE member_id IN $ids) DETACH DELETE node",
                {"ids": [str(row["id"]) for row in id_rows] or ["none"]},
            )
            await store.execute_write(
                "MATCH (a:_MergeAlias) WHERE a.merge_key IN $merge_keys "
                "DETACH DELETE a",
                {
                    "merge_keys": [
                        f"Person:{name.strip().casefold()}"
                        for name in (first, second, third)
                    ]
                },
            )
            await store.close()

    @pytest.mark.parametrize(
        ("module", "stage"),
        [
            (_ingest_pipeline, "write_nodes_stage"),
            (_ingest_pipeline, "write_relations_stage"),
            (_merge_stage, "apply_merge"),
            (_merge_stage, "write_matches_and_rebuild"),
            (_merge_stage, "embed_resolved_entities"),
            (_ingest_pipeline, "_embed_and_upsert_chunks"),
            (_ingest_pipeline, "_embed_and_upsert_survivors"),
        ],
    )
    async def test_skip_fails_the_document_when_its_job_loses_the_lease(
        self, monkeypatch: pytest.MonkeyPatch, module: ModuleType, stage: str
    ) -> None:
        """A write after recovery claimed the job fails the document under SKIP.

        Recovery claims the job just before one pending stage writes. That
        stage's fenced write must raise out of ``Graph.add`` instead of being
        recorded as a stage failure, because the job can no longer commit.
        """
        store = build_test_store()
        await store.connect()
        suffix = uuid4().hex[:8]
        first, second = f"E2e Quasar {suffix}", f"E2e Quasars {suffix}"
        names = [first, second]
        key = f"e2e://{suffix}-claimed"
        original = getattr(module, stage)
        claimed: list[bool] = []

        async def claim_then_run(*args: object, **kwargs: object) -> object:
            if not claimed:
                claimed.append(True)
                await store.execute_write(
                    "MATCH (job:CutoverJob {document_key: $key}) "
                    "SET job.status = 'rolling_back'",
                    {"key": key},
                )
            return await original(*args, **kwargs)

        monkeypatch.setattr(module, stage, claim_then_run)
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_SuffixEmbedder(suffix),
            extractor=_ProbeExtractor({"batchone": names}),
        )
        try:
            with pytest.raises(GraphStoreFenceError):
                await graph.add(
                    documents=[_document(key, "batchone alpha. " * 60)],
                    error_policy=ErrorPolicy.SKIP,
                )

            jobs = await store.execute_read(
                "MATCH (job:CutoverJob {document_key: $key}) RETURN job.status AS s",
                {"key": key},
            )
            assert claimed == [True]
            assert jobs == [{"s": "rolling_back"}]
        finally:
            job_rows = await store.execute_read(
                "MATCH (job:CutoverJob {document_key: $key}) RETURN job.id AS id",
                {"key": key},
            )
            for row in job_rows:
                await store.execute_write(
                    "MATCH ()-[r]->() WHERE r._pending_job_id = $id DELETE r",
                    {"id": row["id"]},
                )
                await store.execute_write(
                    "MATCH (n) WHERE n._pending_job_id = $id DETACH DELETE n",
                    {"id": row["id"]},
                )
            await store.execute_write(
                "MATCH (job:CutoverJob {document_key: $key}) DETACH DELETE job",
                {"key": key},
            )
            await store.execute_write(
                "MATCH (e:Person) WHERE e.name IN $names DETACH DELETE e",
                {"names": names},
            )
            await store.close()

    async def test_skip_fails_the_document_when_its_resolved_entity_is_not_written(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A resolved entity that cannot be written fails the document under SKIP.

        The job writes its match edges, then the resolved entity in a second
        transaction. When that second write fails, committing the job would
        publish matches with no resolved entity, so the document is rolled
        back instead of being skipped past.
        """
        store = build_test_store()
        await store.connect()
        suffix = uuid4().hex[:8]
        first, second = f"E2e Quasar {suffix}", f"E2e Quasars {suffix}"
        names = [first, second]
        key = f"e2e://{suffix}-unwritten"

        async def fail_write(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("injected resolved entity write failure")

        monkeypatch.setattr(resolved_entities, "_write_resolved_entity", fail_write)
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_SuffixEmbedder(suffix),
            extractor=_ProbeExtractor({"batchone": names}),
        )
        try:
            with pytest.raises(ResolvedEntityWriteError):
                await graph.add(
                    documents=[_document(key, "batchone alpha. " * 60)],
                    error_policy=ErrorPolicy.SKIP,
                )

            persons = await store.execute_read(
                "MATCH (e:Person) WHERE e.name IN $names RETURN e.id AS id",
                {"names": names},
            )
            matches = await store.execute_read(
                "MATCH (a:Person)-[:MATCHES]->(b:Person) "
                "WHERE a.name IN $names AND b.name IN $names RETURN a.name AS a",
                {"names": names},
            )
            documents = await store.execute_read(
                "MATCH (d:Document {document_key: $key}) RETURN d.id AS id",
                {"key": key},
            )
            jobs = await store.execute_read(
                "MATCH (job:CutoverJob {document_key: $key}) RETURN job.status AS s",
                {"key": key},
            )
            assert persons == []
            assert matches == []
            assert documents == []
            assert jobs == []
        finally:
            await store.execute_write(
                "MATCH (d:Document {document_key: $key}) "
                "OPTIONAL MATCH (d)-[:HAS_PART]->(c:Chunk) DETACH DELETE d, c",
                {"key": key},
            )
            await store.execute_write(
                "MATCH (e:Person) WHERE e.name IN $names DETACH DELETE e",
                {"names": names},
            )
            await store.execute_write(
                "MATCH (a:_MergeAlias) WHERE a.merge_key IN $merge_keys "
                "DETACH DELETE a",
                {"merge_keys": [f"Person:{name.strip().casefold()}" for name in names]},
            )
            await store.execute_write(
                "MATCH (job:CutoverJob {document_key: $key}) DETACH DELETE job",
                {"key": key},
            )
            await store.close()

    async def test_consolidate_dry_run_then_apply(self) -> None:
        """Dry-run reports the seeded duplicate pair with zero writes."""
        store = build_test_store()
        await store.connect()
        suffix = uuid4().hex[:8]
        first_name, second_name = (
            f"E2e Consolidate {suffix}",
            f"E2e Consolidates {suffix}",
        )
        first = Entity(
            id=uuid4(), label="Person", name=first_name, embedding=[1.0, 0.0, 0.0, 0.0]
        )
        second = Entity(
            id=uuid4(),
            label="Person",
            name=second_name,
            embedding=[1.0, 0.0, 0.0, 0.0],
        )
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_SuffixEmbedder(suffix),
            extractor=_ProbeExtractor({}),
        )
        try:
            await store.upsert_nodes(
                "Person", [first.to_node_record(), second.to_node_record()]
            )
            dry = await graph.consolidate()
            assert any(
                {m.entity_a_id, m.entity_b_id} == {first.id, second.id}
                for m in dry.would_match
            )
            rows = await store.execute_read(
                "MATCH (a:Person)-[match:MATCHES]->(b:Person) "
                "WHERE a.id IN $ids AND b.id IN $ids "
                "RETURN count(match) AS n",
                {"ids": [str(first.id), str(second.id)]},
            )
            assert rows == [{"n": 0}]

            applied = await graph.consolidate(apply=True)
            assert applied.applied is True
            rows = await store.execute_read(
                "MATCH (a:Person)-[match:MATCHES]->(b:Person) "
                "WHERE a.id IN $ids AND b.id IN $ids "
                "MATCH (a)-[:RESOLVED_AS]->(resolved:ResolvedEntity) "
                "MATCH (b)-[:RESOLVED_AS]->(resolved) "
                "RETURN resolved.id AS resolved_id",
                {"ids": [str(first.id), str(second.id)]},
            )
            assert len(rows) == 1
        finally:
            await store.execute_write(
                "MATCH (e:Person) WHERE e.id IN $ids DETACH DELETE e",
                {"ids": [str(first.id), str(second.id)]},
            )
            await store.execute_write(
                "MATCH (node:ResolvedEntity) "
                "WHERE any(member_id IN node.member_ids WHERE member_id IN $ids) "
                "DETACH DELETE node",
                {"ids": [str(first.id), str(second.id)]},
            )
            await store.close()
