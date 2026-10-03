"""Tests for the public Graph ingestion API (agrag.ingestion.Graph).

Graph.open and Graph.add are exercised against fake GraphStore, Embedder, and
Extractor implementations, so no real database or LLM calls are made. Covers
adding from a directory, raw text, and prebuilt documents; the mutually
exclusive input validation; error policies (raise, skip, quarantine) for
unsupported sources; progress callbacks; and that Graph.open closes the store
when provisioning fails at any stage (connect, setup_constraints,
ensure_vector_index).
"""

import hashlib
import importlib
import json
from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import Tracer

import agrag.ingestion._cutover as cutover_module
import agrag.ingestion.graph as graph_module
from agrag.chunking import (
    DEFAULT_CHUNKING,
    Chunking,
    ChunkingRule,
    RecursiveChunker,
    RuleMatch,
    TokenChunker,
)
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.community import (
    COMMUNITY_LABEL,
    MEMBER_OF_RELATION,
)
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_record import (
    NodeRecord,
    RelationRecord,
    UpsertResult,
)
from agrag.common.data_models.graph_schema import (
    GENERIC,
    EntityType,
    GraphSchema,
)
from agrag.common.data_models.normalization import Normalization
from agrag.common.data_models.resolved_entity import (
    MATCHES_RELATION,
    RESOLVED_AS_RELATION,
    RESOLVED_ENTITY_LABEL,
)
from agrag.common.data_models.vector_record import Distance, VectorHit
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion import Graph
from agrag.ingestion._ingest_pipeline import (
    _embed_and_upsert_chunks,
    _embed_and_upsert_survivors,
    _vector_record,
)
from agrag.ingestion._walk import chunk_documents
from agrag.ingestion.extract import Extractor
from agrag.ingestion.resolve import SYSTEM_RELATION_TYPES, ResolutionResult
from agrag.loaders.corpus.errors import UnsupportedFormatError
from agrag.loaders.corpus.readers.prose import TextLoader
from agrag.loaders.corpus.types import ErrorPolicy, ReadOptions
from agrag.observability import get_tracer
from tests.unit.ingestion._lease_fake import CutoverJobLeaseFake


_FIXTURES = Path(__file__).parents[1] / "loaders" / "corpus" / "fixtures"


class _DoclingItem:
    """A docling chunk with a text and no headings or page items."""

    class meta:  # noqa: N801
        headings: list[str] = []
        doc_items: list[object] = []

    text = "chunk"


def _chunk_docling(
    graph: Graph, document: Document, tracer: Tracer | None = None
) -> list[Chunk]:
    """Chunk a docling document with docling's chunker replaced by one chunk."""
    docling_chunking = importlib.import_module("docling.chunking")
    with patch.object(docling_chunking, "HybridChunker") as hybrid:
        hybrid.return_value.chunk.return_value = [_DoclingItem()]
        chunks, _ = chunk_documents(
            [document], chunking=graph.chunking, tracer=get_tracer(tracer)
        )
    return chunks


