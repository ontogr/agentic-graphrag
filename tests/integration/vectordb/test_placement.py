"""Graph.open keeps its vector placement fixed for each graph database."""

from collections.abc import Sequence

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.vector_record import Distance, VectorKind
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.vectordb.errors import VectorPlacementError
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration._backend import build_test_store
from tests.integration._fake_vector_store import FakeVectorStore


pytestmark = pytest.mark.xdist_group(name="vector_placement")


class _FixedEmbedder(Embedder):
    """Provide a small stable embedding shape without external model calls."""

    model = "placement-test"

    def __init__(self, dimensions: int = FAKE_EMBEDDING_DIMENSIONS) -> None:
        self._dimensions = dimensions

    async def dimensions(self) -> int:
        """Return the configured vector dimension."""
        return self._dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return deterministic vectors for all requested texts."""
        return [[1.0] + [0.0] * (self._dimensions - 1) for _ in texts]


class _NoopExtractor(Extractor):
    """Avoid external extraction dependencies when opening the graph."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return no extracted graph data."""
        return ExtractionResult(entities=[], relations=[], extractor_name="noop")


async def _clear_placement(graph_store: GraphStore) -> None:
    """Clear the singleton placement between isolated integration cases."""
    await graph_store.connect()
    await graph_store.execute_write("MATCH (node:VectorPlacement) DETACH DELETE node")
    await graph_store.close()


async def _open_graph(
    graph_store: GraphStore,
    embedder: Embedder,
    vector_store: FakeVectorStore | None,
) -> Graph:
    """Open a graph using deterministic dependencies and the selected store."""
    return await Graph.open(
        schema=DEFAULT_SCHEMA,
        graph_store=graph_store,
        embedder=embedder,
        vector_store=vector_store,
        extractor=_NoopExtractor(),
    )


class TestVectorPlacement:
    """Placement is created on first open and mismatches are rejected."""

    async def test_external_open_creates_collections_and_records_placement(
        self,
    ) -> None:
        """External open provisions every kind and persists its exact placement."""
        graph_store = build_test_store()
        await _clear_placement(graph_store)
        vector_store = FakeVectorStore(collection_prefix="placement")
        try:
            await _open_graph(graph_store, _FixedEmbedder(), vector_store)
            rows = await graph_store.execute_read(
                "MATCH (node:VectorPlacement) RETURN node.store AS store, "
                "node.collection_prefix AS collection_prefix, "
                "node.dimensions AS dimensions, node.distance AS distance"
            )
            assert rows == [
                {
                    "store": "fake",
                    "collection_prefix": "placement",
                    "dimensions": FAKE_EMBEDDING_DIMENSIONS,
                    "distance": Distance.COSINE.value,
                }
            ]
            for kind in VectorKind:
                info = await vector_store.collection_info(kind)
                assert info is not None
                assert info.dimensions == FAKE_EMBEDDING_DIMENSIONS
                assert info.distance == Distance.COSINE
        finally:
            await vector_store.close()
            await graph_store.close()
            await _clear_placement(graph_store)

    @pytest.mark.parametrize(
        ("new_store", "new_embedder"),
        [
            (FakeVectorStore(collection_prefix="other"), _FixedEmbedder()),
            (FakeVectorStore(collection_prefix="placement"), _FixedEmbedder(5)),
            (None, _FixedEmbedder()),
        ],
    )
    async def test_reopen_rejects_a_different_vector_placement(
        self, new_store: FakeVectorStore | None, new_embedder: Embedder
    ) -> None:
        """A different prefix, dimension, or graph-native mode cannot reopen it."""
        graph_store = build_test_store()
        await _clear_placement(graph_store)
        original_store = FakeVectorStore(collection_prefix="placement")
        try:
            await _open_graph(graph_store, _FixedEmbedder(), original_store)
            with pytest.raises(VectorPlacementError):
                await _open_graph(graph_store, new_embedder, new_store)
        finally:
            await original_store.close()
            if new_store is not None:
                await new_store.close()
            await graph_store.close()
            await _clear_placement(graph_store)

    async def test_graph_native_first_open_persists_native_placement(self) -> None:
        """A first graph-native open records the same immutable placement rule."""
        graph_store = build_test_store()
        await _clear_placement(graph_store)
        vector_store = FakeVectorStore(collection_prefix="later")
        try:
            await _open_graph(graph_store, _FixedEmbedder(), None)
            with pytest.raises(VectorPlacementError):
                await _open_graph(graph_store, _FixedEmbedder(), vector_store)
        finally:
            await vector_store.close()
            await graph_store.close()
            await _clear_placement(graph_store)
