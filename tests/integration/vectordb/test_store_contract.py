"""The in-memory store satisfies the public external-vector contract."""

import json
import threading
from collections.abc import AsyncIterator, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.vector_record import Distance, VectorKind, VectorRecord
from agrag.vectordb.base import VectorStore
from agrag.vectordb.errors import CollectionMismatchError, VectorStoreError
from agrag.vectordb.qdrant import QdrantSettings, QdrantVectorStore
from tests.integration._fake_vector_store import FakeVectorStore
from tests.integration._vector_backend import build_vector_store, selected_vector_stores


@pytest.fixture(params=selected_vector_stores())
async def vector_store(request: pytest.FixtureRequest) -> AsyncIterator[VectorStore]:
    """Open an isolated collection namespace and remove it after the case."""
    store = build_vector_store(
        request.param, collection_prefix=f"contract_{uuid4().hex}"
    )
    await store.initialize()
    try:
        yield store
    finally:
        try:
            for kind in VectorKind:
                await store.delete_collection(kind)
        finally:
            await store.close()


def _record(
    vector: list[float],
    *,
    text: str = "",
    labels: list[str] | None = None,
    record_id: UUID | None = None,
) -> VectorRecord:
    """Build a record with caller-visible metadata."""
    return VectorRecord(
        id=record_id or uuid4(), vector=vector, labels=labels or ["Thing"], text=text
    )