class _MockGraphStore(CutoverJobLeaseFake, GraphStore):
    """A no-op GraphStore for ingestion-only unit tests."""

    def __init__(self) -> None:
        """Create the store, tracking close() calls for cleanup assertions."""
        self.close_calls = 0

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        self.close_calls += 1

    def session(self) -> AbstractAsyncContextManager[Any]:
        class _MockSession:
            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *exc: object) -> None:
                return None

            async def execute_read(self, *a: Any, **kw: Any) -> list[dict[str, Any]]:
                return []

            async def execute_write(self, *a: Any, **kw: Any) -> list[dict[str, Any]]:
                return []

        return _MockSession()  # type: ignore[return-value]

    async def execute_read(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        handled = self.handle_cutover_query(query, parameters)
        if handled is not None:
            return handled
        return []

    async def setup_constraints(self) -> None:
        return None

    async def setup_indexes(self) -> None:
        return None

    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
    ) -> UpsertResult:
        return UpsertResult(written=len(nodes))

    async def upsert_relations(
        self,
        relations: Sequence[RelationRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
    ) -> UpsertResult:
        return UpsertResult(written=len(relations))

    async def ensure_vector_index(
        self, *, label: str, vector_property: str, dimensions: int, distance: Distance
    ) -> None:
        return None

    async def vector_search(
        self,
        *,
        label: str,
        vector_property: str,
        query_vector: Sequence[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        return []

    async def register_labels(self, labels: Sequence[str]) -> None:
        return None

    async def register_relation_types(self, types: Sequence[str]) -> None:
        return None


class _MockEmbedder(Embedder):
    """A fake embedder returning zero vectors."""

    model = "fake"

    async def dimensions(self) -> int:
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.0, 0.0, 0.0, 0.0] for _ in texts]


class _MockExtractor(Extractor):
    """A fake extractor returning no entities."""

    async def extract(self, chunk: Chunk, schema) -> ExtractionResult:  # type: ignore[no-untyped-def]
        return ExtractionResult(entities=[], relations=[], extractor_name="fake")


async def _open_graph() -> Graph:
    """Open a graph with fake dependencies for ingestion-only tests."""
    return await Graph.open(
        schema=GENERIC,
        graph_store=_MockGraphStore(),
        embedder=_MockEmbedder(),
        extractor=_MockExtractor(),
    )


class _RecordingOpenStore(_MockGraphStore):
    """Records the Graph.open provisioning calls it receives."""

    def __init__(self) -> None:
        """Create the store with empty provisioning call logs."""
        super().__init__()
        self.labels_calls: list[list[str]] = []
        self.relation_calls: list[list[str]] = []
        self.vector_index_labels: list[str] = []

    async def register_labels(self, labels: Sequence[str]) -> None:
        self.labels_calls.append(list(labels))

    async def register_relation_types(self, types: Sequence[str]) -> None:
        self.relation_calls.append(list(types))

    async def ensure_vector_index(
        self, *, label: str, vector_property: str, dimensions: int, distance: Distance
    ) -> None:
        self.vector_index_labels.append(label)


class TestGraphOpenRegistration:
    """Graph.open provisions resolved-entity storage."""

    async def test_open_registers_resolved_entity_names(self) -> None:
        """The derived label and match relations register alongside Community's."""
        store = _RecordingOpenStore()
        await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
        )

        assert RESOLVED_ENTITY_LABEL in store.labels_calls[0]
        assert COMMUNITY_LABEL in store.labels_calls[0]
        assert MATCHES_RELATION in store.relation_calls[0]
        assert RESOLVED_AS_RELATION in store.relation_calls[0]
        assert MEMBER_OF_RELATION in store.relation_calls[0]

    async def test_open_ensures_resolved_entity_vector_index(self) -> None:
        """Native vector search covers the derived label like Community's."""
        store = _RecordingOpenStore()
        await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
        )

        assert RESOLVED_ENTITY_LABEL in store.vector_index_labels
        assert COMMUNITY_LABEL in store.vector_index_labels


