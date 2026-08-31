"""Unit tests for the Milvus vector-store backend, with a mocked client."""

import asyncio
from types import SimpleNamespace
from unittest import mock
from uuid import UUID, uuid4

import pytest
from pymilvus.exceptions import MilvusException

from agrag.common.data_models.vector_record import Distance, VectorHit, VectorRecord
from agrag.vectordb.errors import (
    CollectionDimensionMismatchError,
    VectorStoreError,
    VectorStoreMissingExtraError,
)
from agrag.vectordb.milvus import (
    MAX_RESPONSE_LIMIT,
    MilvusVectorStore,
    _escape_list,
    _escape_scalar,
)
from agrag.vectordb.settings import MilvusSettings


_ALL_ADAPTER_FIELDS = ["id", "vector", "text", "sparse", "payload"]


def _describe_collection(dim: int = 4, *, fields: list[str] | None = None) -> dict:
    """Build a fake ``describe_collection`` response.

    Args:
        dim: The dense vector field's dimension.
        fields: The field names the collection carries. Defaults to this
            adapter's full required set (id, vector, text, sparse, payload),
            representing a collection this adapter can actually serve.
    """
    field_names = _ALL_ADAPTER_FIELDS if fields is None else fields
    return {
        "fields": [
            {"name": name, "params": {"dim": dim} if name == "vector" else {}}
            for name in field_names
        ]
    }


class MockMilvusClient:
    """A stand-in for AsyncMilvusClient that records calls and returns stubs."""

    def __init__(self) -> None:
        """Create the fake with async mocks for every used method."""
        self.list_collections = mock.AsyncMock(return_value=[])
        self.has_collection = mock.AsyncMock(return_value=False)
        self.describe_collection = mock.AsyncMock(return_value=_describe_collection())
        self.describe_index = mock.AsyncMock(return_value={"metric_type": "COSINE"})
        self.drop_collection = mock.AsyncMock()
        self.prepare_index_params = mock.MagicMock(
            return_value=SimpleNamespace(add_index=mock.MagicMock())
        )
        self.create_collection = mock.AsyncMock()
        self.load_collection = mock.AsyncMock()
        self.upsert = mock.AsyncMock()
        self.search = mock.AsyncMock(return_value=[[{"id": "x", "distance": 0.9}]])
        self.hybrid_search = mock.AsyncMock(
            return_value=[[{"id": "x", "distance": 0.8}]]
        )
        self.query = mock.AsyncMock(return_value=[])
        self.get = mock.AsyncMock(return_value=[])
        self.delete = mock.AsyncMock()
        self.flush = mock.AsyncMock()
        self.close = mock.AsyncMock()


@pytest.fixture
def client() -> MockMilvusClient:
    """A fresh fake Milvus client."""
    return MockMilvusClient()


@pytest.fixture
def store(client: MockMilvusClient) -> MilvusVectorStore:
    """A MilvusVectorStore backed by the fake client."""
    return MilvusVectorStore(settings=MilvusSettings(), client=client)