class TestVectorStoreContract:
    """Exercise all storage, ranking, filtering, and missing-data guarantees."""

    async def test_collection_shape_is_fixed_after_creation(self, vector_store) -> None:
        """Collections are created once and reject dimension or metric changes."""
        await vector_store.ensure_collection(
            VectorKind.ENTITY, dimensions=2, distance=Distance.COSINE
        )
        info = await vector_store.collection_info(VectorKind.ENTITY)
        assert info is not None
        assert (info.dimensions, info.distance, info.count) == (2, Distance.COSINE, 0)
        shape = await vector_store.collection_info(VectorKind.ENTITY, exact_count=False)
        assert shape is not None
        assert (shape.dimensions, shape.distance) == (2, Distance.COSINE)

        with pytest.raises(CollectionMismatchError):
            await vector_store.ensure_collection(
                VectorKind.ENTITY, dimensions=3, distance=Distance.COSINE
            )
        with pytest.raises(CollectionMismatchError):
            await vector_store.ensure_collection(
                VectorKind.ENTITY, dimensions=2, distance=Distance.EUCLID
            )
        with pytest.raises(ValueError, match="DOT"):
            await vector_store.ensure_collection(
                VectorKind.CHUNK, dimensions=2, distance=Distance.DOT
            )

    @pytest.mark.parametrize(
        ("distance", "vectors", "expected"),
        [
            (
                Distance.COSINE,
                [[1.0, 0.0], [0.7, 0.7], [0.0, 1.0], [-1.0, 0.0]],
                [1.0, 0.854, 0.5, 0.0],
            ),
            (
                Distance.EUCLID,
                [[0.0, 0.0], [1.0, 0.0], [0.0, 2.0], [2.0, 2.0]],
                [1.0, 0.5, 0.2, 0.111111],
            ),
        ],
    )
    async def test_dense_scores_use_the_graph_native_scale(
        self, vector_store, distance, vectors, expected
    ) -> None:
        """Cosine and Euclidean scores use the same scale as graph-native search."""
        await vector_store.ensure_collection(
            VectorKind.ENTITY, dimensions=2, distance=distance
        )
        await vector_store.upsert(
            VectorKind.ENTITY,
            [
                _record(vector, record_id=UUID(int=index + 1))
                for index, vector in enumerate(vectors)
            ],
        )

        hits = await vector_store.search(
            VectorKind.ENTITY, vectors[0], limit=len(vectors)
        )

        assert [hit.score for hit in hits] == pytest.approx(expected, abs=0.0005)
        assert [hit.id for hit in hits] == [UUID(int=index) for index in range(1, 5)]

    async def test_hybrid_endpoints_match_dense_and_lexical_order(
        self, vector_store
    ) -> None:
        """Alpha endpoints preserve dense and lexical ranking order exactly."""
        await vector_store.ensure_collection(
            VectorKind.ENTITY, dimensions=2, distance=Distance.COSINE
        )
        records = [
            _record([1.0, 0.0], text="pear apple", record_id=UUID(int=1)),
            _record([0.8, 0.6], text="apple pear", record_id=UUID(int=2)),
            _record([0.0, 1.0], text="pear pear apple", record_id=UUID(int=3)),
            _record([-1.0, 0.0], text="plum", record_id=UUID(int=4)),
        ]
        await vector_store.upsert(VectorKind.ENTITY, records)
        dense = await vector_store.search(VectorKind.ENTITY, [1.0, 0.0], limit=4)
        dense_hybrid = await vector_store.hybrid_search(
            VectorKind.ENTITY, [1.0, 0.0], "pear apple", limit=4, alpha=1.0
        )
        lexical_hybrid = await vector_store.hybrid_search(
            VectorKind.ENTITY, [1.0, 0.0], "pear apple", limit=4, alpha=0.0
        )
        mixed_hybrid = await vector_store.hybrid_search(
            VectorKind.ENTITY, [1.0, 0.0], "pear apple", limit=4, alpha=0.5
        )

        assert [hit.id for hit in dense_hybrid] == [hit.id for hit in dense]
        assert lexical_hybrid[0].id == UUID(int=3)
        assert len(lexical_hybrid) == 3
        assert {hit.id for hit in lexical_hybrid[1:]} == {UUID(int=1), UUID(int=2)}
        assert (
            await vector_store.hybrid_search(
                VectorKind.ENTITY, [1.0, 0.0], "mango", limit=4, alpha=0.0
            )
            == []
        )
        assert [hit.score for hit in mixed_hybrid] == sorted(
            (hit.score for hit in mixed_hybrid), reverse=True
        )

    async def test_search_filters_any_matching_label_and_respects_the_limit(
        self, vector_store
    ) -> None:
        """Search returns sorted, capped hits whose labels overlap the filter."""
        await vector_store.ensure_collection(
            VectorKind.ENTITY, dimensions=2, distance=Distance.COSINE
        )
        records = [
            _record([1.0, 0.0], labels=["Person", "Entity"], record_id=UUID(int=1)),
            _record([0.9, 0.1], labels=["Company"], record_id=UUID(int=2)),
            _record([0.0, 1.0], labels=["Organization"], record_id=UUID(int=3)),
        ]
        await vector_store.upsert(VectorKind.ENTITY, records)

        hits = await vector_store.search(
            VectorKind.ENTITY,
            [1.0, 0.0],
            limit=3,
            labels=["Person", "Organization"],
        )
        assert len(hits) == 2
        assert hits[0].id == UUID(int=1)
        assert hits[0].payload == {"labels": ["Person", "Entity"]}
        capped_hits = await vector_store.search(
            VectorKind.ENTITY,
            [1.0, 0.0],
            limit=1,
            labels=["Person", "Organization"],
        )
        assert [hit.id for hit in capped_hits] == [UUID(int=1)]
        capped_hybrid = await vector_store.hybrid_search(
            VectorKind.ENTITY,
            [1.0, 0.0],
            "person",
            limit=1,
            alpha=1.0,
            labels=["Person", "Organization"],
        )
        assert [hit.id for hit in capped_hybrid] == [UUID(int=1)]
        hybrid_hits = await vector_store.hybrid_search(
            VectorKind.ENTITY,
            [1.0, 0.0],
            "person",
            limit=3,
            alpha=0.5,
            labels=["Organization"],
        )
        assert [hit.id for hit in hybrid_hits] == [UUID(int=3)]
        with pytest.raises(ValueError, match="limit"):
            await vector_store.search(
                VectorKind.ENTITY, [1.0, 0.0], limit=vector_store.max_results + 1
            )
        with pytest.raises(ValueError, match="limit"):
            await vector_store.hybrid_search(
                VectorKind.ENTITY,
                [1.0, 0.0],
                "person",
                limit=vector_store.max_results + 1,
                alpha=0.5,
            )

    async def test_upsert_delete_and_keyset_pages_are_immediately_visible(
        self, vector_store
    ) -> None:
        """Writes overwrite by id and id pages advance with an exclusive cursor."""
        await vector_store.ensure_collection(
            VectorKind.CHUNK, dimensions=2, distance=Distance.COSINE
        )
        first = _record([1.0, 0.0], text="old", record_id=UUID(int=1))
        second = _record([0.0, 1.0], record_id=UUID(int=2))
        replacement = first.model_copy(update={"text": "new", "vector": [0.6, 0.8]})
        await vector_store.upsert(VectorKind.CHUNK, [first, second])
        await vector_store.upsert(VectorKind.CHUNK, [replacement])

        assert await vector_store.list_ids(VectorKind.CHUNK, limit=1) == [first.id]
        assert await vector_store.list_ids(VectorKind.CHUNK, limit=0) == []
        assert await vector_store.list_ids(
            VectorKind.CHUNK, limit=vector_store.max_results + 1
        ) == [first.id, second.id]
        with pytest.raises(ValueError, match="limit"):
            await vector_store.list_ids(VectorKind.CHUNK, limit=-1)
        assert await vector_store.list_ids(VectorKind.CHUNK, after=first.id) == [
            second.id
        ]
        info = await vector_store.collection_info(VectorKind.CHUNK)
        assert info is not None
        assert info.count == 2
        dense_hits = await vector_store.search(VectorKind.CHUNK, [0.0, 1.0], limit=2)
        assert [hit.id for hit in dense_hits] == [second.id, first.id]
        await vector_store.delete(VectorKind.CHUNK, [UUID(int=99)])
        await vector_store.delete(VectorKind.CHUNK, [first.id])
        assert await vector_store.list_ids(VectorKind.CHUNK) == [second.id]
        await vector_store.delete_collection(VectorKind.CHUNK)
        assert await vector_store.collection_info(VectorKind.CHUNK) is None

    async def test_missing_collection_reads_and_deletes_are_empty(
        self, vector_store
    ) -> None:
        """Absent collections are empty for reads and deletes but reject writes."""
        assert await vector_store.collection_info(VectorKind.CHUNK) is None
        assert await vector_store.search(VectorKind.CHUNK, [1.0], limit=1) == []
        assert (
            await vector_store.hybrid_search(
                VectorKind.CHUNK, [1.0], "text", limit=1, alpha=0.5
            )
            == []
        )
        assert await vector_store.list_ids(VectorKind.CHUNK) == []
        await vector_store.delete(VectorKind.CHUNK, [uuid4()])
        with pytest.raises(VectorStoreError):
            await vector_store.upsert(VectorKind.CHUNK, [_record([1.0])])

    async def test_fault_hooks_fail_once_without_hiding_later_operations(
        self,
    ) -> None:
        """Injected write and delete failures are one-shot and leave usable state."""
        vector_store = FakeVectorStore()
        await vector_store.ensure_collection(
            VectorKind.CHUNK, dimensions=2, distance=Distance.COSINE
        )
        record = _record([1.0, 0.0])
        vector_store.fail_next_upsert = True
        with pytest.raises(VectorStoreError, match="injected upsert"):
            await vector_store.upsert(VectorKind.CHUNK, [record])
        await vector_store.upsert(VectorKind.CHUNK, [record])
        vector_store.fail_next_delete = True
        with pytest.raises(VectorStoreError, match="injected delete"):
            await vector_store.delete(VectorKind.CHUNK, [record.id])
        await vector_store.delete(VectorKind.CHUNK, [record.id])
        assert await vector_store.list_ids(VectorKind.CHUNK) == []