class TestGraphAdd:
    """The Graph accepts sources, text, and documents."""

    async def test_add_directory_reads_all_sources(self) -> None:
        """Add directory reads all sources."""
        graph = await _open_graph()
        result = await graph.add(_FIXTURES)
        assert result.ingestion.documents > 0
        assert result.ingestion.sources > 0

    async def test_add_single_text(self) -> None:
        """Add single text."""
        graph = await _open_graph()
        result = await graph.add(text="a short note")
        assert result.ingestion.documents == 1
        assert result.ingestion.sources == 1

    @pytest.mark.parametrize("verb", ["add", "update"])
    async def test_reports_rebuild_failures_in_storage_stats(
        self, monkeypatch: pytest.MonkeyPatch, verb: str
    ) -> None:
        """A skipped rebuild failure appears in the result storage stats."""
        graph = await _open_graph()
        graph._graph_store.execute_read = AsyncMock(  # type: ignore[method-assign]
            return_value=[]
        )
        member = Entity(
            id=uuid4(), label="Person", name="Alice", properties={}, source_chunk_ids=[]
        )
        real_ingest = graph_module.ingest_chunks

        async def _ingest_with_component(*args: object, **kwargs: Any) -> Any:
            kwargs["rebuilt_components"].append(([], [member]))
            return await real_ingest(*args, **kwargs)

        monkeypatch.setattr(graph_module, "ingest_chunks", _ingest_with_component)
        monkeypatch.setattr(
            graph_module,
            "rebuild_resolved_entities",
            AsyncMock(side_effect=RuntimeError("database unavailable")),
        )

        if verb == "add":
            result = await graph.add(text="a short note", error_policy=ErrorPolicy.SKIP)
        else:
            update = await graph.update(
                "memory://doc", text="brand new", error_policy=ErrorPolicy.SKIP
            )
            assert update.add_result is not None
            result = update.add_result

        assert result.storage.failures_total == 1
        assert result.storage.failures[0].item_id == str(member.id)
        assert result.storage.failures[0].error_message == "database unavailable"

    @pytest.mark.parametrize("verb", ["add", "update"])
    async def test_rebuilds_components_after_commit(
        self, monkeypatch: pytest.MonkeyPatch, verb: str
    ) -> None:
        """The cleanup phase rebuilds each component the job rebuilt."""
        graph = await _open_graph()
        graph._graph_store.execute_read = AsyncMock(  # type: ignore[method-assign]
            return_value=[]
        )
        low, high = sorted([uuid4(), uuid4()], key=str)
        members = [
            Entity(id=entity_id, label="Person", name=str(entity_id))
            for entity_id in (high, low)
        ]
        real_ingest = graph_module.ingest_chunks

        async def _ingest_with_component(*args: object, **kwargs: Any) -> Any:
            kwargs["rebuilt_components"].append(([], members))
            return await real_ingest(*args, **kwargs)

        rebuild = AsyncMock(return_value=[])
        monkeypatch.setattr(graph_module, "ingest_chunks", _ingest_with_component)
        monkeypatch.setattr(graph_module, "rebuild_resolved_entities", rebuild)

        if verb == "add":
            await graph.add(text="a short note")
        else:
            await graph.update("memory://doc", text="brand new")

        rebuild.assert_awaited_once()
        assert rebuild.await_args.args[0] == [low]

    async def test_add_requires_exactly_one_input(self) -> None:
        """Add requires exactly one input."""
        graph = await _open_graph()
        with pytest.raises(ValueError):
            await graph.add()
        with pytest.raises(ValueError):
            await graph.add(text="x", documents=[])

    async def test_update_normalizes_text_before_comparing_content_hash(self) -> None:
        """An NFKC-equivalent update does not replace the current version."""
        graph = await _open_graph()
        node_id = uuid4()
        graph._graph_store.execute_read = AsyncMock(  # type: ignore[method-assign]
            return_value=[
                {
                    "id": str(node_id),
                    "current_content_hash": hashlib.sha256(b"K").hexdigest(),
                }
            ]
        )
        graph._graph_store.execute_write = AsyncMock(  # type: ignore[method-assign]
            return_value=[]
        )

        result = await graph.update("memory://doc", text="Ｋ")

        assert result.no_op is True
        graph._graph_store.execute_write.assert_not_awaited()

    async def test_update_not_found_behaves_like_fresh_add(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unknown document_key ingests with nothing to close first."""
        graph = await _open_graph()
        graph._graph_store.execute_read = AsyncMock(  # type: ignore[method-assign]
            return_value=[]
        )
        closes: list[object] = []
        real_close = cutover_module.close_open_part_of_edges

        async def _spy_close(*args: object, **kwargs: object) -> int:
            closes.append((args, kwargs))
            return await real_close(*args, **kwargs)

        monkeypatch.setattr(cutover_module, "close_open_part_of_edges", _spy_close)
        real_ingest = graph_module.ingest_chunks
        ingest_calls = 0

        async def _count_ingest(*args: object, **kwargs: object) -> object:
            nonlocal ingest_calls
            ingest_calls += 1
            return await real_ingest(*args, **kwargs)

        monkeypatch.setattr(graph_module, "ingest_chunks", _count_ingest)

        result = await graph.update("memory://doc", text="brand new")

        assert result.no_op is False
        assert result.previous_content_hash is None
        assert result.chunks_closed == 0
        assert result.add_result is not None
        assert closes == []
        assert ingest_calls == 1

    async def test_update_rejects_missing_input(self) -> None:
        """Update with neither text nor source raises like add does."""
        graph = await _open_graph()

        with pytest.raises(ValueError, match="exactly one"):
            await graph.update("memory://doc")

    async def test_update_rejects_multiple_inputs(self) -> None:
        """Update requires exactly one replacement source."""
        graph = await _open_graph()

        with pytest.raises(ValueError, match="exactly one"):
            await graph.update("memory://doc", text="new", source="other.txt")

    async def test_update_reads_a_single_file_source(self) -> None:
        """Update accepts a loader-backed single-file source."""
        graph = await _open_graph()

        result = await graph.update(
            "memory://doc",
            source=_FIXTURES / "sample.txt",
        )

        assert result.no_op is False
        assert result.add_result is not None

    async def test_update_rejects_source_with_multiple_documents(self) -> None:
        """Update rejects sources that do not resolve to exactly one document."""
        graph = await _open_graph()

        with pytest.raises(ValueError, match="exactly one document"):
            await graph.update("memory://doc", source=_FIXTURES / "sample.csv")

    async def test_add_rejects_duplicate_document_keys(self) -> None:
        """An add call cannot join chunks from separate document versions."""
        graph = await _open_graph()
        first = Document(
            text="first",
            title="first",
            uri="memory://first",
            document_key="shared",
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash="first",
            loader_name="inline",
            char_count=5,
            line_count=1,
        )
        second = first.model_copy(update={"text": "second", "content_hash": "second"})

        with pytest.raises(ValueError, match="distinct document keys"):
            await graph.add(documents=[first, second])

    def test_docling_chunks_use_distinct_ids_for_each_content_version(self) -> None:
        """Same-index docling chunks retain their separate version histories."""
        graph = Graph(
            schema=GENERIC,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
        )
        first = Document(
            text="first",
            title="first",
            uri="memory://doc",
            document_key="memory://doc",
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash="first",
            loader_name="docling",
            char_count=5,
            line_count=1,
            metadata={"_docling_document": object()},
        )
        second = first.model_copy(update={"content_hash": "second"})

        first_chunk = _chunk_docling(graph, first)[0]
        second_chunk = _chunk_docling(graph, second)[0]

        assert first_chunk.document_id == second_chunk.document_id
        assert first_chunk.id != second_chunk.id

    async def test_delete_missing_document_is_a_no_op(self) -> None:
        """Deleting an unknown document does not write graph state."""
        graph = await _open_graph()
        graph._graph_store.execute_read = AsyncMock(  # type: ignore[method-assign]
            return_value=[]
        )
        graph._graph_store.execute_write = AsyncMock(  # type: ignore[method-assign]
            return_value=[{"closed": 1}]
        )

        result = await graph.delete_document("memory://missing")

        assert result.no_op is True
        graph._graph_store.execute_write.assert_not_awaited()

    async def test_on_progress_receives_stats(self) -> None:
        """On progress receives stats."""
        graph = await _open_graph()
        seen: list[Any] = []
        await graph.add(_FIXTURES, on_progress=seen.append)
        assert seen

    async def test_raise_policy_stops_on_unsupported_format(
        self, tmp_path: Path
    ) -> None:
        """Raise policy stops on unsupported format."""
        bad = tmp_path / "file.unknown"
        bad.write_text("x")
        graph = await _open_graph()
        with pytest.raises(UnsupportedFormatError):
            await graph.add(bad)

    async def test_skip_policy_counts_skipped_source(self, tmp_path: Path) -> None:
        """Skip policy counts skipped source."""
        bad = tmp_path / "file.unknown"
        bad.write_text("x")
        graph = await _open_graph()
        result = await graph.add(bad, error_policy=ErrorPolicy.SKIP)
        assert result.ingestion.skipped == 1
        assert result.ingestion.documents == 0

    async def test_quarantine_policy_counts_quarantined(self, tmp_path: Path) -> None:
        """Quarantine policy counts quarantined."""
        bad = tmp_path / "file.unknown"
        bad.write_text("x")
        graph = await _open_graph()
        result = await graph.add(bad, error_policy=ErrorPolicy.QUARANTINE)
        assert result.ingestion.quarantined == 1
        assert result.ingestion.quarantined_items

    async def test_loader_override_with_text_raises(self) -> None:
        """A loader override has no effect on ``text`` and must be rejected."""
        graph = await _open_graph()
        with pytest.raises(ValueError):
            await graph.add(text="x", loader=TextLoader())

    async def test_loader_override_with_documents_raises(self) -> None:
        """A loader override has no effect on ``documents`` and must be rejected."""
        graph = await _open_graph()
        doc = Document(
            text="prebuilt",
            title="t",
            uri="u",
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash="h",
            loader_name="text",
            char_count=8,
            line_count=1,
        )
        with pytest.raises(ValueError):
            await graph.add(documents=[doc], loader=TextLoader())

    async def test_glob_pattern_skips_directory_matches(self, tmp_path: Path) -> None:
        """A glob pattern that also matches a directory does not choke on it."""
        (tmp_path / "sub").mkdir()
        (tmp_path / "a.txt").write_text("hello")
        graph = await _open_graph()
        result = await graph.add(str(tmp_path / "*"))
        assert result.ingestion.documents == 1
        assert result.ingestion.sources == 1


class TestConsolidateResolutionContext:
    """Graph.consolidate passes real LLM verification context to Resolver.

    The equivalent coverage for Graph.add lives in
    tests/unit/ingestion/test_ingest_pipeline.py, against ingest_chunks --
    the shared pipeline core add() delegates to -- since that is where the
    neighbor and similarity context is actually built for that path.
    """

    async def test_consolidate_neighbors_are_keyed_by_entity_index(self) -> None:
        """Consolidate's neighbor context is keyed by entity list position."""
        schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label="Person", description="p")],
            relations=[],
        )
        graph = await Graph.open(
            schema=schema,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
        )
        first = Entity(id=uuid4(), label="Person", name="Alice", properties={})
        second = Entity(id=uuid4(), label="Person", name="alice", properties={})
        resolver_instance = AsyncMock()
        resolver_instance.resolve.return_value = ResolutionResult(groups=[], matches=[])
        fetch_neighbors = AsyncMock(return_value={first.id: ["KNOWS Bob"]})

        with (
            mock.patch.object(
                graph,
                "_all_entities_by_label",
                new_callable=AsyncMock,
                return_value=[first, second],
            ),
            mock.patch(
                "agrag.ingestion.resolve.resolution.Resolver",
                return_value=resolver_instance,
            ),
            mock.patch(
                "agrag.ingestion.resolve.resolution.fetch_persisted_neighbors",
                fetch_neighbors,
            ),
        ):
            await graph.consolidate(apply=False)

        assert fetch_neighbors.await_args.args[0] == [first.id, second.id]
        assert (
            fetch_neighbors.await_args.kwargs["exclude_relation_types"]
            == SYSTEM_RELATION_TYPES
        )
        kwargs = resolver_instance.resolve.await_args.kwargs
        assert kwargs["neighbors_by_index"] == {0: ["KNOWS Bob"], 1: []}
        assert kwargs["similarity_by_pair"] == {}


