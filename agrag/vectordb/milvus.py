"""Milvus vector-store backend."""

import json
import re
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from agrag.common.data_models.vector_record import Distance, VectorHit, VectorRecord
from agrag.vectordb.base import VectorStore
from agrag.vectordb.errors import VectorStoreMissingExtraError
from agrag.vectordb.settings import MilvusSettings


_VECTOR_FIELD = "vector"
_TEXT_FIELD = "text"
_SPARSE_FIELD = "sparse"
_PAYLOAD_FIELD = "payload"

# Milvus's self-hosted default gRPC response ceiling is roughly 64MB, but Zilliz
# Cloud caps a single response at about 4MB. Cap the number of records returned
# per page so a single scroll/retrieve call stays under that ceiling. This is a
# conservative constant, not bisection/retry logic.
MAX_RESPONSE_LIMIT = 16384

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _escape_field(name: str) -> str:
    """Validate a filter field name is a safe Milvus identifier.

    Args:
        name: The payload key used as a filter field.

    Returns:
        ``name`` unchanged, once validated.

    Raises:
        ValueError: ``name`` is not a safe identifier (a real injection surface,
            since Milvus filter syntax is a raw string).
    """
    if not _IDENTIFIER.match(name):
        raise ValueError(f"invalid Milvus filter field: {name!r}")
    return name