class _MisroutedProxy(BaseHTTPRequestHandler):
    """Answer the reachability check but return 404 for every other route."""

    def do_GET(self) -> None:  # noqa: N802
        """Serve an empty collection list and reject all other paths."""
        found = self.path.rstrip("/") == "/collections"
        body = json.dumps({"result": {"collections": []}, "status": "ok"})
        self.send_response(200 if found else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode() if found else b"not found")

    do_POST = do_PUT = do_DELETE = do_GET  # noqa: N815

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Keep test output quiet."""


@pytest.fixture
def misrouted_url() -> Iterator[str]:
    """Serve a stand-in for a proxy that forwards to the wrong place."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MisroutedProxy)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.skipif(
    "qdrant" not in selected_vector_stores(), reason="Qdrant is not selected"
)
class TestQdrantMissingCollection:
    """A 404 means an absent collection only when the server confirms it."""

    async def test_unconfirmed_not_found_is_an_error_not_an_empty_result(
        self, misrouted_url: str
    ) -> None:
        """A 404 from the wrong route fails instead of reading as no data."""
        store = QdrantVectorStore(
            settings=QdrantSettings(url=misrouted_url, collection_prefix="misrouted")
        )
        async with store:
            with pytest.raises(VectorStoreError, match="HTTP 404"):
                await store.search(VectorKind.CHUNK, [1.0], limit=1)
            with pytest.raises(VectorStoreError, match="HTTP 404"):
                await store.list_ids(VectorKind.CHUNK)
