"""Tests for the public Graph ingestion API (agrag.ingestion.Graph).

Graph.open and Graph.add are exercised against fake GraphStore, Embedder, and
Extractor implementations, so no real database or LLM calls are made. Covers
adding from a directory, raw text, and prebuilt documents; the mutually
exclusive input validation; progress callbacks; and that Graph.open closes the
store when connecting fails.
"""

import hashlib
from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

import agrag.ingestion._ingest as ingest_module
import agrag.ingestion._job_cleanup as job_cleanup_module
from agrag.chunking import Chunker
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.community import (
    COMMUNITY_LABEL,
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
)
from agrag.common.data_models.normalization import Normalization
from agrag.common.data_models.resolved_entity import (
    RESOLVED_ENTITY_LABEL,
)
from agrag.common.data_models.vector_record import Distance, VectorHit
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion import Graph
from agrag.ingestion._ingest_pipeline import (
    _embed_and_upsert_chunks,
    _embed_and_upsert_survivors,
)
from agrag.ingestion.extract import Extractor
from agrag.loaders.prose import TextLoader
from agrag.loaders.types import ErrorPolicy, ReadOptions
from tests.unit.ingestion._lease_fake import CutoverJobLeaseFake


_FIXTURES = Path(__file__).parents[1] / "loaders" / "fixtures"


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


