"""Qdrant vector-store backend."""

import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from agrag.common.data_models.vector_record import Distance, VectorHit, VectorRecord
from agrag.common.validation import require_positive_batch_size
from agrag.embedding.fastembed_bm25 import FastEmbedBM25Embedder
from agrag.embedding.sparse_base import SparseEmbedder
from agrag.vectordb.base import VectorStore
from agrag.vectordb.errors import (
    CollectionDimensionMismatchError,
    VectorStoreError,
    VectorStoreMissingExtraError,
)
from agrag.vectordb.settings import QdrantSettings


_SPARSE_VECTOR_NAME = "bm25"

# Unlike Weaviate and Milvus, Qdrant has no server-side text-to-sparse-vector
# pipeline, so upsert must compute and attach each record's sparse vector
# itself, from this payload key, matching the "text" convention Milvus's
# server-side BM25 Function already uses.
_TEXT_PAYLOAD_FIELD = "text"

# Qdrant's native fusion (RRF, DBSF) has no continuous dense/keyword weight, so
# hybrid_search blends two independent queries client-side instead. Each side
# fetches more than `limit` candidates so a document that is weak on one
# signal but strong on the other still has a chance to surface once alpha
# favors that signal.
_HYBRID_POOL_MULTIPLIER = 5


def _min_max_normalize(scores: dict[UUID, float]) -> dict[UUID, float]:
    """Scale a score map to [0, 1] so two differently-scaled result sets blend fairly.

    Args:
        scores: A map of id to raw score.

    Returns:
        The same ids mapped to their min-max normalized score. Every value is
        ``1.0`` when all scores are equal, so a nonempty pool never drops out
        of a blend just because its scores were tied.
    """
    if not scores:
        return {}
    values = scores.values()
    lo, hi = min(values), max(values)
    if hi == lo:
        return dict.fromkeys(scores, 1.0)
    return {point_id: (score - lo) / (hi - lo) for point_id, score in scores.items()}