class TestEnsureCollection:
    """ensure_collection creates and is idempotent."""

    async def test_creates_when_absent(self, store: MilvusVectorStore, client) -> None:
        """A missing collection is created with both dense and sparse indices."""
        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        client.create_collection.assert_called_once()
        assert client.load_collection.call_args.args[0] == "c"
        index_calls = client.prepare_index_params.return_value.add_index.call_args_list
        indexed_fields = {c.kwargs["field_name"] for c in index_calls}
        assert "vector" in indexed_fields
        assert "sparse" in indexed_fields

    async def test_idempotent_when_present(
        self, store: MilvusVectorStore, client
    ) -> None:
        """An existing collection is not recreated."""
        client.has_collection.return_value = True
        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        client.create_collection.assert_not_called()
        client.load_collection.assert_not_called()

    async def test_dimension_mismatch_raises(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A dimension conflict on an existing collection raises."""
        client.has_collection.return_value = True
        client.describe_collection.return_value = _describe_collection(dim=8)
        with pytest.raises(CollectionDimensionMismatchError) as exc_info:
            await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        assert exc_info.value.expected == 8
        assert exc_info.value.actual == 4

    async def test_dimension_match_does_not_raise(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A matching dimension on an existing collection passes silently."""
        client.has_collection.return_value = True
        client.describe_collection.return_value = _describe_collection(dim=4)
        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        client.create_collection.assert_not_called()

    async def test_existing_dense_only_collection_raises(
        self, store: MilvusVectorStore, client
    ) -> None:
        """An existing collection with only id/vector fields is rejected.

        Regression guard: upsert and hybrid_search always read and write the
        text, sparse, and payload fields (Milvus has no per-call hybrid
        toggle), so a dense-only collection this adapter did not provision
        would fail at write or search time instead of at setup time.
        """
        client.has_collection.return_value = True
        client.describe_collection.return_value = _describe_collection(
            dim=4, fields=["id", "vector"]
        )
        with pytest.raises(VectorStoreError, match="missing fields"):
            await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)

    async def test_existing_collection_missing_sparse_index_raises(
        self, store: MilvusVectorStore, client
    ) -> None:
        """An existing collection with every field but no sparse index is rejected.

        Regression guard: hybrid_search issues an AnnSearchRequest against
        the sparse field's index; without that index the field exists but
        cannot actually be searched.
        """
        client.has_collection.return_value = True
        client.describe_collection.return_value = _describe_collection(dim=4)

        async def fake_describe_index(*, collection_name: str, index_name: str):
            if index_name == "sparse":
                raise MilvusException("index not found")
            return {"metric_type": "COSINE"}

        client.describe_index = mock.AsyncMock(side_effect=fake_describe_index)
        with pytest.raises(VectorStoreError, match="sparse index present: False"):
            await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)