class TestGraphOpen:
    """Graph.open provisioning failure handling."""

    async def test_connect_failure_closes_store(self) -> None:
        """A failure inside connect() itself still closes the store.

        Regression test: connect() can build and cache a driver before
        connectivity verification fails, so a failure here must still reach
        close() instead of leaking that driver's connection pool.
        """

        class _FailingStore(_MockGraphStore):
            async def connect(self) -> None:
                raise RuntimeError("boom")

        store = _FailingStore()
        with pytest.raises(RuntimeError, match="boom"):
            await Graph.open(
                schema=GENERIC,
                graph_store=store,
                embedder=_MockEmbedder(),
                extractor=_MockExtractor(),
            )
        assert store.close_calls == 1

    async def test_setup_constraints_failure_closes_store(self) -> None:
        """A provisioning failure after connect() still closes the store.

        Regression test: a failure between connect() and the end of
        provisioning must not leak the connection. Fails at
        setup_constraints, before the later stages (setup_indexes,
        embedder.dimensions(), ensure_vector_index) even run.
        """

        class _FailingStore(_MockGraphStore):
            async def setup_constraints(self) -> None:
                raise RuntimeError("boom")

        store = _FailingStore()
        with pytest.raises(RuntimeError, match="boom"):
            await Graph.open(
                schema=GENERIC,
                graph_store=store,
                embedder=_MockEmbedder(),
                extractor=_MockExtractor(),
            )
        assert store.close_calls == 1

    async def test_ensure_vector_index_failure_closes_store(self) -> None:
        """A failure in the last provisioning stage still closes the store."""

        class _FailingStore(_MockGraphStore):
            async def ensure_vector_index(self, **kwargs: Any) -> None:
                raise RuntimeError("boom")

        store = _FailingStore()
        with pytest.raises(RuntimeError, match="boom"):
            await Graph.open(
                schema=GENERIC,
                graph_store=store,
                embedder=_MockEmbedder(),
                extractor=_MockExtractor(),
            )
        assert store.close_calls == 1