def _escape_scalar(value: Any) -> str:
    """Render a filter scalar as a Milvus expression literal.

    Args:
        value: A string, bool, int, or float to embed in a filter expression.

    Returns:
        The value as a safely escaped Milvus literal.

    Raises:
        TypeError: ``value`` is not a supported scalar type.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise TypeError(f"unsupported filter value type: {type(value).__name__}")


def _escape_list(values: Sequence[Any]) -> str:
    """Render a list filter value as a Milvus ``in`` clause body.

    Args:
        values: The values to match any of.

    Returns:
        The bracketed, comma-separated, escaped list.
    """
    return "[" + ", ".join(_escape_scalar(v) for v in values) + "]"


class MilvusVectorStore(VectorStore):
    """A ``VectorStore`` backed by Milvus, including native hybrid search.

    The client connects lazily on first use, so constructing the store does not
    open a network connection. Milvus performs BM25 server-side, so hybrid
    search needs no client-side sparse embedder; the sparse vector is computed
    by a Milvus ``Function`` from the ``text`` field on write and at query time.
    """

    def __init__(
        self,
        *,
        settings: MilvusSettings | None = None,
        client: Any | None = None,
    ) -> None:
        """Build the store.

        Args:
            settings: Milvus connection settings. Defaults to
                ``MilvusSettings()``.
            client: A pre-built ``AsyncMilvusClient``, for tests. When set,
                ``__init__`` imports nothing and the store calls this object
                directly instead of building one.
        """
        self._settings = settings or MilvusSettings()
        self._client: Any = client

    async def _ensure_client(self) -> Any:
        """Build the Milvus client once and cache it.

        Returns:
            The connected client object.

        Raises:
            VectorStoreMissingExtraError: pymilvus is not installed.
        """
        if self._client is None:
            try:
                # Lazy import: a clean install must raise
                # VectorStoreMissingExtraError, not ImportError, when
                # pymilvus is absent.
                from pymilvus import AsyncMilvusClient  # noqa: PLC0415
            except ImportError as exc:
                raise VectorStoreMissingExtraError("milvus") from exc
            if self._settings.token:
                self._client = AsyncMilvusClient(
                    uri=self._settings.uri, token=self._settings.token
                )
            else:
                self._client = AsyncMilvusClient(uri=self._settings.uri)
        return self._client

    def _milvus_metric(self, distance: Distance) -> str:
        """Map our ``Distance`` to Milvus's metric-type name.

        Args:
            distance: The distance metric to map.

        Returns:
            The matching Milvus metric name.
        """
        return {
            Distance.COSINE: "COSINE",
            Distance.EUCLID: "L2",
            Distance.DOT: "IP",
        }[distance]

    def _compile_filter(self, filters: dict[str, Any] | None) -> str:
        """Build a Milvus filter expression from a flat-dict payload filter.

        Args:
            filters: A flat-dict filter: a scalar value means exact match, a
                list value means any of, and all keys are AND-ed together.
                ``None`` means no filter.

        Returns:
            A Milvus ``filter`` expression string, or ``""`` when ``filters`` is
            empty.
        """
        if not filters:
            return ""
        clauses = []
        for key, value in filters.items():
            field = _escape_field(key)
            if isinstance(value, list):
                clauses.append(f"{field} in {_escape_list(value)}")
            else:
                clauses.append(f"{field} == {_escape_scalar(value)}")
        return " and ".join(clauses)

    @staticmethod
    def _to_hit(row: dict[str, Any]) -> VectorHit:
        """Convert a Milvus result row to a ``VectorHit``.

        Args:
            row: A Milvus search/query result row.

        Returns:
            The equivalent hit.
        """
        payload = {}
        if row.get(_PAYLOAD_FIELD):
            payload = json.loads(row[_PAYLOAD_FIELD])
        return VectorHit(
            id=UUID(str(row["id"])),
            score=float(row.get("distance", 0.0)),
            payload=payload,
        )

    @staticmethod
    def _to_record(row: dict[str, Any]) -> VectorRecord:
        """Convert a Milvus result row to a ``VectorRecord``.

        Args:
            row: A Milvus query result row.

        Returns:
            The equivalent record.
        """
        payload = {}
        if row.get(_PAYLOAD_FIELD):
            payload = json.loads(row[_PAYLOAD_FIELD])
        vector = list(row.get(_VECTOR_FIELD) or [])
        return VectorRecord(
            id=UUID(str(row["id"])),
            vector=vector,
            payload=payload,
        )

    async def initialize(self) -> None:
        """Check connectivity and authentication."""
        client = await self._ensure_client()
        await client.list_collections()

    async def ensure_collection(
        self, name: str, *, dimensions: int, distance: Distance, hybrid: bool = False
    ) -> None:
        """Create the collection if it does not exist.

        Milvus performs BM25 server-side, so the sparse field and its ``Function``
        are always provisioned; the ``hybrid`` flag is accepted for interface
        parity but is a no-op here.

        Args:
            name: The collection name.
            dimensions: The embedding dimension.
            distance: The distance metric new collections use.
            hybrid: Accepted for interface parity; ignored by Milvus.
        """
        from pymilvus import (  # noqa: PLC0415
            CollectionSchema,
            DataType,
            FieldSchema,
            Function,
            FunctionType,
        )

        client = await self._ensure_client()
        if await client.has_collection(name):
            return
        metric = self._milvus_metric(distance)
        fields = [
            FieldSchema(
                name="id",
                dtype=DataType.VARCHAR,
                is_primary=True,
                max_length=64,
            ),
            FieldSchema(
                name=_VECTOR_FIELD,
                dtype=DataType.FLOAT_VECTOR,
                dim=dimensions,
            ),
            FieldSchema(
                name=_TEXT_FIELD,
                dtype=DataType.VARCHAR,
                max_length=65535,
                enable_analyzer=True,
            ),
            FieldSchema(name=_SPARSE_FIELD, dtype=DataType.SPARSE_FLOAT_VECTOR),
            FieldSchema(name=_PAYLOAD_FIELD, dtype=DataType.VARCHAR, max_length=65535),
        ]
        bm25 = Function(
            name="bm25",
            function_type=FunctionType.BM25,
            input_field_names=[_TEXT_FIELD],
            output_field_names=[_SPARSE_FIELD],
        )
        schema = CollectionSchema(fields, functions=[bm25], enable_dynamic_field=False)
        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name=_VECTOR_FIELD, index_type="AUTOINDEX", metric_type=metric
        )
        index_params.add_index(
            field_name=_SPARSE_FIELD,
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="BM25",
        )
        await client.create_collection(
            collection_name=name, schema=schema, index_params=index_params
        )
        await client.load_collection(name)

    async def collection_exists(self, name: str) -> bool:
        """Report whether a collection exists.

        Args:
            name: The collection name.

        Returns:
            ``True`` if the collection exists.
        """
        client = await self._ensure_client()
        return await client.has_collection(name)

    async def delete_collection(self, name: str) -> None:
        """Delete a collection and all its entities.

        Args:
            name: The collection name.
        """
        client = await self._ensure_client()
        await client.drop_collection(name)

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
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            data = [
                {
                    "id": str(record.id),
                    _VECTOR_FIELD: record.vector,
                    _TEXT_FIELD: record.payload.get(_TEXT_FIELD, ""),
                    _PAYLOAD_FIELD: json.dumps(record.payload, default=str),
                }
                for record in batch
            ]
            await client.insert(collection_name=collection, data=data)
            await client.flush(collection_name=collection)

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
            filters: A flat-dict filter on scalar fields.

        Returns:
            The matched hits, highest score first.
        """
        client = await self._ensure_client()
        response = await client.search(
            collection_name=collection,
            data=[list(query_vector)],
            anns_field=_VECTOR_FIELD,
            limit=limit,
            filter=self._compile_filter(filters),
            output_fields=["id", _PAYLOAD_FIELD],
        )
        return [self._to_hit(row) for row in response[0]]

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

        Fusion uses Milvus's native weighted reranker, which normalizes each
        request's scores before applying ``alpha``.

        Args:
            collection: The collection to search.
            query_vector: The dense query embedding.
            query_text: The query text, matched by BM25.
            limit: The maximum number of hits to return.
            filters: A flat-dict filter on scalar fields.
            alpha: The dense/keyword balance. ``1.0`` is pure dense, ``0.0`` is
                pure keyword.

        Returns:
            The fused hits, highest score first.
        """
        from pymilvus import AnnSearchRequest, WeightedRanker  # noqa: PLC0415

        client = await self._ensure_client()
        expr = self._compile_filter(filters)
        dense_req = AnnSearchRequest(
            data=[list(query_vector)],
            anns_field=_VECTOR_FIELD,
            param={},
            limit=limit,
            filter=expr or None,
        )
        sparse_req = AnnSearchRequest(
            data=[query_text],
            anns_field=_SPARSE_FIELD,
            param={},
            limit=limit,
            filter=expr or None,
        )
        response = await client.hybrid_search(
            collection_name=collection,
            reqs=[dense_req, sparse_req],
            ranker=WeightedRanker(alpha, 1 - alpha),
            limit=limit,
            output_fields=["id", _PAYLOAD_FIELD],
        )
        return [self._to_hit(row) for row in response[0]]

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
            page_offset: The numeric offset from a previous ``scroll`` call.
            filters: A flat-dict filter on scalar fields.
            with_vectors: Whether to return each record's vector.

        Returns:
            The page of records and the next page offset, or ``None`` at the
            end.
        """
        client = await self._ensure_client()
        output_fields = ["id", _PAYLOAD_FIELD]
        if with_vectors:
            output_fields.append(_VECTOR_FIELD)
        safe_limit = min(limit, MAX_RESPONSE_LIMIT)
        offset = int(page_offset) if page_offset is not None else 0
        rows = await client.query(
            collection_name=collection,
            filter=self._compile_filter(filters),
            output_fields=output_fields,
            limit=safe_limit,
            offset=offset,
        )
        records = [self._to_record(row) for row in rows]
        next_offset = str(offset + len(rows)) if len(rows) == safe_limit else None
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
        if not ids:
            return []
        rows = await client.get(
            collection_name=collection,
            ids=[str(i) for i in ids],
            output_fields=["id", _VECTOR_FIELD, _PAYLOAD_FIELD],
        )
        by_id = {row["id"]: row for row in rows}
        records = []
        for item_id in ids:
            row = by_id.get(str(item_id))
            if row is not None:
                records.append(self._to_record(row))
        return records

    async def count(
        self, collection: str, *, filters: dict[str, Any] | None = None
    ) -> int:
        """Count records in a collection.

        Args:
            collection: The collection to count.
            filters: A flat-dict filter on scalar fields.

        Returns:
            The number of matching records.
        """
        client = await self._ensure_client()
        rows = await client.query(
            collection_name=collection,
            filter=self._compile_filter(filters),
            output_fields=["count(*)"],
            limit=1,
        )
        if not rows:
            return 0
        return int(rows[0]["count(*)"])

    async def delete(self, collection: str, ids: Sequence[UUID]) -> None:
        """Delete records by id.

        Args:
            collection: The collection to delete from.
            ids: The ids to delete.
        """
        client = await self._ensure_client()
        await client.delete(collection_name=collection, ids=[str(i) for i in ids])

    async def close(self) -> None:
        """Release the backend connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
