"""Milvus dense and native BM25 indexes for external vector placement."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urlparse
from uuid import UUID
from weakref import WeakKeyDictionary

from opentelemetry.trace import SpanKind, Tracer, get_tracer
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from agrag.common.data_models.vector_record import (
    CollectionInfo,
    Distance,
    VectorHit,
    VectorKind,
    VectorRecord,
)
from agrag.common.validation import (
    require_encrypted_remote_connection,
    require_positive_batch_size,
)
from agrag.vectordb.base import VectorStore
from agrag.vectordb.errors import (
    CollectionMismatchError,
    VectorStoreError,
    VectorStoreMissingExtraError,
)
from agrag.vectordb.settings import CollectionPrefix


if TYPE_CHECKING:
    from pymilvus import AsyncMilvusClient

_logger = logging.getLogger(__name__)
_METRICS = {Distance.COSINE: "COSINE", Distance.EUCLID: "L2"}
_creation_locks: WeakKeyDictionary[
    asyncio.AbstractEventLoop, dict[tuple[str, str], asyncio.Lock]
] = WeakKeyDictionary()


def _labels_filter(labels: Sequence[str] | None) -> str:
    """Encode any-of labels as literals rather than executable filter fragments."""
    if labels is None:
        return ""
    if not labels:
        return "id in []"
    return f"array_contains_any(labels, {json.dumps(list(labels), ensure_ascii=False)})"


class MilvusSettings(BaseSettings):
    """Milvus or Zilliz Cloud connection and collection namespace.

    Attributes:
        uri: HTTP(S) endpoint. Env: ``MILVUS_URI``.
        token: Optional authentication token. Env: ``MILVUS_TOKEN``.
        require_tls: Require TLS for non-local endpoints, even without a token.
            Env: ``MILVUS_REQUIRE_TLS``.
        collection_prefix: Required namespace unique to one graph, starting with
            a letter and containing at most 41 letters, digits or underscores.
            Env: ``MILVUS_COLLECTION_PREFIX``.

    Searches allow up to 16384 results. Zilliz gateways can impose an approximately
    4 MB response cap; use smaller limits if that cap is reached. Milvus Lite and
    embedded endpoints are unsupported.
    """

    model_config = SettingsConfigDict(
        env_prefix="MILVUS_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    uri: str = "http://localhost:19530"
    token: SecretStr | None = None
    require_tls: bool = False
    collection_prefix: CollectionPrefix

    @model_validator(mode="after")
    def _validate_connection(self) -> MilvusSettings:
        """Require a remote-server URI and protect remote credentials with TLS."""
        parsed = urlparse(self.uri)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("MILVUS_URI must be an http:// or https:// server URI")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Use MILVUS_TOKEN rather than credentials in MILVUS_URI")
        require_encrypted_remote_connection(
            url=self.uri,
            has_credential=bool(self.token and self.token.get_secret_value()),
            encrypted_schemes=frozenset({"https"}),
            require_encryption=self.require_tls,
        )
        return self


class MilvusVectorStore(VectorStore):
    """Store UUID-keyed vectors with server-generated BM25 sparse vectors.

    Dense scores match graph-native cosine and Euclidean scores. Hybrid scores
    use Milvus's normalized weighted ranking; alpha endpoints use a single search
    path so a zero-weight path cannot add hits. All reads use Strong consistency.
    """

    name: ClassVar[str] = "milvus"
    max_results: int = 16384

    def __init__(
        self, settings: MilvusSettings | None = None, *, tracer: Tracer | None = None
    ) -> None:
        """Configure settings and operation tracing without connecting the SDK."""
        self.settings = settings if settings is not None else MilvusSettings()
        self.collection_prefix = self.settings.collection_prefix
        self._tracer = tracer if tracer is not None else get_tracer(__name__)
        self._client: AsyncMilvusClient | None = None
        self._connect_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Connect and authenticate, reporting failures without credential values."""
        async with self._connect_lock:
            if self._client is not None:
                return
            try:
                from pymilvus import AsyncMilvusClient  # noqa: PLC0415
            except ImportError:
                raise VectorStoreMissingExtraError("milvus") from None
            client = None
            try:
                client = AsyncMilvusClient(
                    uri=self.settings.uri,
                    token=(
                        self.settings.token.get_secret_value()
                        if self.settings.token
                        else ""
                    ),
                    consistency_level="Strong",
                )
                await client.list_collections()
            except Exception:
                if client is not None:
                    await client.close()
                raise VectorStoreError(
                    "Milvus connection or authentication failed"
                ) from None
            self._client = client

    async def close(self) -> None:
        """Release the connection; a later initialize reconnects."""
        async with self._connect_lock:
            if self._client is not None:
                client, self._client = self._client, None
                await client.close()

    async def ensure_collection(
        self, kind: VectorKind, *, dimensions: int, distance: Distance
    ) -> None:
        """Create and load a collection, or reject dimension and metric mismatches."""
        if distance not in _METRICS:
            raise ValueError("Milvus supports COSINE and EUCLID, not DOT")
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        await self.initialize()
        from pymilvus import DataType, Function, FunctionType  # noqa: PLC0415

        name = self.collection_name(kind)
        locks = _creation_locks.setdefault(asyncio.get_running_loop(), {})
        async with (
            locks.setdefault((self.settings.uri, name), asyncio.Lock()),
            self._connection("ensure_collection", kind) as client,
        ):
            if not await client.has_collection(name):
                schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
                schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
                schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dimensions)
                schema.add_field(
                    "labels",
                    DataType.ARRAY,
                    element_type=DataType.VARCHAR,
                    max_capacity=4096,
                    max_length=256,
                )
                schema.add_field(
                    "text", DataType.VARCHAR, max_length=65535, enable_analyzer=True
                )
                schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
                schema.add_function(
                    Function(
                        name="bm25",
                        function_type=FunctionType.BM25,
                        input_field_names=["text"],
                        output_field_names=["sparse"],
                    )
                )
                indexes = client.prepare_index_params()
                indexes.add_index(
                    field_name="vector",
                    index_name="dense",
                    index_type="AUTOINDEX",
                    metric_type=_METRICS[distance],
                )
                indexes.add_index(
                    field_name="sparse",
                    index_name="bm25",
                    index_type="SPARSE_INVERTED_INDEX",
                    metric_type="BM25",
                )
                from pymilvus import MilvusException  # noqa: PLC0415

                try:
                    await client.create_collection(
                        name,
                        schema=schema,
                        index_params=indexes,
                        consistency_level="Strong",
                    )
                except MilvusException:
                    if not await client.has_collection(name):
                        raise
            actual_dimensions, actual_distance = await self._metadata(client, name)
            if (actual_dimensions, actual_distance) != (dimensions, distance):
                raise CollectionMismatchError(
                    f"Milvus collection {name!r} has "
                    f"dimensions={actual_dimensions}, distance={actual_distance}; "
                    f"requested dimensions={dimensions}, distance={distance}"
                )
            await client.load_collection(name)

    async def collection_info(self, kind: VectorKind) -> CollectionInfo | None:
        """Return schema metadata and a Strong count, including unflushed writes."""
        async with self._connection("collection_info", kind) as client:
            name = self.collection_name(kind)
            if not await client.has_collection(name):
                return None
            dimensions, distance = await self._metadata(client, name)
            await client.load_collection(name)
            rows = await client.query(
                name, output_fields=["count(*)"], consistency_level="Strong"
            )
            return CollectionInfo(
                dimensions=dimensions, distance=distance, count=int(rows[0]["count(*)"])
            )

    async def delete_collection(self, kind: VectorKind) -> None:
        """Drop a collection if it exists."""
        async with self._connection("delete_collection", kind) as client:
            name = self.collection_name(kind)
            if await client.has_collection(name):
                await client.drop_collection(name)

    async def upsert(
        self,
        kind: VectorKind,
        records: Sequence[VectorRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Overwrite records by UUID, truncating only stored BM25 text to 65535 bytes.

        UTF-8 truncation preserves whole characters. The input records and dense
        vectors remain unchanged. A warning is emitted once per truncated call.
        """
        require_positive_batch_size(batch_size)
        truncated = False
        async with self._connection("upsert", kind) as client:
            name = self.collection_name(kind)
            if not await client.has_collection(name):
                raise VectorStoreError(f"Milvus collection {name!r} does not exist")
            for offset in range(0, len(records), batch_size):
                rows = []
                for record in records[offset : offset + batch_size]:
                    encoded = record.text.encode("utf-8")
                    truncated |= len(encoded) > 65535
                    rows.append(
                        {
                            "id": str(record.id),
                            "vector": record.vector,
                            "labels": record.labels,
                            "text": encoded[:65535].decode("utf-8", errors="ignore"),
                        }
                    )
                await client.upsert(name, data=rows)
        if truncated:
            _logger.warning("Milvus BM25 text truncated to 65535 UTF-8 bytes")

    async def search(
        self,
        kind: VectorKind,
        vector: Sequence[float],
        *,
        limit: int,
        labels: Sequence[str] | None = None,
    ) -> list[VectorHit]:
        """Return dense hits with graph-native scores, best first."""
        self._validate_limit(limit)
        if labels is not None and not labels:
            return []
        async with self._connection("search", kind) as client:
            name = self.collection_name(kind)
            if not await client.has_collection(name):
                return []
            _, distance = await self._metadata(client, name)
            results = await client.search(
                name,
                data=[list(vector)],
                anns_field="vector",
                limit=limit,
                filter=_labels_filter(labels),
                output_fields=["labels"],
                search_params={"metric_type": _METRICS[distance]},
                consistency_level="Strong",
            )
            return [
                VectorHit(
                    id=UUID(hit["id"]),
                    score=(
                        (1 + float(hit["distance"])) / 2
                        if distance == Distance.COSINE
                        else 1 / (1 + float(hit["distance"]))
                    ),
                    payload={"labels": hit["entity"]["labels"]},
                )
                for hit in results[0]
            ]

    async def hybrid_search(
        self,
        kind: VectorKind,
        vector: Sequence[float],
        text: str,
        *,
        limit: int,
        alpha: float,
        labels: Sequence[str] | None = None,
    ) -> list[VectorHit]:
        """Fuse normalized dense and BM25 scores; endpoints select one path only."""
        self._validate_limit(limit)
        if not 0 <= alpha <= 1:
            raise ValueError("alpha must be between zero and one")
        if alpha == 1:
            return await self.search(kind, vector, limit=limit, labels=labels)
        if labels is not None and not labels:
            return []
        async with self._connection("hybrid_search", kind) as client:
            name = self.collection_name(kind)
            if not await client.has_collection(name):
                return []
            if alpha == 0:
                results = await client.search(
                    name,
                    data=[text],
                    anns_field="sparse",
                    limit=limit,
                    filter=_labels_filter(labels),
                    output_fields=["labels"],
                    search_params={"metric_type": "BM25"},
                    consistency_level="Strong",
                )
            else:
                from pymilvus import AnnSearchRequest, WeightedRanker  # noqa: PLC0415

                _, distance = await self._metadata(client, name)
                requests = [
                    AnnSearchRequest(
                        data=[list(vector)],
                        anns_field="vector",
                        param={"metric_type": _METRICS[distance]},
                        limit=limit,
                        expr=_labels_filter(labels),
                    ),
                    AnnSearchRequest(
                        data=[text],
                        anns_field="sparse",
                        param={"metric_type": "BM25"},
                        limit=limit,
                        expr=_labels_filter(labels),
                    ),
                ]
                results = await client.hybrid_search(
                    name,
                    reqs=requests,
                    ranker=WeightedRanker(alpha, 1 - alpha),
                    limit=limit,
                    output_fields=["labels"],
                    consistency_level="Strong",
                )
            return [
                VectorHit(
                    id=UUID(hit["id"]),
                    score=float(hit["distance"]),
                    payload={"labels": hit["entity"]["labels"]},
                )
                for hit in results[0]
            ]

    async def delete(self, kind: VectorKind, ids: Sequence[UUID]) -> None:
        """Delete in batches, ignoring absent IDs and collections."""
        if not ids:
            return
        async with self._connection("delete", kind) as client:
            name = self.collection_name(kind)
            if not await client.has_collection(name):
                return
            for offset in range(0, len(ids), 256):
                await client.delete(
                    name,
                    ids=[str(record_id) for record_id in ids[offset : offset + 256]],
                )

    async def list_ids(
        self, kind: VectorKind, *, after: UUID | None = None, limit: int = 1000
    ) -> list[UUID]:
        """Page UUIDs in ascending order with an exclusive keyset cursor.

        Milvus 3.0 sorting orders the canonical VARCHAR UUIDs lexicographically,
        which is also UUID numeric order. Pages do not form a concurrent snapshot.
        """
        self._validate_limit(limit)
        async with self._connection("list_ids", kind) as client:
            name = self.collection_name(kind)
            if not await client.has_collection(name):
                return []
            rows = await client.query(
                name,
                filter=f'id > "{after}"' if after is not None else "",
                output_fields=["id"],
                limit=limit,
                order_by=["id:asc"],
                consistency_level="Strong",
            )
            return [UUID(row["id"]) for row in rows]

    @asynccontextmanager
    async def _connection(
        self, operation: str, kind: VectorKind
    ) -> AsyncIterator[AsyncMilvusClient]:
        """Trace operations and translate SDK errors without credential values."""
        await self.initialize()
        from pymilvus import MilvusException  # noqa: PLC0415

        client = self._client
        if client is None:
            raise VectorStoreError("Milvus client is closed")
        with self._tracer.start_as_current_span(
            f"agrag.vectordb.{operation}",
            kind=SpanKind.CLIENT,
            attributes={
                "db.system.name": "milvus",
                "db.collection.name": self.collection_name(kind),
            },
            record_exception=False,
        ):
            try:
                yield client
            except MilvusException:
                raise VectorStoreError(f"Milvus {operation} failed") from None

    async def _metadata(
        self, client: AsyncMilvusClient, name: str
    ) -> tuple[int, Distance]:
        """Read dimensions and distance from the schema and dense index."""
        schema = await client.describe_collection(name)
        field = next(
            (field for field in schema["fields"] if field["name"] == "vector"), None
        )
        if field is None:
            raise CollectionMismatchError(
                f"Milvus collection {name!r} has no vector field"
            )
        index = await client.describe_index(name, index_name="dense")
        metric = index.get("metric_type")
        if metric not in {"COSINE", "L2"}:
            raise CollectionMismatchError(
                f"Milvus collection {name!r} has unsupported metric"
            )
        return int(field["params"]["dim"]), (
            Distance.COSINE if metric == "COSINE" else Distance.EUCLID
        )

    def _validate_limit(self, limit: int) -> None:
        """Reject unusable result counts before contacting the server."""
        if not 1 <= limit <= self.max_results:
            raise ValueError(f"limit must be between 1 and {self.max_results}")