class TestGraphVectorStore:
    """Test Graph's vector-store synchronization safeguards."""

    def test_vector_record_includes_filterable_properties(self) -> None:
        """Optional metadata augments the standard vector payload."""
        record = _vector_record(
            uuid4(),
            [0.1],
            label="Community",
            text="Report",
            properties={"tenant": "a"},
        )

        assert record.payload == {
            "label": "Community",
            "text": "Report",
            "tenant": "a",
        }

    async def test_vector_upsert_failures_leave_chunk_and_entity_vectors(self) -> None:
        """Failed vector writes leave the collection untouched.

        The mirror has no conditional write, so a delete issued after
        checking the graph would race a concurrent call that owns the
        record. The stored record keeps its previous text until the next
        successful ingest replaces it.
        """
        chunk_id = uuid4()
        chunk = MagicMock(id=chunk_id, text="Chunk", embedding=None)
        entity = Entity(id=uuid4(), label="Person", name="Ada", properties={})
        graph_store = AsyncMock()
        graph_store.execute_write.side_effect = [
            [{"id": str(chunk_id)}],
            [{"id": str(entity.id)}],
        ]
        chunk_store = AsyncMock()
        entity_store = AsyncMock()
        chunk_store.upsert.side_effect = RuntimeError("chunk upsert failed")
        entity_store.upsert.side_effect = RuntimeError("entity upsert failed")

        chunk_failures = await _embed_and_upsert_chunks(
            [chunk],
            embedder=_MockEmbedder(),
            graph_store=graph_store,
            error_policy=ErrorPolicy.SKIP,
            vector_store=chunk_store,
            vector_collection="chunks",
        )
        entity_failures = await _embed_and_upsert_survivors(
            {entity.id: entity},
            embedder=_MockEmbedder(),
            graph_store=graph_store,
            error_policy=ErrorPolicy.SKIP,
            vector_store=entity_store,
            vector_collection="entities",
        )

        assert chunk_failures[0].item_id == "chunk_vector_store"
        assert entity_failures[0].item_id == "entity_vector_store"
        chunk_store.delete.assert_not_awaited()
        entity_store.delete.assert_not_awaited()