class QdrantVectorStore(VectorStore):
    """A ``VectorStore`` backed by Qdrant, including native hybrid search.

    The client connects lazily on first use, so constructing the store does not
    open a network connection. Hybrid search builds its sparse query with a
    ``SparseEmbedder`` that defaults to FastEmbed BM25 and loads only when a
    hybrid call first runs, not at construction.
    """

    def __init__(
        self,
        *,
        settings: QdrantSettings | None = None,
        sparse_embedder: SparseEmbedder | None = None,
        client: Any | None = None,
    ) -> None:
        """Build the store.

        Args:
            settings: Qdrant connection settings. Defaults to
                ``QdrantSettings()``.
            sparse_embedder: The sparse embedder hybrid search uses. Defaults to
                a lazily-built ``FastEmbedBM25Embedder``.
            client: A pre-built ``AsyncQdrantClient``, for tests. When set,
                ``__init__`` imports nothing and the store calls this object
                directly instead of building one.
        """
        self._settings = settings or QdrantSettings()
        self._sparse_embedder = sparse_embedder
        self._client: Any = client
        self._models: Any = None
        self._hybrid_collections: set[str] = set()
        self._checked_collections: set[str] = set()

    async def _ensure_client(self) -> Any:
        """Build the Qdrant client once and cache it.

        Returns:
            The connected client object.

        Raises:
            VectorStoreMissingExtraError: qdrant-client is not installed.
        """
        if self._client is None:
            try:
                # Lazy import: a clean install must raise
                # VectorStoreMissingExtraError, not ImportError, when
                # qdrant-client is absent.
                from qdrant_client import AsyncQdrantClient, models  # noqa: PLC0415
            except ImportError as exc:
                raise VectorStoreMissingExtraError("qdrant") from exc
            self._models = models
            self._client = AsyncQdrantClient(
                url=self._settings.url,
                api_key=self._settings.api_key or None,
            )
        elif self._models is None:
            # A test injected a client; still resolve the models module so
            # filter and payload helpers work without rebuilding a client.
            from qdrant_client import models  # noqa: PLC0415

            self._models = models
        return self._client

    def _ensure_sparse_embedder(self) -> SparseEmbedder:
        """Return the sparse embedder, building the default on first use.

        Returns:
            The sparse embedder hybrid search uses.
        """
        if self._sparse_embedder is None:
            self._sparse_embedder = FastEmbedBM25Embedder()
        return self._sparse_embedder

    def _qdrant_distance(self, distance: Distance) -> Any:
        """Map our ``Distance`` to Qdrant's distance enum.

        Args:
            distance: The distance metric to map.

        Returns:
            The matching Qdrant distance value.
        """
        return {
            Distance.COSINE: self._models.Distance.COSINE,
            Distance.EUCLID: self._models.Distance.EUCLID,
            Distance.DOT: self._models.Distance.DOT,
        }[distance]

    def _compile_filter(self, filters: dict[str, Any] | None) -> Any:
        """Build a Qdrant filter from a flat-dict payload filter.

        Args:
            filters: A flat-dict filter: a scalar value means exact match, a
                list value means any of, and all keys are AND-ed together.
                ``None`` means no filter.

        Returns:
            A Qdrant ``Filter``, or ``None`` when ``filters`` is empty.
        """
        if not filters:
            return None
        conditions = []
        for key, value in filters.items():
            if isinstance(value, list):
                condition = self._models.FieldCondition(
                    key=key, match=self._models.MatchAny(any=value)
                )
            else:
                condition = self._models.FieldCondition(
                    key=key, match=self._models.MatchValue(value=value)
                )
            conditions.append(condition)
        return self._models.Filter(must=conditions)

    @staticmethod
    def _dimension_of(vectors: Any) -> int | None:
        """Read the dense vector dimension from a collection's vector config.

        Args:
            vectors: The ``vectors`` field of a Qdrant ``CollectionInfo``.

        Returns:
            The dense vector dimension, or ``None`` when it cannot be read.
        """
        if isinstance(vectors, dict):
            for vector in vectors.values():
                if vector is not None:
                    return getattr(vector, "size", None)
            return None
        return getattr(vectors, "size", None)

    def _to_hit(self, point: Any) -> VectorHit:
        """Convert a Qdrant scored point to a ``VectorHit``.

        Args:
            point: A Qdrant ``ScoredPoint``.

        Returns:
            The equivalent hit.
        """
        return VectorHit(
            id=UUID(str(point.id)),
            score=float(point.score),
            payload=point.payload or {},
        )

    def _to_record(self, point: Any) -> VectorRecord:
        """Convert a Qdrant record to a ``VectorRecord``.

        Args:
            point: A Qdrant point with payload and optional vector.

        Returns:
            The equivalent record.
        """
        vector = point.vector or []
        if isinstance(vector, dict):
            # A hybrid point's vector is a dict of named vectors, with the
            # dense vector stored unnamed (""), matching _point_vector's
            # write-side convention.
            vector = vector.get("", [])
        return VectorRecord(
            id=UUID(str(point.id)),
            vector=list(vector),
            payload=point.payload or {},
        )

    async def initialize(self) -> None:
        """Check connectivity and authentication."""
        client = await self._ensure_client()
        await client.get_collections()

    async def ensure_collection(
        self, name: str, *, dimensions: int, distance: Distance, hybrid: bool = False
    ) -> None:
        """Create the collection if it does not exist.

        Args:
            name: The collection name.
            dimensions: The embedding dimension.
            distance: The distance metric new collections use.
            hybrid: Whether to provision the named sparse vector hybrid search
                needs.

        Raises:
            CollectionDimensionMismatchError: The collection exists with a
                different dimension than ``dimensions``.
            VectorStoreError: The collection exists without hybrid search
                support and ``hybrid=True`` was requested.
        """
        client = await self._ensure_client()
        if await client.collection_exists(name):
            info = await client.get_collection(name)
            existing = self._dimension_of(info.config.params.vectors)
            if existing is not None and existing != dimensions:
                raise CollectionDimensionMismatchError(
                    expected=existing, actual=dimensions
                )
            if info.config.params.sparse_vectors:
                self._hybrid_collections.add(name)
            elif hybrid:
                # Adding sparse-vector config to an existing collection would
                # leave every record already in it without a sparse vector,
                # so it would never surface in keyword search. Upgrading in
                # place is not supported; the caller needs a new collection.
                raise VectorStoreError(
                    f"collection {name!r} already exists without hybrid "
                    "search support; create a new collection with "
                    "ensure_collection(..., hybrid=True) instead of "
                    "upgrading this one in place"
                )
            self._checked_collections.add(name)
            return
        vectors_config = self._models.VectorParams(
            size=dimensions, distance=self._qdrant_distance(distance)
        )
        sparse_config: dict[str, Any] | None = None
        if hybrid:
            sparse_config = {
                _SPARSE_VECTOR_NAME: self._models.SparseVectorParams(
                    modifier=self._models.Modifier.IDF
                )
            }
        await client.create_collection(
            collection_name=name,
            vectors_config=vectors_config,
            sparse_vectors_config=sparse_config,
        )
        if hybrid:
            self._hybrid_collections.add(name)
        self._checked_collections.add(name)

    async def collection_exists(self, name: str) -> bool:
        """Report whether a collection exists.

        Args:
            name: The collection name.

        Returns:
            ``True`` if the collection exists.
        """
        client = await self._ensure_client()
        return await client.collection_exists(name)

    async def delete_collection(self, name: str) -> None:
        """Delete a collection and all its points.

        Args:
            name: The collection name.
        """
        client = await self._ensure_client()
        await client.delete_collection(name)
        self._hybrid_collections.discard(name)
        self._checked_collections.discard(name)

    async def _is_hybrid(self, client: Any, collection: str) -> bool:
        """Report whether ``collection`` has sparse-vector support, resolving lazily.

        A fresh store instance has no process-local record of a collection it
        did not itself create or upgrade through ``ensure_collection``, so a
        collection's hybrid state is resolved from the backend on first use
        and cached from then on.

        Args:
            client: The connected Qdrant client.
            collection: The collection name.

        Returns:
            Whether the collection was provisioned with the named sparse
            vector.
        """
        if collection not in self._checked_collections:
            info = await client.get_collection(collection)
            if info.config.params.sparse_vectors:
                self._hybrid_collections.add(collection)
            self._checked_collections.add(collection)
        return collection in self._hybrid_collections

    async def upsert(
        self,
        collection: str,
        records: Sequence[VectorRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Write or overwrite records in a collection.

        When ``collection`` has sparse-vector support (created or previously
        seen with ``ensure_collection(..., hybrid=True)``), each record's
        ``payload["text"]`` is also sparse-embedded and stored under the named
        sparse vector, so ``hybrid_search``'s keyword arm has real vectors to
        match. A record with no ``text`` payload key gets an empty sparse
        vector and only ever surfaces through the dense side of a hybrid
        search.

        Args:
            collection: The collection to write to.
            records: The records to upsert, in order.
            batch_size: The number of records per backend write call. Must be
                positive.

        Raises:
            ValueError: ``batch_size`` is not positive.
        """
        require_positive_batch_size(batch_size)
        client = await self._ensure_client()
        sparse_vectors: list[Any] | None = None
        if await self._is_hybrid(client, collection):
            texts = [
                str(record.payload.get(_TEXT_PAYLOAD_FIELD, "")) for record in records
            ]
            sparse_vectors = await self._ensure_sparse_embedder().embed(texts)
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            batch_sparse = (
                sparse_vectors[start : start + batch_size]
                if sparse_vectors is not None
                else [None] * len(batch)
            )
            points = [
                self._models.PointStruct(
                    id=str(record.id),
                    vector=self._point_vector(record, sparse),
                    payload=record.payload,
                )
                for record, sparse in zip(batch, batch_sparse, strict=True)
            ]
            await client.upsert(collection_name=collection, points=points)

    def _point_vector(self, record: VectorRecord, sparse: Any) -> Any:
        """Build a PointStruct's vector value, attaching a sparse vector if given.

        Args:
            record: The record being upserted.
            sparse: The record's sparse embedding, or ``None`` for a
                dense-only point.

        Returns:
            A plain dense vector, or a dict combining the unnamed dense vector
            (Qdrant's convention for the default vector when it is combined
            with named vectors) and the named sparse vector.
        """
        if sparse is None:
            return record.vector
        return {
            "": record.vector,
            _SPARSE_VECTOR_NAME: self._models.SparseVector(
                indices=sparse.indices, values=sparse.values
            ),
        }

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
        client = await self._ensure_client()
        response = await client.query_points(
            collection_name=collection,
            query=list(query_vector),
            limit=limit,
            query_filter=self._compile_filter(filters),
            with_payload=True,
        )
        return [self._to_hit(point) for point in response.points]

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
        """Search by dense vector and keyword text, fused by a weighted blend.

        Qdrant's native fusion methods (RRF, DBSF) have no continuous
        dense/keyword weight, so this runs the dense and sparse (BM25)
        searches independently, min-max normalizes each result set's scores
        to ``[0, 1]``, then combines them per id as
        ``alpha * dense + (1 - alpha) * sparse``. Each side fetches a wider
        candidate pool than ``limit`` so a document strong on only one signal
        still has a chance to reach the blended top results.

        Args:
            collection: The collection to search.
            query_vector: The dense query embedding.
            query_text: The query text, matched by BM25.
            limit: The maximum number of hits to return.
            filters: A flat-dict filter on payload fields.
            alpha: The dense/keyword balance. ``1.0`` is pure dense, ``0.0`` is
                pure keyword.

        Returns:
            The blended hits, highest combined score first.
        """
        client = await self._ensure_client()
        sparse = await self._ensure_sparse_embedder().embed([query_text])
        sparse_vector = sparse[0]
        query_filter = self._compile_filter(filters)
        pool_limit = max(limit * _HYBRID_POOL_MULTIPLIER, limit)
        dense_response, sparse_response = await asyncio.gather(
            client.query_points(
                collection_name=collection,
                query=list(query_vector),
                limit=pool_limit,
                query_filter=query_filter,
                with_payload=True,
            ),
            client.query_points(
                collection_name=collection,
                query=self._models.SparseVector(
                    indices=sparse_vector.indices, values=sparse_vector.values
                ),
                using=_SPARSE_VECTOR_NAME,
                limit=pool_limit,
                query_filter=query_filter,
                with_payload=True,
            ),
        )
        dense_hits = [self._to_hit(point) for point in dense_response.points]
        sparse_hits = [self._to_hit(point) for point in sparse_response.points]
        return self._fuse_by_alpha(dense_hits, sparse_hits, alpha=alpha, limit=limit)

    @staticmethod
    def _fuse_by_alpha(
        dense_hits: Sequence[VectorHit],
        sparse_hits: Sequence[VectorHit],
        *,
        alpha: float,
        limit: int,
    ) -> list[VectorHit]:
        """Blend two independently-scored hit lists into one ranked list.

        Args:
            dense_hits: Hits from the dense-only query.
            sparse_hits: Hits from the sparse-only query.
            alpha: The dense/keyword balance. ``1.0`` is pure dense, ``0.0`` is
                pure keyword.
            limit: The maximum number of hits to return.

        Returns:
            The blended hits, highest combined score first.
        """
        dense_by_id = {hit.id: hit for hit in dense_hits}
        sparse_by_id = {hit.id: hit for hit in sparse_hits}
        dense_norm = _min_max_normalize(
            {point_id: hit.score for point_id, hit in dense_by_id.items()}
        )
        sparse_norm = _min_max_normalize(
            {point_id: hit.score for point_id, hit in sparse_by_id.items()}
        )
        combined_scores = {
            point_id: alpha * dense_norm.get(point_id, 0.0)
            + (1 - alpha) * sparse_norm.get(point_id, 0.0)
            for point_id in {*dense_by_id, *sparse_by_id}
        }
        ranked_ids = sorted(
            combined_scores,
            key=lambda point_id: (-combined_scores[point_id], str(point_id)),
        )[:limit]
        return [
            VectorHit(
                id=point_id,
                score=combined_scores[point_id],
                payload=(dense_by_id.get(point_id) or sparse_by_id[point_id]).payload,
            )
            for point_id in ranked_ids
        ]

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
            page_offset: The offset from a previous ``scroll`` call.
            filters: A flat-dict filter on payload fields.
            with_vectors: Whether to return each record's vector.

        Returns:
            The page of records and the next page offset, or ``None`` at the
            end.
        """
        client = await self._ensure_client()
        points, offset = await client.scroll(
            collection_name=collection,
            limit=limit,
            offset=page_offset,
            scroll_filter=self._compile_filter(filters),
            with_payload=True,
            with_vectors=with_vectors,
        )
        records = [self._to_record(point) for point in points]
        return records, str(offset) if offset else None

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
        points = await client.retrieve(
            collection_name=collection,
            ids=[str(i) for i in ids],
            with_payload=True,
            with_vectors=True,
        )
        return [self._to_record(point) for point in points]

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
        result = await client.count(
            collection_name=collection, count_filter=self._compile_filter(filters)
        )
        return result.count

    async def delete(self, collection: str, ids: Sequence[UUID]) -> None:
        """Delete records by id.

        Args:
            collection: The collection to delete from.
            ids: The ids to delete.
        """
        client = await self._ensure_client()
        await client.delete(
            collection_name=collection,
            points_selector=self._models.PointIdsList(points=[str(i) for i in ids]),
        )

    async def close(self) -> None:
        """Release the backend connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