async def _open_graph(store: _MockGraphStore | None = None) -> Graph:
    """Open a graph with fake dependencies for ingestion-only tests."""
    return await Graph.open(
        schema=GENERIC,
        graph_store=store if store is not None else _MockGraphStore(),
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

    async def test_add_requires_exactly_one_input(self) -> None:
        """Add requires exactly one input."""
        graph = await _open_graph()
        with pytest.raises(ValueError):
            await graph.add()
        with pytest.raises(ValueError):
            await graph.add(text="x", documents=[])

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

    def test_chunks_use_distinct_ids_for_each_content_version(self) -> None:
        """Same-index chunks retain their separate version histories."""
        first = Document(
            text="first",
            title="first",
            uri="memory://doc",
            document_key="memory://doc",
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash="first",
            loader_name="text",
            char_count=5,
            line_count=1,
        )
        second = first.model_copy(update={"text": "second", "content_hash": "second"})
        chunker = Chunker()

        first_chunk = chunker.chunk(first).chunks[0]
        second_chunk = chunker.chunk(second).chunks[0]

        assert first_chunk.document_id == second_chunk.document_id
        assert first_chunk.id != second_chunk.id

    async def test_on_progress_receives_stats(self) -> None:
        """On progress receives stats."""
        graph = await _open_graph()
        seen: list[Any] = []
        await graph.add(_FIXTURES, on_progress=seen.append)
        assert seen

    async def test_loader_override_with_text_raises(self) -> None:
        """A loader override has no effect on ``text`` and must be rejected."""
        graph = await _open_graph()
        with pytest.raises(ValueError):
            await graph.add(text="x", loader=TextLoader())

    async def test_glob_pattern_skips_directory_matches(self, tmp_path: Path) -> None:
        """A glob pattern that also matches a directory does not choke on it."""
        (tmp_path / "sub").mkdir()
        (tmp_path / "a.txt").write_text("hello")
        graph = await _open_graph()
        result = await graph.add(str(tmp_path / "*"))
        assert result.ingestion.documents == 1
        assert result.ingestion.sources == 1


class TestGraphUpdate:
    """An update replaces one document version or deletes the document."""

    async def test_update_normalizes_text_before_comparing_content_hash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An NFKC-equivalent update does not replace the current version."""
        store = _MockGraphStore()
        graph = await _open_graph(store)
        node_id = uuid4()
        monkeypatch.setattr(
            store,
            "execute_read",
            AsyncMock(
                return_value=[
                    {
                        "id": str(node_id),
                        "current_content_hash": hashlib.sha256(b"K").hexdigest(),
                    }
                ]
            ),
        )
        writes = AsyncMock(return_value=[])
        monkeypatch.setattr(store, "execute_write", writes)

        result = await graph.update("memory://doc", text="Ｋ")

        assert result.no_op is True
        writes.assert_not_awaited()

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

    async def test_delete_missing_document_is_a_no_op(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Deleting an unknown document does not write graph state."""
        store = _MockGraphStore()
        graph = await _open_graph(store)
        monkeypatch.setattr(store, "execute_read", AsyncMock(return_value=[]))
        writes = AsyncMock(return_value=[{"closed": 1}])
        monkeypatch.setattr(store, "execute_write", writes)

        result = await graph.delete_document("memory://missing")

        assert result.no_op is True
        writes.assert_not_awaited()


class TestGraphFailurePolicies:
    """Skipped failures are counted in the result instead of stopping the call."""

    @pytest.mark.parametrize("verb", ["add", "update"])
    async def test_reports_rebuild_failures_in_storage_stats(
        self, monkeypatch: pytest.MonkeyPatch, verb: str
    ) -> None:
        """A skipped rebuild failure appears in the result storage stats."""
        store = _MockGraphStore()
        graph = await _open_graph(store)
        monkeypatch.setattr(store, "execute_read", AsyncMock(return_value=[]))
        member = Entity(
            id=uuid4(), label="Person", name="Alice", properties={}, source_chunk_ids=[]
        )
        real_ingest = ingest_module.ingest_chunks

        async def _ingest_with_component(*args: object, **kwargs: Any) -> Any:
            kwargs["rebuilt_components"].append(([], [member]))
            return await real_ingest(*args, **kwargs)

        monkeypatch.setattr(ingest_module, "ingest_chunks", _ingest_with_component)
        monkeypatch.setattr(
            job_cleanup_module,
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


class TestGraphVectorStore:
    """Test Graph's vector-store synchronization safeguards."""

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
    """Graph chunks every document with its one chunker."""

    _TEXT = "The quick brown fox jumps over the lazy dog. " * 20

    async def _open(
        self, chunker: Chunker | None = None
    ) -> tuple[Graph, _MockGraphStore]:
        kwargs = {} if chunker is None else {"chunker": chunker}
        store = _MockGraphStore()
        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
            **kwargs,
        )
        return graph, store

    async def test_default_chunker_is_recorded_on_every_chunk(self) -> None:
        """Without a chunker argument, chunks carry the default settings hash."""
        graph, _ = await self._open()

        result = await graph.add(text=self._TEXT, return_chunks=True)

        assert result.chunks
        assert {c.chunker for c in result.chunks} == {"section"}
        assert {c.chunker_hash for c in result.chunks} == {Chunker().fingerprint}
        assert result.chunking.chunks == len(result.chunks)
        assert result.chunking.sections == 1

    async def test_the_chunker_argument_sets_the_chunk_size(self) -> None:
        """A smaller size gives more chunks and a different hash."""
        chunker = Chunker(size=40)
        graph, _ = await self._open(chunker)
        assert graph.chunker is chunker

        result = await graph.add(text=self._TEXT, return_chunks=True)
        default_graph, _ = await self._open()
        default = await default_graph.add(text=self._TEXT, return_chunks=True)

        assert len(result.chunks) > len(default.chunks)
        assert {c.chunker_hash for c in result.chunks} == {chunker.fingerprint}

    async def test_add_and_update_pass_read_options_to_the_loaders(self) -> None:
        """A none Unicode form keeps a ligature in the chunk text on both paths."""
        graph, _ = await self._open()
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
        self,
        graph: Graph,
        store: _MockGraphStore,
        stored_hash: str | None,
        *,
        has_chunk: bool = True,
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

        with mock.patch.object(store, "execute_read", new=AsyncMock(side_effect=_read)):
            result = await graph.update("memory://doc", text=self._TEXT)
        return result.no_op

    async def test_update_is_a_no_op_when_content_and_chunker_are_unchanged(
        self,
    ) -> None:
        """The stored fingerprint equals the chunker's, so nothing runs."""
        graph, store = await self._open()

        assert await self._update(graph, store, graph.chunker.fingerprint) is True

    async def test_update_rechunks_when_only_the_chunker_changed(self) -> None:
        """Same content with a different stored fingerprint runs the full update."""
        graph, store = await self._open()

        assert await self._update(graph, store, "0123456789abcdef") is False

    async def test_update_treats_chunks_without_a_fingerprint_as_unchanged(
        self,
    ) -> None:
        """A chunk from before chunkers were recorded does not force a re-chunk."""
        graph, store = await self._open()

        assert await self._update(graph, store, None) is True