class TestGraphChunking:
    """Graph chunks each document with the chunker its rules pick."""

    _TEXT = "The quick brown fox jumps over the lazy dog. " * 20

    async def _open(self, chunking: Chunking | None = None) -> Graph:
        kwargs = {} if chunking is None else {"chunking": chunking}
        return await Graph.open(
            schema=GENERIC,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
            **kwargs,
        )

    async def test_default_chunking_records_the_fallback_on_every_chunk(self) -> None:
        """Without a chunking argument, chunks name the recursive fallback."""
        graph = await self._open()

        result = await graph.add(text=self._TEXT, return_chunks=True)

        fallback = DEFAULT_CHUNKING.fallback
        assert result.chunks
        assert {c.chunker for c in result.chunks} == {"recursive"}
        assert {c.chunker_hash for c in result.chunks} == {fallback.fingerprint()}
        assert result.chunking.documents_by_rule == {"fallback": 1}
        assert result.chunking.chunks_by_strategy == {"recursive": len(result.chunks)}

    async def test_custom_rule_picks_the_chunker_for_matching_documents(self) -> None:
        """A rule on the format sends Markdown to the token chunker only."""
        chunking = Chunking(
            rules=[
                ChunkingRule(
                    match=RuleMatch(source_formats=[SourceFormat.MARKDOWN]),
                    chunker=TokenChunker(chunk_size=32, tokenizer="character"),
                )
            ],
            fallback=RecursiveChunker(chunk_size=200, tokenizer="character"),
        )
        graph = await self._open(chunking)
        assert graph.chunking is chunking

        result = await graph.add(source=_FIXTURES, return_chunks=True)

        by_uri = {Path(m.document_key).suffix: m for m in result.chunking.matches}
        assert by_uri[".md"].strategy == "token"
        assert by_uri[".md"].rule == 0
        assert by_uri[".txt"].strategy == "recursive"
        assert by_uri[".txt"].rule is None
        assert result.chunking.matches_total == len(result.chunking.matches)
        assert sum(result.chunking.chunks_by_strategy.values()) == len(result.chunks)

    async def test_add_and_update_pass_read_options_to_the_loaders(self) -> None:
        """A none Unicode form keeps a ligature in the chunk text on both paths."""
        graph = await self._open()
        options = ReadOptions(normalization=Normalization(unicode_form="none"))

        added = await graph.add(
            text="\ufb01 rst line", read_options=options, return_chunks=True
        )
        updated = await graph.update(
            "memory://doc", text="\ufb01 rst line", read_options=options
        )

        assert added.chunks[0].text == "\ufb01 rst line"
        assert (
            updated.new_content_hash
            == hashlib.sha256("\ufb01 rst line".encode()).hexdigest()
        )

    async def _update(
        self, graph: Graph, stored_hash: str | None, *, has_chunk: bool = True
    ) -> bool:
        node_row = {
            "id": str(uuid4()),
            "current_content_hash": hashlib.sha256(self._TEXT.encode()).hexdigest(),
        }
        chunk_rows = [{"chunker_hash": stored_hash}] if has_chunk else []

        async def _read(query: str, *args: object, **kwargs: object) -> list[dict]:
            if "current_content_hash" in query:
                return [node_row]
            if "chunker_hash" in query:
                return chunk_rows
            return []

        graph._graph_store.execute_read = AsyncMock(  # type: ignore[method-assign]
            side_effect=_read
        )
        result = await graph.update("memory://doc", text=self._TEXT)
        return result.no_op

    async def test_update_is_a_no_op_when_content_and_chunker_are_unchanged(
        self,
    ) -> None:
        """The stored fingerprint equals the chunker's, so nothing runs."""
        graph = await self._open()
        _, chunker = graph.chunking.select(
            Document(
                text="x",
                title="t",
                uri="memory://doc",
                source_format=SourceFormat.TXT,
                family=DocumentFamily.PROSE,
                content_hash="h",
                loader_name="inline",
                char_count=1,
            )
        )

        assert await self._update(graph, chunker.fingerprint()) is True

    async def test_update_rechunks_when_only_the_chunker_changed(self) -> None:
        """Same content with a different stored fingerprint runs the full update."""
        graph = await self._open()

        assert await self._update(graph, "0123456789abcdef") is False

    async def test_update_treats_chunks_without_a_fingerprint_as_unchanged(
        self,
    ) -> None:
        """A chunk from before chunkers were recorded does not force a re-chunk."""
        graph = await self._open()

        assert await self._update(graph, None) is True

    async def test_update_without_current_chunks_is_a_no_op_on_same_content(
        self,
    ) -> None:
        """A document with no readable chunk keeps the content-hash rule."""
        graph = await self._open()

        assert await self._update(graph, None, has_chunk=False) is True