class TestWritesAndReads:
    """upsert, search, hybrid_search, scroll, retrieve, count, delete."""

    async def test_upsert_inserts_rows(self, store: MilvusVectorStore, client) -> None:
        """Upsert writes each record with its vector, text, and payload JSON."""
        record = VectorRecord(
            id=uuid4(), vector=[0.1, 0.2], payload={"text": "a", "n": 1}
        )
        await store.upsert("c", [record])
        client.upsert.assert_called_once()
        row = client.upsert.call_args.kwargs["data"][0]
        assert row["id"] == str(record.id)
        assert row["vector"] == [0.1, 0.2]
        assert row["text"] == "a"
        assert row["payload"] == {"text": "a", "n": 1}

    async def test_upsert_rejects_non_positive_batch_size(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A zero or negative batch_size raises instead of silently misbehaving."""
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={})
        with pytest.raises(ValueError):
            await store.upsert("c", [record], batch_size=0)
        client.upsert.assert_not_called()

    async def test_upsert_overwrites_existing_id(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Upsert uses Milvus's upsert call, not insert, so a repeat id overwrites."""
        record_id = uuid4()
        first = VectorRecord(id=record_id, vector=[0.1], payload={"text": "old"})
        second = VectorRecord(id=record_id, vector=[0.2], payload={"text": "new"})
        await store.upsert("c", [first])
        await store.upsert("c", [second])
        assert client.upsert.call_count == 2
        last_row = client.upsert.call_args.kwargs["data"][0]
        assert last_row["payload"] == {"text": "new"}

    async def test_upsert_normalizes_non_json_native_values(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A UUID payload value is stringified before writing, as it was before."""
        payload_uuid = uuid4()
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={"ref": payload_uuid})
        await store.upsert("c", [record])
        row = client.upsert.call_args.kwargs["data"][0]
        assert row["payload"] == {"ref": str(payload_uuid)}

    async def test_search_returns_hits(self, store: MilvusVectorStore, client) -> None:
        """Search maps rows to VectorHit objects."""
        obj_id = str(uuid4())
        client.search.return_value = [
            [{"id": obj_id, "distance": 0.9, "payload": {"text": "a"}}]
        ]
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert len(hits) == 1
        assert isinstance(hits[0], VectorHit)
        assert hits[0].id == UUID(obj_id)
        assert hits[0].score == 0.9
        assert hits[0].payload == {"text": "a"}

    async def test_search_rejects_non_positive_limit(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A non-positive limit raises instead of reaching the backend."""
        with pytest.raises(ValueError, match="positive"):
            await store.search("c", [0.1, 0.2], limit=0)
        client.search.assert_not_called()

    async def test_hybrid_search_rejects_invalid_alpha(
        self, store: MilvusVectorStore, client
    ) -> None:
        """An out-of-range alpha raises instead of reaching the backend."""
        with pytest.raises(ValueError, match="0.0 and 1.0"):
            await store.hybrid_search("c", [0.1, 0.2], "q", alpha=-0.1)
        client.hybrid_search.assert_not_called()

    async def test_search_inverts_euclidean_distance(
        self, store: MilvusVectorStore, client
    ) -> None:
        """An L2 collection's raw distance is negated so higher is closer."""
        client.describe_index.return_value = {"metric_type": "L2"}
        obj_id = str(uuid4())
        client.search.return_value = [[{"id": obj_id, "distance": 0.5}]]
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert hits[0].score == pytest.approx(-0.5)

    async def test_search_keeps_cosine_distance_as_is(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A COSINE collection's distance field is already a similarity score."""
        client.describe_index.return_value = {"metric_type": "COSINE"}
        obj_id = str(uuid4())
        client.search.return_value = [[{"id": obj_id, "distance": 0.5}]]
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert hits[0].score == pytest.approx(0.5)

    async def test_search_uses_metric_cached_by_ensure_collection(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A metric known from creation is not re-fetched on search."""
        await store.ensure_collection("c", dimensions=4, distance=Distance.EUCLID)
        obj_id = str(uuid4())
        client.search.return_value = [[{"id": obj_id, "distance": 0.5}]]
        hits = await store.search("c", [0.1, 0.2], limit=5)
        client.describe_index.assert_not_called()
        assert hits[0].score == pytest.approx(-0.5)

    async def test_hybrid_search_passes_requests(
        self, store: MilvusVectorStore, client
    ) -> None:
        """hybrid_search forwards the dense and sparse requests to the backend."""
        obj_id = str(uuid4())
        client.hybrid_search.return_value = [
            [{"id": obj_id, "distance": 0.8, "payload": {}}]
        ]
        hits = await store.hybrid_search("c", [0.1, 0.2], "query text", alpha=0.3)
        assert len(hits) == 1
        assert hits[0].id == UUID(obj_id)
        reqs = client.hybrid_search.call_args.kwargs["reqs"]
        assert {r.anns_field for r in reqs} == {"vector", "sparse"}
        ranker = client.hybrid_search.call_args.kwargs["ranker"]
        assert ranker.dict()["params"]["weights"] == [0.3, 0.7]

    async def test_scroll_returns_records_and_offset(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Scroll returns the page and the next id cursor when the page is full."""
        obj_id = str(uuid4())
        client.query.return_value = [{"id": obj_id, "vector": [0.1], "payload": {}}]
        records, offset = await store.scroll("c", limit=1, with_vectors=True)
        assert len(records) == 1
        assert records[0].vector == [0.1]
        assert offset == obj_id

    async def test_scroll_never_sends_offset(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Scroll never sends a numeric offset, regardless of page depth.

        Regression guard: Milvus rejects a query whose offset + limit
        exceeds MAX_RESPONSE_LIMIT, so a numeric offset cannot page past
        that many total records without eventually erroring and leaving
        later records unread. The id cursor needs no offset at all.
        """
        obj_id = str(uuid4())
        client.query.return_value = [{"id": obj_id, "vector": [0.1], "payload": {}}]
        await store.scroll("c", limit=1, page_offset=str(uuid4()))
        assert "offset" not in client.query.call_args.kwargs

    async def test_scroll_filters_on_id_cursor(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A follow-up page filters on ``id > page_offset``, combined with filters."""
        cursor = str(uuid4())
        client.query.return_value = []
        await store.scroll("c", limit=10, page_offset=cursor, filters={"kind": "a"})
        expr = client.query.call_args.kwargs["filter"]
        assert f"id > {_escape_scalar(cursor)}" in expr
        assert 'payload["kind"] == "a"' in expr

    async def test_scroll_orders_by_id_ascending(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Scroll explicitly orders by id, not relying on unordered results.

        Regression guard: without an explicit order, an unordered query
        result could return rows out of id order. Advancing the cursor past
        this page's highest returned id would then permanently skip any
        lower, unmatched id that Milvus happened not to include in this
        batch.
        """
        client.query.return_value = []
        await store.scroll("c", limit=10)
        assert client.query.call_args.kwargs["order_by"] == "id:asc"

    async def test_scroll_next_offset_is_last_row_id_in_order(
        self, store: MilvusVectorStore, client
    ) -> None:
        """The next cursor is the last (highest) id in the ordered page."""
        ids = [str(uuid4()) for _ in range(2)]
        client.query.return_value = [
            {"id": i, "vector": [], "payload": {}} for i in ids
        ]
        _, offset = await store.scroll("c", limit=2)
        assert offset == ids[-1]

    async def test_scroll_zero_limit_returns_empty_page(
        self, store: MilvusVectorStore, client
    ) -> None:
        """limit=0 returns an empty page instead of crashing on an empty result.

        Regression guard: ``len(rows) == safe_limit`` was true for an empty
        result at ``limit=0``, so indexing ``rows[-1]`` raised ``IndexError``
        instead of signaling there is no next page.
        """
        client.query.return_value = []
        records, offset = await store.scroll("c", limit=0)
        assert records == []
        assert offset is None

    async def test_scroll_caps_response_limit(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Scroll caps the page size at MAX_RESPONSE_LIMIT."""
        big = MAX_RESPONSE_LIMIT + 10
        await store.scroll("c", limit=big)
        assert client.query.call_args.kwargs["limit"] == MAX_RESPONSE_LIMIT

    async def test_retrieve_preserves_order(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Retrieve returns records in the requested id order, omitting misses."""
        first, second = uuid4(), uuid4()
        client.get.return_value = [
            {"id": str(second), "vector": [0.1], "payload": {}},
            {"id": str(first), "vector": [0.2], "payload": {}},
        ]
        records = await store.retrieve("c", [first, second])
        assert [r.id for r in records] == [first, second]

    async def test_retrieve_batches_large_id_lists(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Retrieve chunks a large id list instead of sending it all in one call.

        Regression guard: a single request covering too many ids can exceed
        Milvus's cloud response cap; MAX_RESPONSE_LIMIT already documents
        that retrieve is meant to chunk the same way scroll does.
        """
        ids = [uuid4() for _ in range(MAX_RESPONSE_LIMIT + 5)]
        client.get.return_value = []
        await store.retrieve("c", ids)
        assert client.get.call_count == 2
        first_batch = client.get.call_args_list[0].kwargs["ids"]
        second_batch = client.get.call_args_list[1].kwargs["ids"]
        assert len(first_batch) == MAX_RESPONSE_LIMIT
        assert len(second_batch) == 5

    async def test_count_returns_total(self, store: MilvusVectorStore, client) -> None:
        """Count returns the backend total."""
        client.query.return_value = [{"count(*)": 3}]
        assert await store.count("c") == 3

    async def test_delete_forwards_ids(self, store: MilvusVectorStore, client) -> None:
        """Delete forwards the ids to the backend."""
        target_id = uuid4()
        await store.delete("c", [target_id])
        assert client.delete.call_args.kwargs["ids"] == [str(target_id)]

    async def test_delete_collection_clears_cached_metric(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Deleting a collection forgets its cached similarity metric.

        Otherwise a name reused with a different metric would apply the old
        score conversion to the new collection's results.
        """
        await store.ensure_collection("c", dimensions=4, distance=Distance.EUCLID)
        assert "c" in store._collection_metrics
        await store.delete_collection("c")
        assert "c" not in store._collection_metrics

    async def test_invalidate_collection_clears_cached_metric(
        self, store: MilvusVectorStore
    ) -> None:
        """invalidate_collection drops cached metric state without deleting data.

        This is the escape hatch for a collection recreated by something
        other than this store instance: without it, stale cached state from
        before the recreation would keep being trusted.
        """
        store._collection_metrics["c"] = "L2"
        store.invalidate_collection("c")
        assert "c" not in store._collection_metrics

    async def test_close_releases_client(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Close releases the client connection."""
        await store.close()
        client.close.assert_called_once()


class TestFilterEscaping:
    """The Milvus filter expression builder must resist injection."""

    def test_scalar_escapes_quotes(self) -> None:
        """A quote in a string value is escaped, not emitted raw."""
        assert _escape_scalar('a"b') == '"a\\"b"'

    def test_scalar_escapes_backslash(self) -> None:
        """A backslash in a string value is escaped."""
        assert _escape_scalar("a\\b") == '"a\\\\b"'

    def test_scalar_bool_lowercased(self) -> None:
        """A bool renders as Milvus's lower-case literal."""
        assert _escape_scalar(True) == "true"
        assert _escape_scalar(False) == "false"

    def test_list_builds_in_clause(self) -> None:
        """A list value builds a bracketed, escaped ``in`` clause body."""
        assert _escape_list(["a", "b"]) == '["a", "b"]'

    def test_compile_rejects_bad_field(self) -> None:
        """A filter key that is not an identifier raises ValueError."""
        store = MilvusVectorStore(settings=MilvusSettings())
        with pytest.raises(ValueError):
            store._compile_filter({"bad field; drop": "x"})

    def test_compile_neutralizes_operator_in_value(self) -> None:
        """An operator-looking value stays inside an escaped literal."""
        store = MilvusVectorStore(settings=MilvusSettings())
        expr = store._compile_filter({"kind": 'x" or 1==1'})
        assert expr == 'payload["kind"] == "x\\" or 1==1"'

    def test_compile_list_value(self) -> None:
        """A list value renders as an ``in`` clause."""
        store = MilvusVectorStore(settings=MilvusSettings())
        expr = store._compile_filter({"cat": ["a", "b"]})
        assert expr == 'payload["cat"] in ["a", "b"]'

    def test_compile_references_payload_json_field(self) -> None:
        """A scalar filter compiles against the payload JSON field, not a bare field."""
        store = MilvusVectorStore(settings=MilvusSettings())
        expr = store._compile_filter({"kind": "doc"})
        assert expr == 'payload["kind"] == "doc"'

    def test_compile_empty_is_blank(self) -> None:
        """An empty filter compiles to an empty expression."""
        store = MilvusVectorStore(settings=MilvusSettings())
        assert store._compile_filter(None) == ""
        assert store._compile_filter({}) == ""


class TestMissingExtra:
    """Without the extra installed, use raises, not ImportError."""

    async def test_initialize_raises_missing_extra(self) -> None:
        """Initialize without pymilvus raises VectorStoreMissingExtraError."""
        store = MilvusVectorStore()
        with (
            mock.patch.dict("sys.modules", {"pymilvus": None}),
            pytest.raises(VectorStoreMissingExtraError) as exc_info,
        ):
            await store.initialize()
        assert exc_info.value.extra == "milvus"


class TestEnsureClientConcurrency:
    """_ensure_client serializes concurrent first calls."""

    async def test_concurrent_first_calls_build_client_once(self) -> None:
        """Concurrent first calls build exactly one Milvus client, not one each."""
        build_calls = 0

        def mock_client_ctor(*args, **kwargs):
            nonlocal build_calls
            build_calls += 1
            return object()

        store = MilvusVectorStore(settings=MilvusSettings())
        with mock.patch("pymilvus.AsyncMilvusClient", side_effect=mock_client_ctor):
            first, second = await asyncio.gather(
                store._ensure_client(), store._ensure_client()
            )
        assert build_calls == 1
        assert first is second
