"""Tests for the public Graph ingestion API."""

from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.graph_schema import GENERIC
from agrag.common.data_models.vector_record import Distance, VectorHit
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion import Graph
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
        self, query: str, parameters: Mapping[str, Any] | None = None
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
    ) -> None:
        return None

    async def upsert_relations(
        self, relations: Sequence[RelationRecord], *, batch_size: int = 256
    ) -> None:
        return None

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
        assert result.documents > 0
        assert result.sources > 0

    async def test_add_single_text(self) -> None:
        """Add single text."""
        graph = await _open_graph()
        result = await graph.add(text="a short note")
        assert result.documents == 1
        assert result.sources == 1

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
        assert result.documents == 1

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
        assert result.skipped == 1
        assert result.documents == 0

    async def test_quarantine_policy_counts_quarantined(self, tmp_path: Path) -> None:
        """Quarantine policy counts quarantined."""
        bad = tmp_path / "file.unknown"
        bad.write_text("x")
        graph = await _open_graph()
        result = await graph.add(bad, error_policy=ErrorPolicy.QUARANTINE)
        assert result.quarantined == 1
        assert result.quarantined_items

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
        assert result.documents == 1
        assert result.sources == 1


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