class TestChunkDocumentSpans:
    """Chunker spans carry document identity and output counts."""

    def _document(self, key: str = "memory://doc") -> Document:
        """Return a prose document with enough text to chunk."""
        text = "chunk me please. " * 40
        return Document(
            text=text,
            title="t",
            uri=key,
            document_key=key,
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash=key,
            loader_name="text",
            char_count=len(text),
            line_count=1,
        )

    def test_chunk_document_span_carries_attributes(self) -> None:
        """The chunk span records the document key and chunk count."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        graph = Graph(
            schema=GENERIC,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
            tracer=provider.get_tracer("test"),
        )
        document = self._document()
        chunks, matches = chunk_documents(
            [document], chunking=graph.chunking, tracer=provider.get_tracer("test")
        )
        assert chunks
        assert [m.strategy for m in matches] == ["recursive"]
        spans = [
            span
            for span in exporter.get_finished_spans()
            if span.name == "agrag.ingestion.chunk_document"
        ]
        assert len(spans) == 1
        assert spans[0].attributes is not None
        assert (
            spans[0].attributes["agrag.document_key"] == document.resolved_document_key
        )
        assert spans[0].attributes["agrag.chunks_produced"] == len(chunks)
        assert spans[0].attributes["agrag.chunker.strategy"] == "recursive"
        assert spans[0].attributes["agrag.chunker.rule"] == "fallback"
        assert spans[0].attributes["agrag.chunker.hash"] == chunks[0].chunker_hash
        settings = json.loads(str(spans[0].attributes["agrag.chunker.settings"]))
        assert settings["chunk_size"] == 1024

    def test_docling_document_span_names_the_docling_rule(self) -> None:
        """A docling document is chunked under rule 0 with the docling strategy."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        graph = Graph(
            schema=GENERIC,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
            tracer=provider.get_tracer("test"),
        )

        text = "docling doc"
        document = Document(
            text=text,
            title="t",
            uri="memory://docling",
            document_key="memory://docling",
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash="docling",
            loader_name="docling",
            char_count=len(text),
            line_count=1,
            metadata={"_docling_document": object()},
        )
        chunks = _chunk_docling(graph, document, provider.get_tracer("test"))
        assert chunks
        spans = [
            span
            for span in exporter.get_finished_spans()
            if span.name == "agrag.ingestion.chunk_document"
        ]
        assert len(spans) == 1
        assert spans[0].attributes is not None
        assert (
            spans[0].attributes["agrag.document_key"] == document.resolved_document_key
        )
        assert spans[0].attributes["agrag.chunks_produced"] == len(chunks)
        assert spans[0].attributes["agrag.chunker.strategy"] == "docling"
        assert spans[0].attributes["agrag.chunker.rule"] == "0"
