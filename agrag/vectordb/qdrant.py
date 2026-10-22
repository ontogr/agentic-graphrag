"""Qdrant indexes with dense vectors and locally computed BM25 sparse vectors."""

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urlsplit
from uuid import UUID

from opentelemetry.trace import SpanKind, Tracer
from opentelemetry.util.types import AttributeValue
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
    MAX_SEARCH_LIMIT,
    require_encrypted_remote_connection,
    require_positive_batch_size,
)
from agrag.observability import get_tracer
from agrag.vectordb.base import VectorStore
from agrag.vectordb.errors import (
    CollectionMismatchError,
    VectorStoreError,
    VectorStoreMissingExtraError,
)
from agrag.vectordb.settings import CollectionPrefix


if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient, models


_COLLECTION_LOCKS: dict[tuple[str, str], asyncio.Lock] = {}


class QdrantSettings(BaseSettings):
    """Qdrant connection and per-graph collection names.

    Attributes:
        url: HTTP endpoint. Env: ``QDRANT_URL``.
        api_key: Optional authentication secret. Env: ``QDRANT_API_KEY``.
        require_tls: Require HTTPS for remote hosts without credentials too.
            Loopback is exempt. Env: ``QDRANT_REQUIRE_TLS``.
        collection_prefix: Required unique graph prefix, beginning with a letter.
            Env: ``QDRANT_COLLECTION_PREFIX``.
    """

    model_config = SettingsConfigDict(
        env_prefix="QDRANT_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    url: str = "http://localhost:6333"
    api_key: SecretStr | None = None
    require_tls: bool = False
    collection_prefix: CollectionPrefix

    @model_validator(mode="after")
    def _validate_tls(self) -> "QdrantSettings":
        """Reject plaintext remote credentials or an unmet TLS requirement."""
        try:
            parsed = urlsplit(self.url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("QDRANT_URL requires an HTTP or HTTPS host")
            if parsed.username is not None or parsed.password is not None:
                raise ValueError("Use QDRANT_API_KEY instead of URL credentials")
            if parsed.query or parsed.fragment:
                raise ValueError("QDRANT_URL cannot contain a query or fragment")
            if parsed.port == 0:
                raise ValueError("QDRANT_URL port must be between 1 and 65535")
            require_encrypted_remote_connection(
                url=self.url,
                has_credential=self.api_key is not None,
                encrypted_schemes=frozenset({"https"}),
                require_encryption=self.require_tls,
            )
        except ValueError:
            raise ValueError(
                "QDRANT_URL must be an HTTP(S) endpoint with a valid port and "
                "without URL credentials, query or fragment; remote credentials "
                "and QDRANT_REQUIRE_TLS require HTTPS"
            ) from None
        return self


class QdrantVectorStore(VectorStore):
    """An exclusive vector index on Qdrant 1.17 or newer.

    BM25 inference runs locally through FastEmbed, not Qdrant Cloud. Hybrid
    queries use weighted reciprocal rank fusion. Dense scores have graph-native
    scale; hybrid scores are ranks only. Searches accept at most 16384 results.

    Args:
        settings: Connection settings and the required per-graph prefix.
        tracer: Opens spans without recording credentials or embedded text.
    """

    name: ClassVar[str] = "qdrant"
    max_results = MAX_SEARCH_LIMIT

    def __init__(
        self, *, settings: QdrantSettings | None = None, tracer: Tracer | None = None
    ) -> None:
        """Configure the index without connecting or loading an inference model."""
        self._settings = settings or QdrantSettings()
        self.collection_prefix = self._settings.collection_prefix
        self._client: AsyncQdrantClient | None = None
        self._client_lock = asyncio.Lock()
        self._tracer = get_tracer(tracer)

    async def initialize(self) -> None:
        """Connect once, authenticate and check that the server is reachable."""
        async with self._client_lock:
            if self._client is not None:
                return
            try:
                from qdrant_client import AsyncQdrantClient  # noqa: PLC0415
            except ImportError:
                raise VectorStoreMissingExtraError("qdrant") from None
            client: AsyncQdrantClient | None = None
            try:
                async with self._errors("initialize"):
                    client = AsyncQdrantClient(
                        url=self._settings.url,
                        api_key=(
                            self._settings.api_key.get_secret_value()
                            if self._settings.api_key is not None
                            else None
                        ),
                        cloud_inference=False,
                    )
                    await client.get_collections()
            except BaseException:
                if client is not None:
                    await client.close()
                raise
            self._client = client

    async def close(self) -> None:
        """Release connections; a later initialize can reconnect."""
        async with self._client_lock:
            if self._client is not None:
                async with self._errors("close"):
                    await self._client.close()
                self._client = None

    async def ensure_collection(
        self, kind: VectorKind, *, dimensions: int, distance: Distance
    ) -> None:
        """Create both vector indexes or reject a mismatched existing index."""
        if distance == Distance.DOT:
            raise ValueError("DOT distance is unsupported")
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        client = await self._connected_client()
        from qdrant_client import models  # noqa: PLC0415

        name = self.collection_name(kind)
        lock = _COLLECTION_LOCKS.setdefault((self._settings.url, name), asyncio.Lock())
        async with lock, self._errors("ensure_collection", kind=kind):
            if not await client.collection_exists(name):
                try:
                    await client.create_collection(
                        name,
                        vectors_config={
                            "dense": models.VectorParams(
                                size=dimensions,
                                distance=models.Distance(distance.value),
                            )
                        },
                        sparse_vectors_config={
                            "bm25": models.SparseVectorParams(
                                modifier=models.Modifier.IDF
                            )
                        },
                    )
                except Exception:
                    # Another process can create the collection after the check.
                    if not await client.collection_exists(name):
                        raise
            info = await self.collection_info(kind)
            if info is None or (info.dimensions, info.distance) != (
                dimensions,
                distance,
            ):
                raise CollectionMismatchError(
                    f"Collection {name!r} has {info}; requested "
                    f"dimensions={dimensions}, distance={distance}"
                )
            await client.create_payload_index(
                name,
                "labels",
                field_schema=models.PayloadSchemaType.KEYWORD,
                wait=True,
            )

    async def collection_info(
        self, kind: VectorKind, *, exact_count: bool = True
    ) -> CollectionInfo | None:
        """Return count and dense configuration, or None when absent.

        Args:
            kind: The collection to describe.
            exact_count: Scan the collection for an exact count. When false, the
                count is the server's estimate from collection metadata.
        """
        client = await self._connected_client()
        async with self._errors("collection_info", kind=kind, missing_ok=True):
            info = await client.get_collection(self.collection_name(kind))
            vectors = info.config.params.vectors
            if not isinstance(vectors, dict) or "dense" not in vectors:
                raise CollectionMismatchError("Collection has no named dense vector")
            sparse = info.config.params.sparse_vectors
            if sparse is None or "bm25" not in sparse:
                raise CollectionMismatchError(
                    "Collection has no named bm25 sparse vector"
                )
            from qdrant_client import models  # noqa: PLC0415

            if sparse["bm25"].modifier != models.Modifier.IDF:
                raise CollectionMismatchError("Collection bm25 vector requires IDF")
            dense = vectors["dense"]
            if exact_count:
                counted = await client.count(self.collection_name(kind), exact=True)
                count = counted.count
            else:
                count = info.points_count or 0
            return CollectionInfo(
                dimensions=dense.size,
                distance=Distance(dense.distance.value),
                count=count,
            )
        return None

    async def delete_collection(self, kind: VectorKind) -> None:
        """Remove a collection; an absent collection is already deleted."""
        client = await self._connected_client()
        async with self._errors("delete_collection", kind=kind, missing_ok=True):
            await client.delete_collection(self.collection_name(kind))

    async def upsert(
        self,
        kind: VectorKind,
        records: Sequence[VectorRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Overwrite records, waiting for each dense and BM25 batch to be applied."""
        require_positive_batch_size(batch_size)
        client = await self._connected_client()
        from qdrant_client import models  # noqa: PLC0415

        async with self._errors(
            "upsert",
            kind=kind,
            internal=True,
            attributes={"agrag.record_count": len(records)},
        ):
            if not await client.collection_exists(self.collection_name(kind)):
                raise VectorStoreError("Cannot upsert into a missing collection")
            for start in range(0, len(records), batch_size):
                batch = records[start : start + batch_size]
                async with self._errors(
                    "upsert_batch",
                    kind=kind,
                    attributes={"db.operation.batch.size": len(batch)},
                ):
                    await client.upsert(
                        self.collection_name(kind),
                        points=[
                            models.PointStruct(
                                id=str(record.id),
                                vector={
                                    "dense": record.vector,
                                    "bm25": models.Document(
                                        text=record.text, model="Qdrant/bm25"
                                    ),
                                },
                                payload={"labels": record.labels, "text": record.text},
                            )
                            for record in batch
                        ],
                        wait=True,
                    )

    async def search(
        self,
        kind: VectorKind,
        vector: Sequence[float],
        *,
        limit: int,
        labels: Sequence[str] | None = None,
    ) -> list[VectorHit]:
        """Return dense hits on the graph-native score scale."""
        self._validate_limit(limit)
        client = await self._connected_client()
        async with self._errors(
            "search", kind=kind, missing_ok=True, attributes={"agrag.limit": limit}
        ):
            info = await client.get_collection(self.collection_name(kind))
            vectors = info.config.params.vectors
            if not isinstance(vectors, dict) or "dense" not in vectors:
                raise CollectionMismatchError("Collection has no named dense vector")
            distance = Distance(vectors["dense"].distance.value)
            result = await client.query_points(
                self.collection_name(kind),
                query=list(vector),
                using="dense",
                query_filter=self._label_filter(labels),
                limit=limit,
                with_payload=["labels"],
            )
            return [
                VectorHit(
                    id=UUID(str(point.id)),
                    score=(
                        (1 + point.score) / 2
                        if distance == Distance.COSINE
                        else 1 / (1 + point.score**2)
                    ),
                    payload=point.payload or {},
                )
                for point in result.points
            ]
        return []

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
        """Fuse dense and BM25 ranks; alpha endpoints select one leg exactly."""
        self._validate_limit(limit)
        if not 0 <= alpha <= 1:
            raise ValueError("alpha must be between zero and one")
        if alpha == 1:
            return await self.search(kind, vector, limit=limit, labels=labels)
        client = await self._connected_client()
        from qdrant_client import models  # noqa: PLC0415

        async with self._errors(
            "hybrid_search",
            kind=kind,
            missing_ok=True,
            attributes={"agrag.limit": limit, "agrag.alpha": alpha},
        ):
            if not await client.collection_exists(self.collection_name(kind)):
                return []
            lexical = models.Document(text=text, model="Qdrant/bm25")
            if alpha == 0:
                result = await client.query_points(
                    self.collection_name(kind),
                    query=lexical,
                    using="bm25",
                    query_filter=self._label_filter(labels),
                    limit=limit,
                    with_payload=["labels"],
                )
            else:
                pool = min(limit * 4, self.max_results)
                result = await client.query_points(
                    self.collection_name(kind),
                    prefetch=[
                        models.Prefetch(
                            query=list(vector),
                            using="dense",
                            limit=pool,
                            filter=self._label_filter(labels),
                        ),
                        models.Prefetch(
                            query=lexical,
                            using="bm25",
                            limit=pool,
                            filter=self._label_filter(labels),
                        ),
                    ],
                    query=models.RrfQuery(rrf=models.Rrf(weights=[alpha, 1 - alpha])),
                    limit=limit,
                    with_payload=["labels"],
                )
            return [
                VectorHit(
                    id=UUID(str(point.id)),
                    score=point.score,
                    payload=point.payload or {},
                )
                for point in result.points
            ]
        return []

    async def delete(self, kind: VectorKind, ids: Sequence[UUID]) -> None:
        """Delete in batches of 256 and wait for the changes to become visible."""
        client = await self._connected_client()
        from qdrant_client import models  # noqa: PLC0415

        async with self._errors(
            "delete",
            kind=kind,
            internal=True,
            attributes={"agrag.record_count": len(ids)},
        ):
            if not await client.collection_exists(self.collection_name(kind)):
                return
            for start in range(0, len(ids), 256):
                batch = ids[start : start + 256]
                async with self._errors(
                    "delete_batch",
                    kind=kind,
                    missing_ok=True,
                    attributes={"db.operation.batch.size": len(batch)},
                ):
                    await client.delete(
                        self.collection_name(kind),
                        models.PointIdsList(points=[str(id_) for id_ in batch]),
                        wait=True,
                    )

    async def list_ids(
        self, kind: VectorKind, *, after: UUID | None = None, limit: int = 1000
    ) -> list[UUID]:
        """Page ascending UUIDs, excluding the cursor even if it still exists.

        A limit of zero returns no IDs; a negative limit raises ValueError.
        """
        if limit < 0:
            raise ValueError("limit cannot be negative")
        if limit == 0:
            return []
        client = await self._connected_client()
        from qdrant_client import models  # noqa: PLC0415

        async with self._errors(
            "list_ids", kind=kind, missing_ok=True, attributes={"agrag.limit": limit}
        ):
            points, _ = await client.scroll(
                self.collection_name(kind),
                offset=str(after) if after is not None else None,
                scroll_filter=(
                    models.Filter(must_not=[models.HasIdCondition(has_id=[str(after)])])
                    if after is not None
                    else None
                ),
                limit=limit,
                with_payload=False,
                with_vectors=False,
            )
            return [UUID(str(point.id)) for point in points]
        return []

    async def _connected_client(self) -> "AsyncQdrantClient":
        """Initialize lazily without importing the optional client at construction."""
        await self.initialize()
        if self._client is None:
            raise VectorStoreError("Qdrant client is closed")
        return self._client

    def _validate_limit(self, limit: int) -> None:
        """Reject unsupported result sizes before sending a request."""
        if not 1 <= limit <= self.max_results:
            raise ValueError(f"limit must be between 1 and {self.max_results}")

    @staticmethod
    def _label_filter(labels: Sequence[str] | None) -> "models.Filter | None":
        """Match any requested label in the stored keyword array."""
        from qdrant_client import models  # noqa: PLC0415

        if labels is None:
            return None
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="labels", match=models.MatchAny(any=list(labels))
                )
            ]
        )

    async def _collection_missing(self, kind: VectorKind) -> bool:
        """Confirm with the server that the collection is absent."""
        if self._client is None:
            return False
        try:
            return not await self._client.collection_exists(self.collection_name(kind))
        except Exception:
            return False

    @asynccontextmanager
    async def _errors(
        self,
        operation: str,
        *,
        kind: VectorKind | None = None,
        missing_ok: bool = False,
        internal: bool = False,
        attributes: Mapping[str, AttributeValue] | None = None,
    ) -> AsyncIterator[None]:
        """Trace an operation and translate SDK failures without leaking secrets.

        Args:
            operation: Span suffix and failure label.
            kind: Collection the operation targets, if any.
            missing_ok: Suppress a 404 only after the server confirms that the
                collection does not exist; other 404s, such as a proxy or wrong
                URL prefix, still fail.
            internal: Open an ``INTERNAL`` span that groups client spans.
            attributes: Extra span attributes.
        """
        from qdrant_client.http.exceptions import UnexpectedResponse  # noqa: PLC0415

        span_attributes: dict[str, AttributeValue] = {
            "db.system.name": "qdrant",
            "server.address": str(urlsplit(self._settings.url).hostname),
            **(attributes or {}),
        }
        if kind is not None:
            span_attributes["db.collection.name"] = self.collection_name(kind)
        with self._tracer.start_as_current_span(
            f"qdrant.{operation}",
            kind=SpanKind.INTERNAL if internal else SpanKind.CLIENT,
            attributes=span_attributes,
            record_exception=False,
        ):
            try:
                yield
            except VectorStoreError:
                raise
            except UnexpectedResponse as exc:
                if not (
                    missing_ok
                    and kind is not None
                    and exc.status_code == 404
                    and await self._collection_missing(kind)
                ):
                    raise VectorStoreError(
                        f"Qdrant {operation} failed (HTTP {exc.status_code})"
                    ) from None
            except Exception:
                raise VectorStoreError(f"Qdrant {operation} failed") from None
