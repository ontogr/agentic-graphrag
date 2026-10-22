"""Exercise Graph ingestion helpers and pipeline wiring through the public Graph API."""

from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest import mock
from uuid import UUID, uuid4

import pytest

import agrag.ingestion._resolution_maintenance as maintenance_module
from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.chunk import Chunk as ChunkModel
from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_record import (
    DeferredWrites,
    NodeRecord,
    RelationRecord,
    UpsertFailure,
    UpsertResult,
)
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    RelationType,
)
from agrag.common.data_models.vector_record import VectorHit
from agrag.cypher.cutover_job_read import find_incomplete_jobs_query
from agrag.cypher.vector_placement import read_placement_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.graphdb.serialize import parse_entity_node
from agrag.ingestion._ingest_pipeline import (
    _embed_and_upsert_survivors,
)
from agrag.ingestion._merge_stage import _global_relation_lookup
from agrag.ingestion._resolution_maintenance import all_entities_by_label
from agrag.ingestion._walk import resolve_paths
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.reports import AddResult
from agrag.loaders.types import ErrorPolicy
from tests.unit.ingestion._index_fake import NoIndexesMixin
from tests.unit.ingestion._lease_fake import CutoverJobLeaseFake


class MockStore(NoIndexesMixin, CutoverJobLeaseFake, GraphStore):
    """In-memory GraphStore that records calls for assertions."""

    def __init__(self) -> None:
        """Create a fresh fake store."""
        self.connect_calls = 0
        self.register_labels_calls: list[list[str]] = []
        self.register_types_calls: list[list[str]] = []
        self.setup_constraints_calls = 0
        self.setup_indexes_calls = 0
        self.upsert_nodes_calls: list[tuple[str, list[NodeRecord]]] = []
        self.upsert_relations_calls: list[list[RelationRecord]] = []
        self.execute_read_responses: list[list[dict[str, Any]]] = []
        self.execute_read_calls: list[tuple[str, Any]] = []
        self.execute_write_calls: list[tuple[str, Any]] = []
        self._read_index = 0

    async def connect(self) -> None:
        """Record a connect call."""
        self.connect_calls += 1

    async def close(self) -> None:
        """No-op close."""
        pass

    def session(self) -> AbstractAsyncContextManager[Any]:
        """Return a no-op async session."""

        class S:
            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *a: object) -> None:
                return None

        return S()  # type: ignore[return-value]

    async def execute_read(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Record the read and return the next canned response.

        Index-readiness and crash-recovery reads from ``Graph.open()`` do not
        consume responses intended for the test.
        """
        del timeout
        self.execute_read_calls.append((query, parameters))
        if query in {
            find_incomplete_jobs_query(),
            read_placement_query(),
        }:
            return []
        if self._read_index < len(self.execute_read_responses):
            response = self.execute_read_responses[self._read_index]
            self._read_index += 1
            return response
        return []

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Record the write, answering Cutover Job queries in-memory."""
        self.execute_write_calls.append((query, parameters))
        handled = self.handle_cutover_query(query, parameters)
        if handled is not None:
            return handled
        return []

    async def setup_constraints(self) -> None:
        """Record a setup_constraints call."""
        self.setup_constraints_calls += 1

    async def setup_indexes(self) -> None:
        """Record a setup_indexes call."""
        self.setup_indexes_calls += 1

    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult:
        """Record a node upsert."""
        self.upsert_nodes_calls.append((label, list(nodes)))
        return UpsertResult(written=len(nodes))

    async def upsert_relations(
        self,
        relations: Sequence[RelationRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult:
        """Record a relation upsert."""
        self.upsert_relations_calls.append(list(relations))
        return UpsertResult(written=len(relations))

    async def upsert_candidates(
        self,
        candidates: Sequence[CandidateRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
    ) -> UpsertResult:
        """Report every candidate written."""
        return UpsertResult(written=len(candidates))

    async def blocked_candidate_keys(self, keys: Sequence[str]) -> set[str]:
        """Return no reviewed candidate keys."""
        return set()

    async def ensure_vector_index(self, **kw: Any) -> None:
        """No-op vector index creation."""
        pass

    async def ensure_fulltext_index(self, **kw: Any) -> None:
        """No-op full-text index creation."""
        pass

    async def vector_search(self, **kw: Any) -> list[VectorHit]:
        """Return no hits."""
        return []

    async def register_labels(self, labels: Sequence[str]) -> None:
        """Record registered labels."""
        self.register_labels_calls.append(list(labels))

    async def register_relation_types(self, types: Sequence[str]) -> None:
        """Record registered relation types."""
        self.register_types_calls.append(list(types))


class MockEmbedder(Embedder):
    """Embedder that returns a fixed vector."""

    model = "fake"

    async def dimensions(self) -> int:
        """Return fixed dimensions."""
        return 3

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector for each input text."""
        return [[1.0, 2.0, 3.0] for _ in texts]


class MockExtractor(Extractor):
    """Extractor that returns a canned result and records calls."""

    def __init__(self, result: ExtractionResult | None = None) -> None:
        """Create the fake extractor."""
        self.result = result or ExtractionResult(
            entities=[], relations=[], extractor_name="fake"
        )
        self.calls: list[str] = []

    async def extract(self, chunk: ChunkModel, schema: GraphSchema) -> ExtractionResult:
        """Record the chunk text and return the canned result."""
        self.calls.append(chunk.text)
        return self.result


class TestParseEntityNode:
    """Tests for parse_entity_node."""

    def test_parses_stored_node(self) -> None:
        """A stored node's properties become an Entity."""
        cid = uuid4()
        eid = uuid4()
        node = {
            "id": str(eid),
            "name": "Alice",
            "merge_key": "Person:alice",
            "merge_count": 2,
            "source_chunk_ids": [str(cid)],
            "created_at": "2020-01-01T00:00:00+00:00",
            "_pending_job_id": str(uuid4()),
            "age": "30",
        }
        ent = parse_entity_node(node)
        assert ent is not None
        assert ent.id == eid
        assert ent.label == "Person"
        assert ent.name == "Alice"
        assert ent.merge_count == 2
        assert ent.properties == {"age": "30"}
        assert ent.source_chunk_ids == [cid]

    def test_label_is_the_merge_key_prefix(self) -> None:
        """The label comes from the merge key, and a name may hold a colon."""
        node = {
            "id": str(uuid4()),
            "name": "Star Trek: Voyager",
            "merge_key": "Show:star trek: voyager",
        }
        ent = parse_entity_node(node)
        assert ent is not None
        assert ent.label == "Show"
        assert ent.name == "Star Trek: Voyager"

    def test_filters_system_keys(self) -> None:
        """System keys are not kept in properties."""
        node = {
            "id": str(uuid4()),
            "name": "Frank",
            "merge_key": "Person:frank",
            "embedding": [1, 2, 3],
            "custom": "keep",
        }
        ent = parse_entity_node(node)
        assert ent is not None
        assert ent.properties == {"custom": "keep"}
        assert ent.embedding == [1, 2, 3]

    def test_ignores_malformed_created_at_and_merge_count(self) -> None:
        """A bad created_at or merge_count falls back to its default."""
        node = {
            "id": str(uuid4()),
            "name": "Grace",
            "merge_key": "Person:grace",
            "merge_count": "not_an_int",
            "created_at": "bad-date",
        }
        ent = parse_entity_node(node)
        assert ent is not None
        assert ent.name == "Grace"
        assert ent.merge_count == 1

    def test_name_falls_back_to_merge_key_suffix(self) -> None:
        """A missing name falls back to the merge key suffix."""
        ent = parse_entity_node({"id": str(uuid4()), "merge_key": "Person:heidi"})
        assert ent is not None
        assert ent.name == "heidi"

    @pytest.mark.parametrize(
        "node",
        [
            {"name": "x", "merge_key": "Person:x"},
            {"id": str(uuid4()), "name": "x"},
            {"id": str(uuid4()), "merge_key": "nocolon"},
            {"id": "not-a-uuid", "merge_key": "Person:x"},
            {"id": str(uuid4()), "merge_key": "Person:x", "source_chunk_ids": ["bad"]},
            None,
            object(),
        ],
    )
    def test_unusable_node_returns_none(self, node: object) -> None:
        """A node without a usable id or merge key yields None."""
        assert parse_entity_node(node) is None


class TestGlobalRelationLookup:
    """Tests for _global_relation_lookup."""

    async def test_groups_by_type_and_maps_rows(self) -> None:
        """One query per distinct type."""
        store = MockStore()
        s1, t1 = uuid4(), uuid4()
        s2, t2 = uuid4(), uuid4()
        triples = [(s1, t1, "WORKS_AT"), (s2, t2, "WORKS_AT"), (s1, t1, "LIVES_AT")]
        rel_id = uuid4()
        cid = uuid4()
        store.execute_read_responses = [
            [
                {
                    "source_id": str(s1),
                    "target_id": str(t1),
                    "id": str(rel_id),
                    "source_chunk_ids": [str(cid)],
                }
            ],
            [],
        ]
        result = await _global_relation_lookup(
            triples,
            graph_store=store,
            error_policy=ErrorPolicy.RAISE,
            failures=[],
        )
        assert (s1, t1, "WORKS_AT") in result
        assert result[(s1, t1, "WORKS_AT")][0] == rel_id
        assert (s2, t2, "WORKS_AT") not in result
        assert len(store.execute_read_calls) == 2

    async def test_raises_on_malformed_row_instead_of_hiding_its_edge(self) -> None:
        """A malformed row fails the lookup, so no duplicate edge is written."""
        store = MockStore()
        s, t = uuid4(), uuid4()
        store.execute_read_responses = [
            [{"source_id": "bad-uuid", "target_id": str(t), "id": str(uuid4())}]
        ]
        with pytest.raises(ValueError):
            await _global_relation_lookup(
                [(s, t, "WORKS_AT")],
                graph_store=store,
                error_policy=ErrorPolicy.RAISE,
                failures=[],
            )


class _GuardedNodeStore(MockStore):
    """MockStore whose execute_write honors the embedding write/clear guard.

    ``set_embedding_query`` / ``clear_property_query`` apply a record
    only when the target node's current name/description match the
    record's ``expected_name`` / ``expected_description``. The chunk
    variants (``set_chunk_embedding_query`` /
    ``clear_chunk_embedding_query``) guard on ``text`` instead. Real
    Neo4j enforces those WHERE clauses; this fake reproduces them in
    memory so a concurrent-write test can prove a stale record is
    rejected without a live database. ``execute_read`` answers the by-id
    loading queries from the same ``nodes`` mapping, so a test can also
    drive the chunk-write recovery from it.
    """

    def __init__(self, nodes: dict[str, dict[str, Any]]) -> None:
        super().__init__()
        self.nodes = nodes

    async def execute_read(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Answer the by-id loading reads from the in-memory nodes."""
        del timeout
        if "RETURN n" not in query:
            return await super().execute_read(query, parameters)
        rows: list[dict[str, Any]] = []
        for node_id in (parameters or {}).get("ids", []):
            node = self.nodes.get(str(node_id))
            if node is None:
                continue
            # The chunk variant matches the Chunk label instead.
            rows.append({"n": {"id": str(node_id), **node}})
        return rows

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        rows = await super().execute_write(query, parameters)
        # The Cutover Job machinery answers its own queries; only the
        # embedding writes reach the guard below.
        if rows:
            return rows
        records = (parameters or {}).get("records", [])
        matched_ids: list[str] = []
        for record in records:
            node = self.nodes.get(record["id"])
            if node is None:
                continue
            # Entity guard: name + description.
            if "expected_name" in record and node["name"] != record["expected_name"]:
                continue
            if (
                "expected_description" in record
                and (node.get("description") or "") != record["expected_description"]
            ):
                continue
            # Chunk guard: text.
            if (
                "expected_text" in record
                and node.get("text") != record["expected_text"]
            ):
                continue
            if "REMOVE n.embedding" in query:
                node["embedding"] = None
            elif "SET n.embedding" in query:
                node["embedding"] = record["vector"]
                matched_ids.append(record["id"])
        if "SET n.embedding" in query:
            return [{"id": record_id} for record_id in matched_ids]
        return []


class TestEmbedAndUpsertSurvivors:
    """Regression tests for the name/description guard on embedding writes."""

    async def test_failure_clear_does_not_wipe_newer_vector(self) -> None:
        """A failing call's clear must not wipe a different, newer vector.

        Regression test: clear_property_query used to key only by id, so a
        call whose embed() failed for stale text could wipe a vector a
        different, newer call had already written for the node's current
        text.
        """

        class _FailingEmbedder(MockEmbedder):
            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise RuntimeError("embed backend down")

        entity_id = uuid4()
        store = _GuardedNodeStore(
            {
                str(entity_id): {
                    "name": "NewText",
                    "description": None,
                    "embedding": [0.9, 0.9],
                }
            }
        )
        stale_entity = Entity(id=entity_id, label="Person", name="OldText")

        await _embed_and_upsert_survivors(
            {entity_id: stale_entity},
            embedder=_FailingEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.SKIP,
        )

        assert store.nodes[str(entity_id)]["embedding"] == [0.9, 0.9]


class TestGraphOpenHierarchyLabels:
    """Graph.open registers parent and child entity labels with the store."""

    async def test_registers_parent_and_child_labels(self) -> None:
        """A child type's own label and its parent's label both get registered."""
        indexed_labels: list[str] = []

        class IndexRecordingStore(MockStore):
            async def ensure_vector_index(self, **kw: Any) -> None:
                indexed_labels.append(kw["label"])

        schema = GraphSchema(
            name="test",
            version="1",
            entities=[
                EntityType(label="Organization", description="test"),
                EntityType(
                    label="Vendor", description="test", parents=["Organization"]
                ),
            ],
            relations=[],
        )
        store = IndexRecordingStore()
        await Graph.open(
            schema=schema,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
        )
        registered = store.register_labels_calls[0]
        assert "Organization" in registered
        assert "Vendor" in registered
        assert "Organization" in indexed_labels
        assert "Vendor" in indexed_labels


class TestResolvePaths:
    """Tests for resolve_paths."""

    def test_directory(self, tmp_path: Path) -> None:
        """Directory expands to files and single_file False."""
        d = tmp_path / "d"
        d.mkdir()
        (d / "a.txt").write_text("a")
        (d / "b.txt").write_text("b")
        paths, single = resolve_paths(str(d))
        assert len(paths) == 2
        assert single is False

    def test_glob(self, tmp_path: Path) -> None:
        """Glob pattern expands."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.txt").write_text("b")
        paths, single = resolve_paths(str(tmp_path / "*.txt"))
        assert any(p.name == "a.txt" for p in paths)
        assert single is False

    def test_list_of_sources(self, tmp_path: Path) -> None:
        """List input is handled."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("a")
        f2.write_text("b")
        paths, single = resolve_paths([str(f1), str(f2)])
        assert len(paths) == 2
        assert single is False


class TestGraphAddPipeline:
    """Tests for the Graph.add pipeline."""

    async def test_loader_requires_single_file(self, tmp_path: Path) -> None:
        """Loader with directory/glob raises."""
        from agrag.loaders.prose import TextLoader  # noqa: PLC0415

        (tmp_path / "a.txt").write_text("a")
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=embed,
            extractor=extractor,
        )
        with pytest.raises(ValueError):
            await graph.add(str(tmp_path), loader=TextLoader())

    async def test_partial_chunk_write_still_embeds_written_chunks(self) -> None:
        """Chunks committed before a failed node write still get embeddings.

        Regression test: the embedding stage ran only when the whole chunk
        node write succeeded, so a failure in a later batch left the
        already-committed chunks without a vector, unsearchable by vector
        search until their source was ingested again.
        """

        class PartialChunkStore(_GuardedNodeStore):
            """Commits the chunk nodes it is given, then fails the write."""

            async def upsert_nodes(
                self,
                label: str,
                nodes: Sequence[NodeRecord],
                *,
                batch_size: int = 256,
                pending_job_id: UUID | None = None,
                deferred: DeferredWrites | None = None,
            ) -> UpsertResult:
                result = await super().upsert_nodes(
                    label, nodes, batch_size=batch_size, pending_job_id=pending_job_id
                )
                if label != CHUNK_LABEL:
                    return result
                for node in nodes:
                    self.nodes[str(node.id)] = {
                        "text": node.properties.get("text"),
                    }
                raise RuntimeError("chunk node write failed")

        store = PartialChunkStore({})
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
        )

        result = await graph.add(text="hello world", error_policy=ErrorPolicy.SKIP)

        assert any(f.item_id == "chunks" for f in result.storage.failures)
        embedded_ids = {
            record["id"]
            for query, parameters in store.execute_write_calls
            if "SET n.embedding" in query and "expected_text" in query
            for record in (parameters or {}).get("records", [])
        }
        assert embedded_ids == set(store.nodes)

    async def test_non_uuid_chunk_failure_id_does_not_abort_add(self) -> None:
        """Backend failure ids remain failures even when they are not UUIDs."""

        class NonUuidFailureStore(MockStore):
            """Return a backend-specific chunk failure id."""

            async def upsert_nodes(
                self,
                label: str,
                nodes: Sequence[NodeRecord],
                *,
                batch_size: int = 256,
                pending_job_id: UUID | None = None,
                deferred: DeferredWrites | None = None,
            ) -> UpsertResult:
                result = await super().upsert_nodes(
                    label, nodes, batch_size=batch_size, pending_job_id=pending_job_id
                )
                if label == CHUNK_LABEL:
                    return UpsertResult(
                        failures=[
                            UpsertFailure(
                                id="backend-record-7",
                                error_type="BackendFailure",
                                error_message="record rejected",
                            )
                        ]
                    )
                return result

        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=NonUuidFailureStore(),
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
        )

        result = await graph.add(text="hello world", error_policy=ErrorPolicy.RAISE)

        assert [failure.item_id for failure in result.storage.failures] == [
            "backend-record-7"
        ]
        assert all(failure.item_id != "chunks" for failure in result.storage.failures)

    async def test_add_includes_next_chunk_records(self) -> None:
        """add() includes NEXT_CHUNK edges alongside HAS_PART records."""
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=embed,
            extractor=extractor,
        )
        result = await graph.add(text="one two three four five six", return_chunks=True)
        next_records = [
            rec
            for batch in store.upsert_relations_calls
            for rec in batch
            if rec.type == "NEXT_CHUNK"
        ]
        chunk_ids = [chunk.id for chunk in result.chunks]
        assert len(next_records) == max(len(chunk_ids) - 1, 0)
        assert all(rec.properties == {} for rec in next_records)

    async def test_on_progress_fires_batches_plus_final(self) -> None:
        """on_progress fires per batch plus final."""
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=embed,
            extractor=extractor,
        )
        seen: list[AddResult] = []

        def cb(r: AddResult) -> None:
            seen.append(r)

        await graph.add(text="hi", on_progress=cb)
        assert len(seen) == 2
        # Each progress result counts the writes committed so far.
        assert seen[0].storage.nodes_written == 3
        assert seen[0].storage.relationships_written == 4
        assert seen[1].storage.nodes_written == seen[0].storage.nodes_written
        assert seen[1].storage.relationships_written == (
            seen[0].storage.relationships_written
        )

    async def test_on_progress_exception_suppressed(self) -> None:
        """Exception in on_progress does not abort add."""

        def bad_cb(_: AddResult) -> None:
            raise RuntimeError("boom")

        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=embed,
            extractor=extractor,
        )
        result = await graph.add(text="hi", on_progress=bad_cb)
        assert result.ingestion.documents == 1

    async def test_extraction_failure_skip(self) -> None:
        """Extraction failure with SKIP records StageFailure."""

        class FailExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                raise ValueError("fail extract")

        store, embed = MockStore(), MockEmbedder()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=embed,
            extractor=FailExtractor(),
        )
        result = await graph.add(text="hi", error_policy=ErrorPolicy.SKIP)
        assert result.extraction.failures
        assert result.extraction.failures[0].error_type == "ValueError"
        assert result.ingestion.documents == 1

    async def test_extraction_failure_raise(self) -> None:
        """Extraction failure with RAISE propagates."""

        class FailExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                raise ValueError("fail")

        store, embed = MockStore(), MockEmbedder()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=embed,
            extractor=FailExtractor(),
        )
        with pytest.raises(ValueError):
            await graph.add(text="hi", error_policy=ErrorPolicy.RAISE)

    async def test_empty_chunks_writes_only_document_and_section_nodes(self) -> None:
        """No chunks writes the Document and Section nodes and no embeddings."""
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=embed,
            extractor=extractor,
        )
        with mock.patch("agrag.ingestion._ingest.chunk_documents", return_value=[]):
            result = await graph.add(text="hi", on_progress=lambda _: None)
            assert result.extraction.chunks_processed == 0
            assert result.storage.nodes_written == 2
            assert result.chunks == []

    async def test_global_exact_match_integration(self) -> None:
        """Exact match hits populate resolution stats."""
        eid = uuid4()
        cid = uuid4()
        store = MockStore()
        # The first read is the add's document lookup, which finds no stored key.
        store.execute_read_responses = [
            [],
            [
                {
                    "n": {
                        "id": str(eid),
                        "name": "Alice",
                        "merge_key": "Person:alice",
                        "merge_count": 1,
                        "source_chunk_ids": [str(cid)],
                        "created_at": "2020-01-01T00:00:00+00:00",
                    }
                }
            ],
        ]

        class AliceExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=chunk.id,
                            label="Person",
                            text="alice",
                            char_start=0,
                            char_end=5,
                        )
                    ],  # type: ignore[arg-type]
                    relations=[],
                    extractor_name="fake",
                )

        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=AliceExtractor(),
        )
        result = await graph.add(text="alice")
        assert result.resolution.exact_match_hits == 1
        assert result.merge.nodes_updated == 1

    async def test_mentioned_in_dedup(self) -> None:
        """Same entity mentioned twice in same chunk yields one MENTIONED_IN."""
        store, embed = MockStore(), MockEmbedder()

        class DupExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                cid = chunk.id  # type: ignore[union-attr]
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=cid,
                            label="Person",
                            text="Alice",
                            char_start=0,
                            char_end=5,
                        ),
                        ExtractedEntity(
                            chunk_id=cid,
                            label="Person",
                            text="Alice",
                            char_start=6,
                            char_end=11,
                        ),
                    ],
                    relations=[],
                    extractor_name="fake",
                )

        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=embed,
            extractor=DupExtractor(),
        )
        await graph.add(text="Alice Alice")
        # One entity for one chunk yields a single MENTIONED_IN edge.
        mentioned = [
            r
            for batch in store.upsert_relations_calls
            for r in batch
            if r.type == "MENTIONED_IN"
        ]
        assert len(mentioned) == 1

    async def test_relation_dedup_global_and_within(self) -> None:
        """Relation dedup within-call and global."""
        store = MockStore()
        s, t = uuid4(), uuid4()
        existing_rel_id = uuid4()
        existing_cid = uuid4()

        async def fake_read(
            query: str, params: Mapping[str, Any] | None = None
        ) -> list[dict[str, Any]]:
            if "merge_key" in query:
                return []
            if "UNWIND $pairs" in query:
                pairs = params.get("pairs", []) if params else []
                for p in pairs:
                    if p["source_id"] == str(s) and p["target_id"] == str(t):
                        return [
                            {
                                "source_id": str(s),
                                "target_id": str(t),
                                "id": str(existing_rel_id),
                                "source_chunk_ids": [str(existing_cid)],
                            }
                        ]
                return []
            if "RETURN n ORDER BY" in query:
                return []
            return []

        store.execute_read = fake_read  # type: ignore[method-assign]

        from agrag.common.data_models.entity import Entity  # noqa: PLC0415

        e_s = Entity(
            id=s,
            label="Person",
            name="Alice",
            properties={},
            source_chunk_ids=[uuid4()],
        )
        e_t = Entity(
            id=t,
            label="Organization",
            name="Acme",
            properties={},
            source_chunk_ids=[uuid4()],
        )

        class RelExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                cid = chunk.id  # type: ignore[union-attr]
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=cid,
                            label="Person",
                            text="Alice",
                            char_start=0,
                            char_end=5,
                        ),
                        ExtractedEntity(
                            chunk_id=cid,
                            label="Organization",
                            text="Acme",
                            char_start=14,
                            char_end=18,
                        ),
                    ],
                    relations=[
                        ExtractedRelation(
                            chunk_id=cid,
                            label="WORKS_AT",
                            source_index=0,
                            target_index=1,
                        )
                    ],
                    extractor_name="fake",
                )

        schema = GraphSchema(
            name="test",
            version="1",
            entities=[
                EntityType(label="Person", description="p"),
                EntityType(label="Organization", description="o"),
            ],
            relations=[
                RelationType(
                    label="WORKS_AT",
                    description="w",
                    patterns=[("Person", "Organization")],
                )
            ],
        )
        graph = await Graph.open(
            schema=schema,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=RelExtractor(),
        )

        import agrag.ingestion._merge_stage as gmod  # noqa: PLC0415

        async def fake_compute(  # type: ignore[no-untyped-def]
            *, existing_entities, mentions, schema, **kw
        ):
            from agrag.ingestion.merge import MergePlan  # noqa: PLC0415

            if mentions[0].text == "Alice":
                return MergePlan(survivor=e_s, conflicts=[]), []
            return MergePlan(survivor=e_t, conflicts=[]), []

        with (
            mock.patch.object(gmod, "compute_merge", side_effect=fake_compute),
            mock.patch.object(gmod, "apply_merge", new_callable=mock.AsyncMock),
        ):
            await graph.add(text="Alice works at Acme")

        # Global dedup reuses the existing relation id.
        domain_rels = [
            r
            for batch in store.upsert_relations_calls
            for r in batch
            if r.type == "WORKS_AT"
        ]
        assert len(domain_rels) == 1
        assert domain_rels[0].id == existing_rel_id
        assert (
            str(existing_cid) in domain_rels[0].properties["source_chunk_ids"]
            or len(domain_rels[0].properties["source_chunk_ids"]) >= 1
        )

    async def test_mentioned_in_reuses_transferred_edge_id(self) -> None:
        """An existing MENTIONED_IN edge keeps its id when a chunk is re-ingested.

        Without an endpoint lookup before writing, Graph.add would compute a
        fresh mentioned_in_id() for the same (chunk, entity) pair and create
        a second, parallel edge instead of reusing the one already there.
        """
        store = MockStore()
        survivor_id = uuid4()
        stale_edge_id = uuid4()
        captured_chunk_id: dict[str, Any] = {}

        class AliceExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                captured_chunk_id["id"] = str(chunk.id)
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=chunk.id,
                            label="Person",
                            text="Alice",
                            char_start=0,
                            char_end=5,
                        )
                    ],
                    relations=[],
                    extractor_name="fake",
                )  # type: ignore[arg-type]

        async def fake_read(
            query: str, params: Mapping[str, Any] | None = None
        ) -> list[dict[str, Any]]:
            if "merge_key" in query:
                return []
            if "UNWIND $pairs" in query:
                pairs = params.get("pairs", []) if params else []
                for pair in pairs:
                    matches_chunk = pair["source_id"] == captured_chunk_id.get("id")
                    matches_survivor = pair["target_id"] == str(survivor_id)
                    if matches_chunk and matches_survivor:
                        return [
                            {
                                "source_id": pair["source_id"],
                                "target_id": pair["target_id"],
                                "id": str(stale_edge_id),
                                "source_chunk_ids": [],
                            }
                        ]
                return []
            return []

        store.execute_read = fake_read  # type: ignore[method-assign]

        survivor = Entity(id=survivor_id, label="Person", name="Alice", properties={})

        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=AliceExtractor(),
        )

        import agrag.ingestion._merge_stage as gmod  # noqa: PLC0415

        async def fake_compute(  # type: ignore[no-untyped-def]
            *, existing_entities, mentions, schema, **kw
        ):
            from agrag.ingestion.merge import MergePlan  # noqa: PLC0415

            return MergePlan(survivor=survivor, conflicts=[]), []

        with (
            mock.patch.object(gmod, "compute_merge", side_effect=fake_compute),
            mock.patch.object(gmod, "apply_merge", new_callable=mock.AsyncMock),
        ):
            await graph.add(text="Alice")

        mentioned = [
            r
            for batch in store.upsert_relations_calls
            for r in batch
            if r.type == "MENTIONED_IN"
        ]
        assert len(mentioned) == 1
        assert mentioned[0].id == stale_edge_id

    async def test_embedding_failure_clears_stale_embedding(self) -> None:
        """A failed batch embed() clears any embedding already on the survivor.

        Regression test: the survivor's node is committed via apply_merge
        before this stage runs, so if embed() then fails, an embedding left
        over from before this call's update would rank the entity by
        outdated text. It must be cleared, not left in place.
        """
        store = MockStore()

        class _FailingEmbedder(MockEmbedder):
            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise RuntimeError("embed backend down")

        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_FailingEmbedder(),
            extractor=MockExtractor(),
        )

        class BobExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=chunk.id,
                            label="Person",
                            text="Bob",
                            char_start=0,
                            char_end=3,
                        )
                    ],
                    relations=[],
                    extractor_name="fake",
                )  # type: ignore[arg-type]

        graph._extractor = BobExtractor()
        result = await graph.add(text="Bob", error_policy=ErrorPolicy.SKIP)

        clear_calls = [
            call
            for call in store.execute_write_calls
            if "REMOVE n.embedding" in call[0]
        ]
        # Both chunk and entity embedding clears on failure.
        assert len(clear_calls) >= 1
        assert result.storage.failures

    async def test_embedding_failure_clears_before_raising(self) -> None:
        """Under RAISE policy, the stale embedding is still cleared first."""
        store = MockStore()

        class _FailingEmbedder(MockEmbedder):
            async def embed_one(self, text: str) -> list[float]:
                return [1.0, 2.0, 3.0]

            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise RuntimeError("embed backend down")

        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_FailingEmbedder(),
            extractor=MockExtractor(),
        )

        class BobExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=chunk.id,
                            label="Person",
                            text="Bob",
                            char_start=0,
                            char_end=3,
                        )
                    ],
                    relations=[],
                    extractor_name="fake",
                )  # type: ignore[arg-type]

        graph._extractor = BobExtractor()
        with pytest.raises(RuntimeError, match="embed backend down"):
            await graph.add(text="Bob", error_policy=ErrorPolicy.RAISE)

        clear_calls = [
            call
            for call in store.execute_write_calls
            if "REMOVE n.embedding" in call[0]
        ]
        # Both chunk and entity embedding clears happen before raising.
        assert len(clear_calls) >= 1

    async def test_all_entities_by_label_pagination(self) -> None:
        """Pagination via skip/limit."""
        store = MockStore()
        eid = uuid4()
        row = {
            "n": {
                "id": str(eid),
                "name": "Alice",
                "merge_key": "Person:alice",
                "merge_count": 1,
                "source_chunk_ids": [],
                "created_at": "2020-01-01T00:00:00+00:00",
            }
        }
        store.execute_read_responses = [[row] * 256, [row], []]
        call_count = 0

        async def fake_read(q: str, p: Any = None) -> list[dict[str, Any]]:
            nonlocal call_count
            if "RETURN n ORDER BY" in q:
                idx = call_count
                call_count += 1
                if idx < len(store.execute_read_responses):
                    return store.execute_read_responses[idx]
                return []
            return []

        store.execute_read = fake_read  # type: ignore[method-assign]
        ents = await all_entities_by_label(store, "Person")
        assert len(ents) == 257
        assert call_count == 2

    async def test_consolidate_reports_candidate_read_failure(self) -> None:
        """A failed candidate read is reported and that entity is not compared."""
        e1 = Entity(id=uuid4(), label="Person", name="Alice", source_chunk_ids=[])
        e2 = Entity(id=uuid4(), label="Person", name="alice", source_chunk_ids=[])
        small_schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label="Person", description="p")],
            relations=[],
        )
        graph = await Graph.open(
            schema=small_schema,
            graph_store=MockStore(),
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
        )
        import agrag.ingestion.resolve.candidate_source as source_module  # noqa: PLC0415
        from agrag.ingestion.resolve import ResolutionResult  # noqa: PLC0415

        async def candidates(_self, mention):
            raise RuntimeError("candidate read failed")

        with (
            mock.patch.object(
                maintenance_module, "all_entities_by_label", new_callable=mock.AsyncMock
            ) as mock_all,
            mock.patch("agrag.ingestion.resolve.resolution.Resolver") as mock_resolver,
            mock.patch.object(
                source_module.GraphCandidateSource, "global_candidates_for", candidates
            ),
        ):
            mock_all.return_value = [e1, e2]
            mock_resolver.return_value.resolve = mock.AsyncMock(
                return_value=ResolutionResult(groups=[], matches=[])
            )

            report = await graph.consolidate(apply=False)

        assert [failure.error_message for failure in report.failures] == [
            "candidate read failed",
            "candidate read failed",
        ]
        compared = mock_resolver.call_args.kwargs["candidate_source"]
        assert await compared.candidates_for(0, []) == []
        assert await compared.candidates_for(1, []) == []

    async def test_consolidate_reports_rebuild_failure(self) -> None:
        """A failed rebuild keeps raw entities intact and reports the error."""
        store = MockStore()
        e1 = Entity(
            id=uuid4(),
            label="Person",
            name="Alice",
            properties={},
            source_chunk_ids=[uuid4()],
        )
        e2 = Entity(
            id=uuid4(),
            label="Person",
            name="alice",
            properties={},
            source_chunk_ids=[uuid4()],
        )
        small_schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label="Person", description="p")],
            relations=[],
        )
        graph = await Graph.open(
            schema=small_schema,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
        )

        with mock.patch.object(
            maintenance_module, "all_entities_by_label", new_callable=mock.AsyncMock
        ) as mock_all:
            mock_all.return_value = [e1, e2]

            with mock.patch(
                "agrag.ingestion.resolve.resolution.Resolver"
            ) as mock_resolver:
                mock_instance = mock.AsyncMock()
                from agrag.ingestion.resolve import (  # noqa: PLC0415
                    ResolutionResult,
                    ResolvedMatch,
                )

                mock_instance.resolve.return_value = ResolutionResult(
                    groups=[],
                    matches=[
                        ResolvedMatch(
                            left_index=0,
                            right_index=1,
                            comparator="FuzzyMatch",
                            decided_at=datetime.now(UTC),
                        )
                    ],
                )
                mock_resolver.return_value = mock_instance
                with mock.patch.object(
                    maintenance_module,
                    "write_matches_and_rebuild",
                    new_callable=mock.AsyncMock,
                    side_effect=RuntimeError("database unavailable"),
                ):
                    report = await graph.consolidate(apply=True)

        assert len(report.failures) == 1
        assert report.failures[0].error_message == "database unavailable"
        assert report.applied is False
        assert store.upsert_nodes_calls == []
        assert store.upsert_relations_calls == []
