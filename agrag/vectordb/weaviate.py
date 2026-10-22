"""Weaviate collections with self-provided vectors and native BM25 fusion."""

import asyncio
import contextlib
import heapq
import json
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, ClassVar, Literal
from urllib.parse import urlparse
from uuid import UUID

from opentelemetry import trace
from opentelemetry.trace import Tracer
from pydantic import Field, SecretStr, model_validator
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
    from weaviate import WeaviateAsyncClient


_METRICS = {Distance.COSINE: "cosine", Distance.EUCLID: "l2-squared"}
_COLLECTION_LOCKS: dict[tuple[str, str], asyncio.Lock] = {}
_DESCRIPTION_PREFIX = "agrag-vector-v1:"


class WeaviateSettings(BaseSettings):
    """Weaviate connection and collection isolation settings.

    Attributes:
        mode: Explicit cloud or custom deployment selection.
        url: HTTP endpoint, including scheme and optional port.
        api_key: Optional API key, hidden in representations and errors.
        grpc_port: Custom deployment gRPC port. Cloud uses TLS on port 443.
        require_tls: Require encryption for non-loopback custom deployments.
        collection_prefix: Required graph-specific prefix. Its first letter
            must be lowercase to prevent first-letter normalization collisions.

    Environment variables use the ``WEAVIATE_`` prefix. Both HTTP and gRPC
    must be reachable. Remote credentials require TLS on both transports.
    """

    model_config = SettingsConfigDict(
        env_prefix="WEAVIATE_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    mode: Literal["cloud", "custom"] = "custom"
    url: str = "http://localhost:8080"
    api_key: SecretStr | None = None
    grpc_port: int = Field(default=50051, ge=1, le=65535)
    require_tls: bool = False
    collection_prefix: CollectionPrefix

    @model_validator(mode="after")
    def _validate_connection(self) -> "WeaviateSettings":
        """Reject unsafe transports, embedded credentials and aliased prefixes."""
        parsed = urlparse(self.url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "url must be an HTTP(S) endpoint without credentials or path"
            )
        if self.mode == "cloud" and parsed.scheme != "https":
            raise ValueError("cloud mode requires HTTPS")
        if not self.collection_prefix[0].islower():
            raise ValueError("collection_prefix must start with a lowercase letter")
        require_encrypted_remote_connection(
            url=self.url,
            has_credential=self.api_key is not None,
            encrypted_schemes={"https"},
            require_encryption=self.require_tls,
        )
        return self


class WeaviateVectorStore(VectorStore):
    """An exclusive external index backed by Weaviate.

    Collections persist dimensions in their description, including when empty.
    Changing that description outside this adapter invalidates the collection.
    Dense scores use the graph-native scale. Hybrid scores are rank-only.
    Server-side asynchronous indexing must be disabled for read-after-write
    consistency. Each collection belongs to exactly one graph.
    """

    name: ClassVar[str] = "weaviate"
    max_results: int = 10000

    def __init__(
        self,
        *,
        settings: WeaviateSettings | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        """Bind connection settings without importing the optional client."""
        self._settings = settings if settings is not None else WeaviateSettings()
        self.collection_prefix = self._settings.collection_prefix
        self._tracer = tracer if tracer is not None else trace.get_tracer(__name__)
        self._client: WeaviateAsyncClient | None = None
        self._connect_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Connect and verify readiness, raising VectorStoreError on failure."""
        await self._connected_client()

    async def close(self) -> None:
        """Close connections; repeated calls are harmless."""
        async with self._connect_lock:
            if self._client is not None:
                client, self._client = self._client, None
                async with self._operation("close"):
                    await client.close()

    def collection_name(self, kind: VectorKind) -> str:
        """Capitalize only the first letter of the prefixed collection name."""
        name = super().collection_name(kind)
        return name[0].upper() + name[1:]

    async def ensure_collection(
        self,
        kind: VectorKind,
        *,
        dimensions: int,
        distance: Distance,
    ) -> None:
        """Create a collection or reject incompatible dimensions and metric.

        An existing collection without adapter-owned dimension metadata is
        rejected rather than silently adopted. DOT raises ValueError.
        """
        if distance not in _METRICS:
            raise ValueError("Weaviate supports cosine and euclidean distance only")
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        client = await self._connected_client()
        from weaviate.classes.config import (  # noqa: PLC0415
            Configure,
            DataType,
            Property,
            Tokenization,
            VectorDistances,
        )

        name = self.collection_name(kind)
        lock = _COLLECTION_LOCKS.setdefault((self._settings.url, name), asyncio.Lock())
        async with lock, self._operation("ensure_collection"):
            if not await client.collections.exists(name):
                description = _DESCRIPTION_PREFIX + json.dumps(
                    {
                        "dimensions": dimensions,
                        "prefix": self.collection_prefix,
                    }
                )
                await client.collections.create(
                    name=name,
                    description=description,
                    vector_config=Configure.Vectors.self_provided(
                        name="vector",
                        vector_index_config=Configure.VectorIndex.hnsw(
                            distance_metric=VectorDistances(_METRICS[distance]),
                        ),
                    ),
                    properties=[
                        Property(
                            name="labels",
                            data_type=DataType.TEXT_ARRAY,
                            tokenization=Tokenization.FIELD,
                            index_searchable=False,
                        ),
                        Property(name="text", data_type=DataType.TEXT),
                    ],
                )
            info = await self.collection_info(kind)
            if info is None or (info.dimensions, info.distance) != (
                dimensions,
                distance,
            ):
                raise CollectionMismatchError(
                    f"{name} does not match dimensions={dimensions}, "
                    f"distance={distance}"
                )

    async def collection_info(self, kind: VectorKind) -> CollectionInfo | None:
        """Return persisted dimensions, actual metric and count, or None if absent."""
        client = await self._connected_client()
        name = self.collection_name(kind)
        async with self._operation("collection_info"):
            if not await client.collections.exists(name):
                return None
            collection = client.collections.use(name)
            config = await collection.config.get()
            description = config.description or ""
            if not description.startswith(_DESCRIPTION_PREFIX):
                raise CollectionMismatchError(f"{name} lacks dimension metadata")
            try:
                metadata = json.loads(description[len(_DESCRIPTION_PREFIX) :])
                dimensions = metadata["dimensions"]
                if (
                    type(dimensions) is not int
                    or dimensions <= 0
                    or metadata["prefix"] != self.collection_prefix
                ):
                    raise ValueError("invalid collection metadata")
                if config.vector_config is None:
                    raise ValueError("missing named vector configuration")
                vector_config = config.vector_config["vector"]
                index_config = vector_config.vector_index_config
                if not hasattr(index_config, "distance_metric"):
                    raise ValueError("missing vector distance metric")
                metric = index_config.distance_metric
                distance = next(
                    key for key, value in _METRICS.items() if value == metric
                )
            except (ValueError, TypeError, KeyError, StopIteration) as exc:
                raise CollectionMismatchError(
                    f"{name} has incompatible metadata"
                ) from exc
            sample = await collection.query.fetch_objects(limit=1, include_vector=True)
            if sample.objects:
                vector = sample.objects[0].vector.get("vector")
                if vector is None or len(vector) != dimensions:
                    raise CollectionMismatchError(f"{name} vector dimension mismatch")
            count = await collection.aggregate.over_all(total_count=True)
            return CollectionInfo(
                dimensions=dimensions,
                distance=distance,
                count=count.total_count,
            )

    async def delete_collection(self, kind: VectorKind) -> None:
        """Delete a collection, ignoring one that does not exist."""
        client = await self._connected_client()
        async with self._operation("delete_collection"):
            name = self.collection_name(kind)
            if await client.collections.exists(name):
                await client.collections.delete(name)

    async def upsert(
        self,
        kind: VectorKind,
        records: Sequence[VectorRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Insert or replace UUIDs in batches, checking every batch response.

        Missing collections and wrong vector dimensions raise VectorStoreError.
        Batch import replaces an object with an existing UUID in Weaviate.
        """
        require_positive_batch_size(batch_size)
        client = await self._connected_client()
        from weaviate.classes.data import DataObject  # noqa: PLC0415

        async with self._operation("upsert"):
            info = await self.collection_info(kind)
            if info is None:
                raise VectorStoreError("Cannot upsert into a missing collection")
            if any(len(record.vector) != info.dimensions for record in records):
                raise VectorStoreError("Vector dimensions do not match the collection")
            collection = client.collections.use(self.collection_name(kind))
            for start in range(0, len(records), batch_size):
                result = await collection.data.insert_many(
                    [
                        DataObject(
                            uuid=record.id,
                            vector={"vector": record.vector},
                            properties={"labels": record.labels, "text": record.text},
                        )
                        for record in records[start : start + batch_size]
                    ]
                )
                if result.has_errors:
                    raise VectorStoreError(
                        f"Weaviate rejected {len(result.errors)} vector records"
                    )

    async def search(
        self,
        kind: VectorKind,
        vector: Sequence[float],
        *,
        limit: int,
        labels: Sequence[str] | None = None,
    ) -> list[VectorHit]:
        """Return dense matches on the graph-native score scale, best first."""
        self._validate_limit(limit)
        client = await self._connected_client()
        from weaviate.classes.query import MetadataQuery  # noqa: PLC0415

        async with self._operation("search"):
            info = await self.collection_info(kind)
            if info is None or (labels is not None and not labels):
                return []
            response = await client.collections.use(
                self.collection_name(kind)
            ).query.near_vector(
                near_vector=list(vector),
                target_vector="vector",
                limit=limit,
                filters=self._label_filter(labels),
                return_properties=["labels"],
                return_metadata=MetadataQuery(distance=True),
            )
            hits = []
            for obj in response.objects:
                distance = obj.metadata.distance
                if distance is None:
                    raise VectorStoreError("Weaviate omitted dense distance metadata")
                score = (
                    1 - distance / 2
                    if info.distance == Distance.COSINE
                    else 1 / (1 + distance)
                )
                hits.append(
                    VectorHit(
                        id=obj.uuid,
                        score=score,
                        payload={"labels": obj.properties["labels"]},
                    )
                )
            return sorted(hits, key=lambda hit: hit.score, reverse=True)

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
        """Fuse dense and BM25 ranks, with exact dense and lexical endpoints."""
        self._validate_limit(limit)
        if not 0 <= alpha <= 1:
            raise ValueError("alpha must be between zero and one")
        if alpha == 1:
            return await self.search(kind, vector, limit=limit, labels=labels)
        client = await self._connected_client()
        from weaviate.classes.query import (  # noqa: PLC0415
            HybridFusion,
            MetadataQuery,
        )

        async with self._operation("hybrid_search"):
            name = self.collection_name(kind)
            if not await client.collections.exists(name) or (
                labels is not None and not labels
            ):
                return []
            query = client.collections.use(name).query
            if alpha == 0:
                response = await query.bm25(
                    query=text,
                    query_properties=["text"],
                    limit=limit,
                    filters=self._label_filter(labels),
                    return_properties=["labels"],
                    return_metadata=MetadataQuery(score=True),
                )
            else:
                response = await query.hybrid(
                    query=text,
                    vector=list(vector),
                    alpha=alpha,
                    target_vector="vector",
                    query_properties=["text"],
                    limit=limit,
                    fusion_type=HybridFusion.RELATIVE_SCORE,
                    filters=self._label_filter(labels),
                    return_properties=["labels"],
                    return_metadata=MetadataQuery(score=True),
                )
            hits = []
            for obj in response.objects:
                if obj.metadata.score is None:
                    raise VectorStoreError("Weaviate omitted hybrid score metadata")
                hits.append(
                    VectorHit(
                        id=obj.uuid,
                        score=obj.metadata.score,
                        payload={"labels": obj.properties["labels"]},
                    )
                )
            return sorted(hits, key=lambda hit: hit.score, reverse=True)

    async def delete(self, kind: VectorKind, ids: Sequence[UUID]) -> None:
        """Delete in batches of at most 500 IDs, ignoring missing records."""
        client = await self._connected_client()
        from weaviate.classes.query import Filter  # noqa: PLC0415

        async with self._operation("delete"):
            name = self.collection_name(kind)
            if not await client.collections.exists(name):
                return
            collection = client.collections.use(name)
            for start in range(0, len(ids), 500):
                result = await collection.data.delete_many(
                    where=Filter.by_id().contains_any(
                        [str(id_) for id_ in ids[start : start + 500]],
                    ),
                )
                if result.failed:
                    raise VectorStoreError(
                        f"Weaviate failed to delete {result.failed} IDs"
                    )

    async def list_ids(
        self,
        kind: VectorKind,
        *,
        after: UUID | None = None,
        limit: int = 1000,
    ) -> list[UUID]:
        """Return ascending IDs strictly after the cursor, independent of scan order.

        Scans all UUIDs with the server cursor and retains only the smallest
        requested page. Memory is bounded by the page size for all collections.
        """
        if limit <= 0:
            raise ValueError("limit must be positive")
        client = await self._connected_client()
        async with self._operation("list_ids"):
            name = self.collection_name(kind)
            if not await client.collections.exists(name):
                return []
            collection = client.collections.use(name)
            cursor = None
            smallest: list[int] = []
            while True:
                response = await collection.query.fetch_objects(
                    limit=1000,
                    after=cursor,
                    return_properties=[],
                )
                if not response.objects:
                    break
                for obj in response.objects:
                    id_ = UUID(str(obj.uuid))
                    if after is None or id_ > after:
                        heapq.heappush(smallest, -id_.int)
                        if len(smallest) > limit:
                            heapq.heappop(smallest)
                cursor = response.objects[-1].uuid
            return [UUID(int=-value) for value in sorted(smallest, reverse=True)]

    async def _connected_client(self) -> "WeaviateAsyncClient":
        """Import the optional SDK lazily and serialize connection creation."""
        async with self._connect_lock:
            if self._client is not None:
                return self._client
            try:
                import weaviate  # noqa: PLC0415
                from weaviate.classes.init import Auth  # noqa: PLC0415
            except ImportError as exc:
                raise VectorStoreMissingExtraError("weaviate") from exc
            settings = self._settings
            auth = (
                Auth.api_key(settings.api_key.get_secret_value())
                if settings.api_key is not None
                else None
            )
            parsed = urlparse(settings.url)
            if settings.mode == "cloud":
                if auth is None:
                    raise VectorStoreError("Weaviate cloud requires an API key")
                client = weaviate.use_async_with_weaviate_cloud(
                    cluster_url=settings.url,
                    auth_credentials=auth,
                )
            else:
                secure = parsed.scheme == "https"
                client = weaviate.use_async_with_custom(
                    http_host=parsed.hostname,
                    http_port=parsed.port or (443 if secure else 8080),
                    http_secure=secure,
                    grpc_host=parsed.hostname,
                    grpc_port=settings.grpc_port,
                    grpc_secure=secure,
                    auth_credentials=auth,
                )
            try:
                async with self._operation("initialize"):
                    await client.connect()
                    if not await client.is_ready():
                        raise VectorStoreError("Weaviate is not ready")
            except BaseException:
                with contextlib.suppress(Exception):
                    await client.close()
                raise
            self._client = client
            return client

    def _validate_limit(self, limit: int) -> None:
        """Reject invalid search windows before issuing any request."""
        if not 1 <= limit <= self.max_results:
            raise ValueError(f"limit must be between 1 and {self.max_results}")

    @staticmethod
    def _label_filter(labels: Sequence[str] | None) -> Any:
        """Build an exact any-of array filter without interpolating strings."""
        from weaviate.classes.query import Filter  # noqa: PLC0415

        return (
            Filter.by_property("labels").contains_any(list(labels)) if labels else None
        )

    @asynccontextmanager
    async def _operation(self, operation: str) -> AsyncIterator[None]:
        """Translate SDK failures without exposing server responses or credentials."""
        from weaviate.exceptions import WeaviateBaseError  # noqa: PLC0415

        with self._tracer.start_as_current_span(f"agrag.vectordb.{operation}"):
            try:
                yield
            except WeaviateBaseError:
                raise VectorStoreError(f"Weaviate {operation} failed") from None
