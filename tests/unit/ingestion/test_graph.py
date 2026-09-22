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
from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import agrag.ingestion.graph as graph_module
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_record import (
    NodeRecord,
    RelationRecord,
    UpsertResult,
)
from agrag.common.data_models.graph_schema import GENERIC
from agrag.common.data_models.provenance import PageProvenance
from agrag.common.data_models.vector_record import Distance, VectorHit
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion import Graph
from agrag.ingestion._ingest_pipeline import (
    _embed_and_upsert_chunks,
    _embed_and_upsert_survivors,
    _vector_record,
)
from agrag.ingestion.extract import Extractor
from agrag.loaders.corpus.errors import UnsupportedFormatError
from agrag.loaders.corpus.readers.prose import TextLoader
from agrag.loaders.corpus.types import ErrorPolicy


_FIXTURES = Path(__file__).parents[1] / "loaders" / "corpus" / "fixtures"


class _MockGraphStore(GraphStore):
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
        return []

    async def setup_constraints(self) -> None:
        return None

    async def setup_indexes(self) -> None:
        return None

    async def upsert_nodes(
        self, label: str, nodes: Sequence[NodeRecord], *, batch_size: int = 256
    ) -> UpsertResult:
        return UpsertResult(written=len(nodes))

    async def upsert_relations(
        self, relations: Sequence[RelationRecord], *, batch_size: int = 256
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


class TestGraphAdd:
    """The Graph accepts sources, text, and documents."""

    async def test_open_returns_a_graph(self) -> None:
        """Open returns a graph."""
        graph = await _open_graph()
        assert isinstance(graph, Graph)

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

    async def test_add_prebuilt_documents(self) -> None:
        """Add prebuilt documents."""
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
        result = await graph.add(documents=[doc])
        assert result.ingestion.documents == 1

    async def test_add_exposes_the_chunks_it_produced(self) -> None:
        """Add returns the chunks it computed, not just counts."""
        graph = await _open_graph()
        result = await graph.add(text="a short note", return_chunks=True)
        assert result.chunks
        assert result.chunks[0].text

    async def test_add_requires_exactly_one_input(self) -> None:
        """Add requires exactly one input."""
        graph = await _open_graph()
        with pytest.raises(ValueError):
            await graph.add()
        with pytest.raises(ValueError):
            await graph.add(text="x", documents=[])

    async def test_update_returns_no_op_for_unchanged_content(self) -> None:
        """Update skips ingestion when the stored hash is unchanged."""
        graph = await _open_graph()
        node_id = uuid4()
        graph._graph_store.execute_read = AsyncMock(  # type: ignore[method-assign]
            return_value=[
                {
                    "id": str(node_id),
                    "current_content_hash": (
                        "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
                    ),
                }
            ]
        )

        result = await graph.update("memory://doc", text="test")

        assert result.no_op is True
        assert result.chunks_closed == 0
        assert result.add_result is None

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

    async def test_delete_document_closes_current_edges(self) -> None:
        """Delete closes current edges and keeps the document result."""
        graph = await _open_graph()
        node_id = uuid4()
        graph._graph_store.execute_read = AsyncMock(  # type: ignore[method-assign]
            return_value=[{"id": str(node_id), "current_content_hash": "hash"}]
        )
        graph._graph_store.execute_write = AsyncMock(  # type: ignore[method-assign]
            return_value=[{"closed": 2}]
        )

        result = await graph.delete_document("memory://doc")

        assert result.no_op is False
        assert result.chunks_closed == 2
        assert result.add_result is None

    async def test_delete_document_writes_nothing_but_closing_edges(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Delete closes edges exactly once without ingesting or upserting."""
        store = _MockGraphStore()
        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
        )
        node_id = uuid4()
        store.execute_read = AsyncMock(  # type: ignore[method-assign]
            return_value=[{"id": str(node_id), "current_content_hash": "hash"}]
        )
        store.execute_write = AsyncMock(  # type: ignore[method-assign]
            return_value=[{"closed": 2}]
        )
        ingest_mock = AsyncMock()
        monkeypatch.setattr(graph_module, "ingest_chunks", ingest_mock)
        close_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        real_close = graph_module.close_open_part_of_edges

        async def _count_close(*args: object, **kwargs: object) -> int:
            close_calls.append((args, kwargs))
            return await real_close(*args, **kwargs)

        monkeypatch.setattr(graph_module, "close_open_part_of_edges", _count_close)
        node_calls: list[object] = []
        relation_calls: list[object] = []
        real_upsert_nodes = store.upsert_nodes
        real_upsert_relations = store.upsert_relations

        async def _spy_nodes(*args: object, **kwargs: object) -> object:
            node_calls.append((args, kwargs))
            return await real_upsert_nodes(*args, **kwargs)

        async def _spy_relations(*args: object, **kwargs: object) -> object:
            relation_calls.append((args, kwargs))
            return await real_upsert_relations(*args, **kwargs)

        store.upsert_nodes = _spy_nodes  # type: ignore[method-assign]
        store.upsert_relations = _spy_relations  # type: ignore[method-assign]

        result = await graph.delete_document("memory://doc")

        assert result.no_op is False
        assert result.new_content_hash is None
        assert result.chunks_closed == 2
        assert result.add_result is None
        assert len(close_calls) == 1
        ingest_mock.assert_not_awaited()
        assert node_calls == []
        assert relation_calls == []

    async def test_delete_document_twice_closes_zero_new_edges(self) -> None:
        """A second delete closes nothing further: closing is idempotent."""
        graph = await _open_graph()
        node_id = uuid4()
        graph._graph_store.execute_read = AsyncMock(  # type: ignore[method-assign]
            return_value=[{"id": str(node_id), "current_content_hash": "hash"}]
        )
        graph._graph_store.execute_write = AsyncMock(  # type: ignore[method-assign]
            side_effect=[[{"closed": 2}], [{"closed": 0}]]
        )

        first = await graph.delete_document("memory://doc")
        second = await graph.delete_document("memory://doc")

        assert first.chunks_closed == 2
        assert second.chunks_closed == 0

    async def test_update_closes_edges_before_ingesting_changed_content(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Update closes the old version before calling the ingest pipeline."""
        graph = await _open_graph()
        node_id = uuid4()
        graph._graph_store.execute_read = AsyncMock(  # type: ignore[method-assign]
            return_value=[{"id": str(node_id), "current_content_hash": "old"}]
        )
        graph._graph_store.execute_write = AsyncMock(  # type: ignore[method-assign]
            return_value=[{"closed": 3}]
        )
        add_result = await graph.add(text="seed")
        ingest_mock = AsyncMock(return_value=add_result)
        monkeypatch.setattr(graph_module, "ingest_chunks", ingest_mock)

        result = await graph.update("memory://doc", text="new")

        assert result.no_op is False
        assert result.previous_content_hash == "old"
        assert result.chunks_closed == 3
        assert result.add_result is add_result
        ingest_mock.assert_awaited_once()

    async def test_update_no_op_never_ingests(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unchanged update never reaches the ingest pipeline or the extractor."""
        graph = await _open_graph()
        node_id = uuid4()
        graph._graph_store.execute_read = AsyncMock(  # type: ignore[method-assign]
            return_value=[
                {
                    "id": str(node_id),
                    "current_content_hash": (
                        "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
                    ),
                }
            ]
        )
        ingest_mock = AsyncMock()
        monkeypatch.setattr(graph_module, "ingest_chunks", ingest_mock)

        result = await graph.update("memory://doc", text="test")

        assert result.no_op is True
        assert result.add_result is None
        ingest_mock.assert_not_awaited()

    async def test_update_not_found_behaves_like_fresh_add(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unknown document_key ingests with nothing to close first."""
        graph = await _open_graph()
        graph._graph_store.execute_read = AsyncMock(  # type: ignore[method-assign]
            return_value=[]
        )
        closes: list[object] = []
        real_close = graph_module.close_open_part_of_edges

        async def _spy_close(*args: object, **kwargs: object) -> int:
            closes.append((args, kwargs))
            return await real_close(*args, **kwargs)

        monkeypatch.setattr(graph_module, "close_open_part_of_edges", _spy_close)
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

    async def test_update_change_closes_before_adding(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Changed content closes old edges before the fresh ingest runs."""
        graph = await _open_graph()
        node_id = uuid4()
        graph._graph_store.execute_read = AsyncMock(  # type: ignore[method-assign]
            return_value=[{"id": str(node_id), "current_content_hash": "old"}]
        )
        events: list[str] = []
        real_close = graph_module.close_open_part_of_edges

        async def _spy_close(*args: object, **kwargs: object) -> int:
            events.append("close")
            return await real_close(*args, **kwargs)

        monkeypatch.setattr(graph_module, "close_open_part_of_edges", _spy_close)
        real_ingest = graph_module.ingest_chunks

        async def _spy_ingest(*args: object, **kwargs: object) -> object:
            events.append("ingest")
            return await real_ingest(*args, **kwargs)

        monkeypatch.setattr(graph_module, "ingest_chunks", _spy_ingest)

        result = await graph.update("memory://doc", text="new")

        assert result.no_op is False
        assert events == ["close", "ingest"]

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

    def test_docling_chunks_use_distinct_ids_for_each_content_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Same-index docling chunks retain their separate version histories."""
        graph = Graph(
            schema=GENERIC,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
        )
        version_ids: list[object] = []

        def fake_chunk_docling_document(
            docling_doc: object, document_id, *, version_id=None
        ) -> list[Chunk]:
            del docling_doc
            version_ids.append(version_id)
            provenance = PageProvenance(page_spans=[])
            return [
                Chunk(
                    id=Chunk.id_for(
                        document_id=document_id,
                        version_id=version_id,
                        provenance=provenance,
                        index=0,
                    ),
                    document_id=document_id,
                    text="chunk",
                    provenance=provenance,
                )
            ]

        monkeypatch.setattr(
            "agrag.ingestion.graph.chunk_docling_document", fake_chunk_docling_document
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

        first_chunk = graph._chunk_documents([first])[0]
        second_chunk = graph._chunk_documents([second])[0]

        assert first_chunk.document_id == second_chunk.document_id
        assert first_chunk.id != second_chunk.id
        assert version_ids[0] != version_ids[1]

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

    async def test_successful_open_does_not_close_store(self) -> None:
        """A successful open leaves the store connected."""
        store = _MockGraphStore()
        await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
        )
        assert store.close_calls == 0


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
