"""An in-memory vector store for contract and graph-seam integration tests."""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from agrag.common.data_models.vector_record import (
    CollectionInfo,
    Distance,
    VectorHit,
    VectorKind,
    VectorRecord,
)
from agrag.vectordb.base import VectorStore
from agrag.vectordb.errors import CollectionMismatchError, VectorStoreError


@dataclass
class _Collection:
    dimensions: int
    distance: Distance
    records: dict[UUID, VectorRecord] = field(default_factory=dict)


class FakeVectorStore(VectorStore):
    """Store vectors in memory while matching the external-store contract."""

    name = "fake"
    max_results = 16384

    def __init__(self, collection_prefix: str = "fake") -> None:
        """Create an empty store with a stable collection prefix."""
        self.collection_prefix = collection_prefix
        self._collections: dict[VectorKind, _Collection] = {}
        self.fail_next_upsert = False
        self.fail_next_delete = False

    async def initialize(self) -> None:
        """Make the in-memory store ready for use."""

    async def close(self) -> None:
        """Close the in-memory store without discarding its collections."""

    async def ensure_collection(
        self, kind: VectorKind, *, dimensions: int, distance: Distance
    ) -> None:
        """Create a collection or reject a different vector shape or metric."""
        if distance is Distance.DOT:
            raise ValueError("DOT distance is not supported")
        collection = self._collections.get(kind)
        if collection is None:
            self._collections[kind] = _Collection(dimensions, distance)
            return
        if collection.dimensions != dimensions or collection.distance != distance:
            raise CollectionMismatchError(
                f"{kind.value} has dimensions={collection.dimensions}, "
                f"distance={collection.distance.value}; requested "
                f"dimensions={dimensions}, distance={distance.value}"
            )

    async def collection_info(self, kind: VectorKind) -> CollectionInfo | None:
        """Return collection shape and current record count, if present."""
        collection = self._collections.get(kind)
        if collection is None:
            return None
        return CollectionInfo(
            dimensions=collection.dimensions,
            distance=collection.distance,
            count=len(collection.records),
        )

    async def delete_collection(self, kind: VectorKind) -> None:
        """Remove a collection if it exists."""
        self._collections.pop(kind, None)

    async def upsert(
        self,
        kind: VectorKind,
        records: Sequence[VectorRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Overwrite records by id, failing once when the fault hook is set."""
        if self.fail_next_upsert:
            self.fail_next_upsert = False
            raise VectorStoreError("injected upsert failure")
        collection = self._collections.get(kind)
        if collection is None:
            raise VectorStoreError(f"collection {kind.value!r} does not exist")
        for offset in range(0, len(records), batch_size):
            for record in records[offset : offset + batch_size]:
                if len(record.vector) != collection.dimensions:
                    raise VectorStoreError(
                        f"record {record.id} has {len(record.vector)} dimensions; "
                        f"expected {collection.dimensions}"
                    )
                collection.records[record.id] = record

    async def search(
        self,
        kind: VectorKind,
        vector: Sequence[float],
        *,
        limit: int,
        labels: Sequence[str] | None = None,
    ) -> list[VectorHit]:
        """Return dense matches in descending graph-native score order."""
        self._validate_limit(limit)
        collection = self._collections.get(kind)
        if collection is None:
            return []
        matches = [
            (record, self._dense_score(collection, vector, record.vector))
            for record in collection.records.values()
            if self._matches_labels(record, labels)
        ]
        matches.sort(key=lambda item: (-item[1], str(item[0].id)))
        return [self._hit(record, score) for record, score in matches[:limit]]

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
        """Rank matches by a weighted dense and lexical score."""
        self._validate_limit(limit)
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be between 0 and 1")
        collection = self._collections.get(kind)
        if collection is None:
            return []
        query_tokens = set(re.findall(r"\w+", text.casefold()))
        matches: list[tuple[VectorRecord, float]] = []
        for record in collection.records.values():
            if not self._matches_labels(record, labels):
                continue
            dense = self._dense_score(collection, vector, record.vector)
            tokens = re.findall(r"\w+", record.text.casefold())
            lexical = (
                sum(math.log1p(tokens.count(token)) for token in query_tokens)
                if query_tokens
                else 0.0
            )
            if alpha == 0.0 and lexical == 0.0:
                continue
            matches.append((record, alpha * dense + (1.0 - alpha) * lexical))
        matches.sort(key=lambda item: (-item[1], str(item[0].id)))
        return [self._hit(record, score) for record, score in matches[:limit]]

    async def delete(self, kind: VectorKind, ids: Sequence[UUID]) -> None:
        """Delete ids while ignoring absent collections and records."""
        if self.fail_next_delete:
            self.fail_next_delete = False
            raise VectorStoreError("injected delete failure")
        collection = self._collections.get(kind)
        if collection is None:
            return
        for record_id in ids:
            collection.records.pop(record_id, None)

    async def list_ids(
        self, kind: VectorKind, *, after: UUID | None = None, limit: int = 1000
    ) -> list[UUID]:
        """Return ascending ids after the optional exclusive cursor."""
        if limit < 0:
            raise ValueError("limit cannot be negative")
        collection = self._collections.get(kind)
        if collection is None:
            return []
        ids = sorted(collection.records)
        if after is not None:
            ids = [record_id for record_id in ids if record_id > after]
        return ids[:limit]

    def inject_orphan(
        self,
        kind: VectorKind,
        id: UUID,  # noqa: A002
        vector: list[float],
    ) -> None:
        """Insert an unjoined record to exercise orphan handling in graph tests."""
        collection = self._collections.get(kind)
        if collection is None:
            raise VectorStoreError(f"collection {kind.value!r} does not exist")
        if len(vector) != collection.dimensions:
            raise ValueError(
                f"orphan vector must have {collection.dimensions} dimensions"
            )
        collection.records[id] = VectorRecord(id=id, vector=vector, labels=[], text="")

    def _validate_limit(self, limit: int) -> None:
        """Reject requests above the adapter's hard result cap."""
        if limit < 0:
            raise ValueError("limit cannot be negative")
        if limit > self.max_results:
            raise ValueError(f"limit cannot exceed {self.max_results}")

    @staticmethod
    def _matches_labels(record: VectorRecord, labels: Sequence[str] | None) -> bool:
        """Return whether a record shares any requested label."""
        return labels is None or bool(set(record.labels) & set(labels))

    @staticmethod
    def _dense_score(
        collection: _Collection, query: Sequence[float], candidate: Sequence[float]
    ) -> float:
        """Convert cosine or Euclidean distance to a higher-is-closer score."""
        if len(query) != collection.dimensions:
            raise ValueError(
                f"query vector must have {collection.dimensions} dimensions"
            )
        if collection.distance is Distance.COSINE:
            query_norm = math.sqrt(sum(value * value for value in query))
            candidate_norm = math.sqrt(sum(value * value for value in candidate))
            similarity = (
                sum(left * right for left, right in zip(query, candidate, strict=True))
                / (query_norm * candidate_norm)
                if query_norm and candidate_norm
                else 0.0
            )
            return (1.0 + similarity) / 2.0
        squared_distance = sum(
            (left - right) ** 2 for left, right in zip(query, candidate, strict=True)
        )
        return 1.0 / (1.0 + squared_distance)

    @staticmethod
    def _hit(record: VectorRecord, score: float) -> VectorHit:
        """Return a public hit containing only the labels filter payload."""
        return VectorHit(id=record.id, score=score, payload={"labels": record.labels})
