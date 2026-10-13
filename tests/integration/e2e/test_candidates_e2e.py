"""Exercise candidate writes and replacement through the public Graph API.

The test uses a real Neo4j store and records stable candidate states after
each document mutation in a repeatable JSON artifact.
"""

import hashlib
import importlib.util
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest

from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_record import UpsertFailure, UpsertResult
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    RelationType,
)
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.settings import ExtractionSettings
from agrag.loaders.types import ErrorPolicy
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.e2e._artifact import write_artifact


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _ConstantEmbedder(Embedder):
    """Return one stable four-dimensional vector for every text."""

    model = "candidate-e2e"

    async def dimensions(self) -> int:
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


class _CandidateExtractor(Extractor):
    """Return two mentions and a relation rejected by the schema pattern."""

    def __init__(self, person: str, organization: str, relation: str) -> None:
        self._person = person
        self._organization = organization
        self._relation = relation
        self.fail = False
        self.emit_candidate = True
        self.repeated = False

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        if self.fail:
            raise RuntimeError("extractor unavailable")
        if "Alice" not in chunk.text or "Acme" not in chunk.text:
            return ExtractionResult(entities=[], relations=[], extractor_name="e2e")
        alice = chunk.text.index("Alice")
        acme = chunk.text.index("Acme")
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label=self._person,
                    text="Alice",
                    char_start=alice,
                    char_end=alice + 5,
                ),
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label=self._organization,
                    text="Acme",
                    char_start=acme,
                    char_end=acme + 4,
                ),
            ],
            relations=[],
            candidates=(
                [
                    CandidateRecord(
                        kind="relation",
                        label=self._relation,
                        reason="off_pattern",
                        source_text="Alice",
                        target_text="Acme",
                        confidence=0.7,
                        chunk_id=chunk.id,
                    )
                    for _ in range(2 if self.repeated else 1)
                ]
                if self.emit_candidate
                else []
            ),
            extractor_name="e2e",
        )


def _document(key: str, text: str) -> Document:
    """Build a prose document with an explicit key."""
    return Document(
        text=text,
        title="candidate lifecycle",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        loader_name="e2e",
        encoding="utf-8",
        char_count=len(text),
        line_count=1,
    )


