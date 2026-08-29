"""Weaviate vector-store backend."""

import urllib.parse
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from agrag.common.data_models.vector_record import Distance, VectorHit, VectorRecord
from agrag.vectordb.base import VectorStore
from agrag.vectordb.errors import VectorStoreMissingExtraError
from agrag.vectordb.settings import WeaviateSettings


_VECTOR_NAME = "vector"


class WeaviateVectorStore(VectorStore):
    """A ``VectorStore`` backed by Weaviate, including native hybrid search.

    The client connects lazily on first use, so constructing the store does not
    open a network connection. Weaviate does its own server-side BM25, so
    hybrid search needs no client-side sparse embedder.
    """

    def __init__(
        self,
        *,
        settings: WeaviateSettings | None = None,
        client: Any | None = None,
    ) -> None:
        """Build the store.

        Args:
            settings: Weaviate connection settings. Defaults to
                ``WeaviateSettings()``.
            client: A pre-built Weaviate async client, for tests. When set,
                ``__init__`` imports nothing and the store calls this object
                directly instead of building one.
        """
        self._settings = settings or WeaviateSettings()
        self._client: Any = client

    async def _ensure_client(self) -> Any:
        """Build the Weaviate client once and cache it.

        Returns:
            The connected client object.

        Raises:
            VectorStoreMissingExtraError: weaviate-client is not installed.
        """
        if self._client is None:
            try:
                # Lazy import: a clean install must raise
                # VectorStoreMissingExtraError, not ImportError, when
                # weaviate-client is absent.
                import weaviate  # noqa: PLC0415
                from weaviate.classes.init import Auth  # noqa: PLC0415
            except ImportError as exc:
                raise VectorStoreMissingExtraError("weaviate") from exc
            auth = (
                Auth.api_key(self._settings.api_key) if self._settings.api_key else None
            )
            if self._settings.mode == "cloud":
                self._client = weaviate.use_async_with_weaviate_cloud(
                    cluster_url=self._settings.url, auth_credentials=auth
                )
            else:
                parsed = urllib.parse.urlparse(self._settings.url)
                self._client = weaviate.use_async_with_custom(
                    http_host=parsed.hostname or "localhost",
                    http_port=parsed.port or 8080,
                    http_secure=parsed.scheme == "https",
                    grpc_host=parsed.hostname or "localhost",
                    grpc_port=self._settings.grpc_port,
                    grpc_secure=parsed.scheme == "https",
                    auth_credentials=auth,
                )
            # use_async_with_custom / use_async_with_weaviate_cloud build a
            # disconnected client; we must connect it before any call.
            await self._client.connect()
        return self._client

    def _weaviate_distance(self, distance: Distance) -> Any:
        """Map our ``Distance`` to Weaviate's vector-similarity function.

        Args:
            distance: The distance metric to map.

        Returns:
            The matching Weaviate distance value.

        Raises:
            ValueError: ``distance`` is not a supported Weaviate metric.
        """
        from weaviate.classes.config import VectorDistances  # noqa: PLC0415

        mapping = {
            Distance.COSINE: VectorDistances.COSINE,
            Distance.EUCLID: VectorDistances.L2_SQUARED,
            Distance.DOT: VectorDistances.DOT,
        }
        if distance not in mapping:
            raise ValueError(f"unsupported distance metric for Weaviate: {distance}")
        return mapping[distance]

    def _compile_filter(self, filters: dict[str, Any] | None) -> Any:
        """Build a Weaviate filter from a flat-dict payload filter.

        Args:
            filters: A flat-dict filter: a scalar value means exact match, a
                list value means any of, and all keys are AND-ed together.
                ``None`` means no filter.

        Returns:
            A Weaviate ``Filter``, or ``None`` when ``filters`` is empty.
        """
        if not filters:
            return None
        from weaviate.classes.query import Filter as WeaviateFilter  # noqa: PLC0415

        conditions = []
        for key, value in filters.items():
            prop = WeaviateFilter.by_property(key)
            if isinstance(value, list):
                conditions.append(prop.contains_any(value))
            else:
                conditions.append(prop.equal(value))
        return WeaviateFilter.all_of(conditions)

    @staticmethod
    def _to_hit(obj: Any) -> VectorHit:
        """Convert a Weaviate object to a ``VectorHit``.

        Args:
            obj: A Weaviate query result object.

        Returns:
            The equivalent hit.
        """
        score = 0.0
        if obj.metadata is not None and obj.metadata.score is not None:
            score = float(obj.metadata.score)
        return VectorHit(
            id=UUID(str(obj.uuid)),
            score=score,
            payload=dict(obj.properties or {}),
        )

    @staticmethod
    def _to_record(obj: Any) -> VectorRecord:
        """Convert a Weaviate object to a ``VectorRecord``.

        Args:
            obj: A Weaviate query result object.

        Returns:
            The equivalent record.
        """
        vector = list((obj.vector or {}).get(_VECTOR_NAME, [])) if obj.vector else []
        return VectorRecord(
            id=UUID(str(obj.uuid)),
            vector=vector,
            payload=dict(obj.properties or {}),
        )

    async def initialize(self) -> None:
        """Open the connection and check authentication."""
        await self._ensure_client()

    async def ensure_collection(
        self, name: str, *, dimensions: int, distance: Distance, hybrid: bool = False
    ) -> None:
        """Create the collection if it does not exist.

        Args:
            name: The collection name.
            dimensions: The embedding dimension. Weaviate stores it on each
                vector, so a mismatch surfaces at write time, not here.
            distance: The distance metric new collections use.
            hybrid: No-op for Weaviate, which needs no sparse provisioning.
        """
        from weaviate.classes.config import Configure  # noqa: PLC0415

        client = await self._ensure_client()
        if await client.collections.exists(name):
            return
        distance_value = self._weaviate_distance(distance)
        vector_config = Configure.Vectors.self_provided(
            name=_VECTOR_NAME,
            vector_index_config=Configure.VectorIndex.hnsw(
                distance_metric=distance_value
            ),
        )
        await client.collections.create(
            name=name,
            vector_config=vector_config,
        )

    async def collection_exists(self, name: str) -> bool:
        """Report whether a collection exists.

        Args:
            name: The collection name.

        Returns:
            ``True`` if the collection exists.
        """
        client = await self._ensure_client()
        return await client.collections.exists(name)

    async def delete_collection(self, name: str) -> None:
        """Delete a collection and all its objects.

        Args:
            name: The collection name.
        """
        client = await self._ensure_client()
        await client.collections.delete(name)

    async def upsert(
        self,
        collection: str,
        records: Sequence[VectorRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Write or overwrite records in a collection.

        Args:
            collection: The collection to write to.
            records: The records to upsert, in order.
            batch_size: The number of records per backend write call.
        """
        client = await self._ensure_client()
        target = client.collections.get(collection)
        for record in records:
            await target.data.insert(
                properties=record.payload,
                vector={_VECTOR_NAME: record.vector},
                uuid=str(record.id),
            )

    async def search(
        self,
        collection: str,
        query_vector: Sequence[float],
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        """Search by dense vector only.

        Args:
            collection: The collection to search.
            query_vector: The dense query embedding.
            limit: The maximum number of hits to return.
            filters: A flat-dict filter on payload fields.

        Returns:
            The matched hits, highest score first.
        """
        from weaviate.classes.query import MetadataQuery  # noqa: PLC0415

        client = await self._ensure_client()
        target = client.collections.get(collection)
        response = await target.query.near_vector(
            near_vector=list(query_vector),
            limit=limit,
            filters=self._compile_filter(filters),
            return_metadata=MetadataQuery(score=True),
        )
        objects = response.objects if hasattr(response, "objects") else response
        return [self._to_hit(obj) for obj in objects]

    async def hybrid_search(
        self,
        collection: str,
        query_vector: Sequence[float],
        query_text: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        alpha: float = 0.5,
    ) -> list[VectorHit]:
        """Search by dense vector and keyword text in one fused call.

        Args:
            collection: The collection to search.
            query_vector: The dense query embedding.
            query_text: The query text, matched by keyword/BM25.
            limit: The maximum number of hits to return.
            filters: A flat-dict filter on payload fields.
            alpha: The dense/keyword balance. ``1.0`` is pure dense, ``0.0`` is
                pure keyword.

        Returns:
            The fused hits, highest score first.
        """
        from weaviate.classes.query import MetadataQuery  # noqa: PLC0415

        client = await self._ensure_client()
        target = client.collections.get(collection)
        response = await target.query.hybrid(
            query=query_text,
            vector=list(query_vector),
            alpha=alpha,
            limit=limit,
            filters=self._compile_filter(filters),
            return_metadata=MetadataQuery(score=True),
        )
        objects = response.objects if hasattr(response, "objects") else response
        return [self._to_hit(obj) for obj in objects]

    async def scroll(
        self,
        collection: str,
        *,
        limit: int = 100,
        page_offset: str | None = None,
        filters: dict[str, Any] | None = None,
        with_vectors: bool = False,
    ) -> tuple[list[VectorRecord], str | None]:
        """Iterate records in a collection, in batches.

        Args:
            collection: The collection to read.
            limit: The maximum number of records per page.
            page_offset: The cursor id from a previous ``scroll`` call.
            filters: A flat-dict filter on payload fields.
            with_vectors: Whether to return each record's vector.

        Returns:
            The page of records and the next page cursor, or ``None`` at the
            end.
        """
        client = await self._ensure_client()
        target = client.collections.get(collection)
        response = await target.query.fetch_objects(
            limit=limit,
            after=page_offset,
            filters=self._compile_filter(filters),
            include_vector=with_vectors,
        )
        objects = response.objects if hasattr(response, "objects") else response
        records = [self._to_record(obj) for obj in objects]
        next_offset = str(objects[-1].uuid) if len(objects) == limit else None
        return records, next_offset

    async def retrieve(
        self, collection: str, ids: Sequence[UUID]
    ) -> list[VectorRecord]:
        """Fetch records by id.

        Args:
            collection: The collection to read.
            ids: The ids to fetch.

        Returns:
            The records that exist, in the requested order, omitting missing
            ids.
        """
        client = await self._ensure_client()
        target = client.collections.get(collection)
        records: list[VectorRecord] = []
        for item_id in ids:
            obj = await target.query.fetch_object_by_id(
                uuid=str(item_id), include_vector=True
            )
            if obj is not None:
                records.append(self._to_record(obj))
        return records

    async def count(
        self, collection: str, *, filters: dict[str, Any] | None = None
    ) -> int:
        """Count records in a collection.

        Args:
            collection: The collection to count.
            filters: A flat-dict filter on payload fields.

        Returns:
            The number of matching records.
        """
        client = await self._ensure_client()
        target = client.collections.get(collection)
        result = await target.aggregate.count(filters=self._compile_filter(filters))
        return result.total_count

    async def delete(self, collection: str, ids: Sequence[UUID]) -> None:
        """Delete records by id.

        Args:
            collection: The collection to delete from.
            ids: The ids to delete.
        """
        client = await self._ensure_client()
        target = client.collections.get(collection)
        for item_id in ids:
            await target.data.delete_by_id(uuid=str(item_id))

    async def close(self) -> None:
        """Release the backend connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