@dataclass
class _Env:
    """Resources and unique labels for one isolated candidate test run."""

    run: str
    store: GraphStore
    graph: Graph
    schema: GraphSchema
    extractor: _CandidateExtractor
    person: str
    organization: str
    relation: str

    def key(self) -> str:
        return f"candidates://{self.run}/doc"

    def text(self, body: str) -> str:
        return f"{body} Reference {self.run}."

    async def rows(self) -> list[dict[str, Any]]:
        return await self.store.execute_read(
            "MATCH (c:Candidate {label: $label}) "
            "OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(chunk) "
            "OPTIONAL MATCH (c)-[:SOURCE]->(source) "
            "OPTIONAL MATCH (c)-[:TARGET]->(target) "
            "RETURN c.state AS state, c.count AS count, c.reason AS reason, "
            "chunk.text AS chunk_text, source.name AS source, "
            "target.name AS target ORDER BY c.state, chunk_text",
            {"label": self.relation},
        )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestCandidatesE2E:
    """Check candidate capture, update replacement, review and deletion."""

    @pytest.fixture
    async def env(self) -> AsyncGenerator[_Env, None]:
        """Open isolated graph resources and remove this run's data afterward."""
        run = uuid4().hex[:8]
        person = validate_identifier(f"Person_{run}")
        organization = validate_identifier(f"Organization_{run}")
        relation = validate_identifier(f"WORKS_AT_{run}")
        schema = GraphSchema(
            name="candidate-e2e",
            version="1",
            entities=[
                EntityType(label=person, description="A named person."),
                EntityType(label=organization, description="An organization."),
            ],
            relations=[
                RelationType(
                    label=relation,
                    description="A person works at an organization.",
                    patterns=[(organization, person)],
                )
            ],
        )
        store = build_graph_store("neo4j")
        extractor = _CandidateExtractor(person, organization, relation)
        graph = await Graph.open(
            schema=schema,
            graph_store=store,
            embedder=_ConstantEmbedder(),
            extractor=extractor,
            extraction_settings=ExtractionSettings(candidates_enabled=True),
        )
        env = _Env(run, store, graph, schema, extractor, person, organization, relation)
        try:
            yield env
        finally:
            try:
                await store.execute_write(
                    "MATCH (c:Candidate {label: $label}) DETACH DELETE c",
                    {"label": relation},
                )
                await store.execute_write(
                    "MATCH (n) WHERE $person IN labels(n) OR $org IN labels(n) "
                    "DETACH DELETE n",
                    {"person": person, "org": organization},
                )
                await store.execute_write(
                    "MATCH (c:Chunk) WHERE c.text CONTAINS $run DETACH DELETE c",
                    {"run": run},
                )
                await store.execute_write(
                    "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix "
                    "DETACH DELETE d",
                    {"prefix": f"candidates://{run}/"},
                )
                await store.execute_write(
                    "MATCH (j:CutoverJob) WHERE j.document_key STARTS WITH $prefix "
                    "DETACH DELETE j",
                    {"prefix": f"candidates://{run}/"},
                )
                await store.execute_write(
                    "MATCH (a:_MergeAlias) WHERE a.merge_key STARTS WITH $prefix "
                    "DETACH DELETE a",
                    {"prefix": f"{person}:"},
                )
                await drop_schema_for(store, person, organization, relation)
            finally:
                await store.close()

    async def test_candidate_lifecycle(self, env: _Env) -> None:
        """Replace pending candidates without reviving reviewed candidates."""
        artifact: dict[str, Any] = {}
        original = env.text("Alice works at Acme.")
        added = await env.graph.add(
            documents=[_document(env.key(), original)],
        )
        rows = await env.rows()
        assert added.extraction.candidates_written == 1
        assert [(row["state"], row["source"], row["target"]) for row in rows] == [
            ("pending", "Alice", "Acme")
        ]
        artifact["added"] = {
            "dropped": [
                {"kind": item.kind, "reason": item.reason, "count": item.count}
                for item in added.extraction.dropped
            ],
            "written": added.extraction.candidates_written,
            "rows": [
                {
                    "state": row["state"],
                    "source": row["source"],
                    "target": row["target"],
                }
                for row in rows
            ],
        }

        changed = env.text("Alice joined Acme in 2020.")
        updated = await env.graph.update(env.key(), text=changed)
        rows = await env.rows()
        assert updated.add_result is not None
        assert updated.add_result.extraction.candidates_written == 1
        assert len(rows) == 1 and "joined" in rows[0]["chunk_text"]
        artifact["updated"] = {
            "written": updated.add_result.extraction.candidates_written
        }

        env.graph.extraction_settings.entity_threshold = 0.6
        refreshed = await env.graph.update(env.key(), text=changed)
        assert refreshed.add_result is not None
        assert refreshed.add_result.extraction.candidates_written == 1
        assert await env.rows() == rows
        artifact["in_place_refresh"] = {"candidates": 1}

        env.extractor.fail = True
        with pytest.raises(RuntimeError, match="extractor unavailable"):
            await env.graph.update(env.key(), text=env.text("Alice left Acme."))
        env.extractor.fail = False
        assert await env.rows() == rows
        artifact["failed_update_preserved"] = True

        await env.store.execute_write(
            "MATCH (c:Candidate {label: $label}) SET c.state = 'rejected'",
            {"label": env.relation},
        )
        reviewed = await env.graph.update(env.key(), text=env.text("Alice left Acme."))
        assert reviewed.add_result is not None
        assert reviewed.add_result.extraction.candidates_skipped == 1
        rows = await env.rows()
        assert [row["state"] for row in rows] == ["rejected"]
        await env.graph.delete_document(env.key())
        assert [row["state"] for row in await env.rows()] == ["rejected"]
        artifact["reviewed_and_deleted"] = {"states": ["rejected"]}
        assert write_artifact("candidates_lifecycle", artifact) == artifact

    @pytest.mark.parametrize(
        "failure_mode", ["lookup_exception", "exception", "returned_failure"]
    )
    async def test_update_candidate_storage_failure_rolls_back_under_skip(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch, failure_mode: str
    ) -> None:
        """Keep committed candidates when a candidate write fails during update."""
        original = env.text("Alice works at Acme.")
        await env.graph.add(documents=[_document(env.key(), original)])
        before = await env.rows()

        async def fail_candidate_write(*_args: Any, **_kwargs: Any) -> UpsertResult:
            if failure_mode in {"lookup_exception", "exception"}:
                raise RuntimeError("candidate storage unavailable")
            return UpsertResult(
                failures=[
                    UpsertFailure(
                        id="candidate",
                        error_type="StorageError",
                        error_message="candidate storage unavailable",
                    )
                ]
            )

        monkeypatch.setattr(
            env.store,
            "blocked_candidate_keys"
            if failure_mode == "lookup_exception"
            else "upsert_candidates",
            fail_candidate_write,
        )
        with pytest.raises(RuntimeError):
            await env.graph.update(
                env.key(),
                text=env.text("Alice joined Acme."),
                error_policy=ErrorPolicy.SKIP,
            )

        after = await env.rows()
        assert after == before
        assert "works" in after[0]["chunk_text"]
        artifact = {
            "failure_mode": failure_mode,
            "candidate_states": [row["state"] for row in after],
            "previous_evidence_preserved": "works" in after[0]["chunk_text"],
        }
        assert write_artifact("candidates_update_storage_failure", artifact) == artifact

    async def test_review_between_candidate_lookups_prevents_pending_twin(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Do not publish a pending twin when review wins the write race."""
        await env.graph.add(
            documents=[_document(env.key(), env.text("Alice works at Acme."))]
        )
        original_lookup = env.store.blocked_candidate_keys
        lookup_count = 0

        async def reject_after_early_lookup(keys: Sequence[str]) -> set[str]:
            nonlocal lookup_count
            blocked = await original_lookup(keys)
            lookup_count += 1
            if lookup_count == 2:
                await env.store.execute_write(
                    "MATCH (c:Candidate {label: $label}) SET c.state = 'rejected'",
                    {"label": env.relation},
                )
            return blocked

        monkeypatch.setattr(
            env.store, "blocked_candidate_keys", reject_after_early_lookup
        )
        await env.graph.update(env.key(), text=env.text("Alice joined Acme."))

        rows = await env.rows()
        assert [row["state"] for row in rows] == ["rejected"]
        artifact = {
            "candidate_states": [row["state"] for row in rows],
            "pending_twin": any(row["state"] == "pending" for row in rows),
        }
        assert write_artifact("candidates_review_race", artifact) == artifact

    async def test_add_sums_stats_across_document_jobs(self, env: _Env) -> None:
        """Keep per-document writes and sum the discarded occurrences."""
        docs = [
            _document(f"candidates://{env.run}/one", env.text("Alice works at Acme.")),
            _document(f"candidates://{env.run}/two", env.text("Alice joined Acme.")),
        ]

        result = await env.graph.add(documents=docs)

        assert result.extraction.candidates_written == 2
        assert [(item.reason, item.count) for item in result.extraction.dropped] == [
            ("off_pattern", 2)
        ]
        assert len(await env.rows()) == 2
        artifact = {
            "candidate_count": len(await env.rows()),
            "dropped_count": result.extraction.dropped[0].count,
            "written": result.extraction.candidates_written,
        }
        assert write_artifact("candidates_document_jobs", artifact) == artifact

    async def test_delete_removes_pending_candidates(self, env: _Env) -> None:
        """Delete the document's pending candidates in its cutover job."""
        key = f"candidates://{env.run}/pending-delete"
        await env.graph.add(
            documents=[_document(key, env.text("Alice works at Acme."))]
        )
        assert len(await env.rows()) == 1

        deleted = await env.graph.delete_document(key)

        assert deleted.no_op is False
        assert await env.rows() == []
        artifact = {"candidates_after_delete": 0, "deleted": not deleted.no_op}
        assert write_artifact("candidates_delete_pending", artifact) == artifact

    async def test_repeated_candidates_aggregate_and_empty_refresh_removes_them(
        self, env: _Env
    ) -> None:
        """Count repeated sightings once per key and replace them with no output."""
        env.extractor.repeated = True
        text = env.text("Alice works at Acme.")
        added = await env.graph.add(documents=[_document(env.key(), text)])
        assert added.extraction.candidates_written == 1
        assert [(item.reason, item.count) for item in added.extraction.dropped] == [
            ("off_pattern", 2)
        ]
        assert [row["count"] for row in await env.rows()] == [2]

        env.graph.extraction_settings.candidates_enabled = False
        updated = await env.graph.update(env.key(), text=text)
        assert updated.add_result is not None
        assert updated.add_result.extraction.candidates_written == 0
        assert updated.add_result.extraction.dropped[0].count == 2
        assert await env.rows() == []
        assert write_artifact(
            "candidates_empty_refresh",
            {"sightings": 2, "written": 1, "after_disabled_refresh": 0},
        ) == {"sightings": 2, "written": 1, "after_disabled_refresh": 0}

    async def test_switch_off_counts_but_writes_nothing(self, env: _Env) -> None:
        """Report discarded relations even when candidate writes are disabled."""
        graph = Graph(
            schema=env.schema,
            graph_store=env.store,
            embedder=_ConstantEmbedder(),
            extractor=env.extractor,
            extraction_settings=ExtractionSettings(candidates_enabled=False),
        )
        result = await graph.add(
            documents=[_document(env.key(), env.text("Alice works at Acme."))]
        )
        assert result.extraction.candidates_written == 0
        assert [item.reason for item in result.extraction.dropped] == ["off_pattern"]
        assert await env.rows() == []
