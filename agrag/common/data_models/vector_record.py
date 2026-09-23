"""Vector storage record shapes shared by VectorStore and GraphStore."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


PENDING_VECTOR_FLAG = "_pending"
"""Payload flag marking a vector as written by an in-flight Cutover Job.

Mirrored at write time and cleared at commit. Payload filters only match
on present values, so pending-exclusion needs this explicit boolean
rather than relying on the job-id key's absence.

Every backend's filter compiler reads the flag two ways: a filter that
omits it, or sets it ``False``, excludes records flagged true while
still returning records written before the flag existed, and a filter
that sets it ``True`` returns only the flagged records, which is the
maintenance path that has to see a job's own in-flight vectors.
"""


class Distance(StrEnum):
    """A distance metric a vector index compares embeddings with.

    Attributes:
        COSINE: Cosine similarity. The default for most embedding models.
        EUCLID: Euclidean (L2) distance.
        DOT: Dot product.
    """

    COSINE = "Cosine"
    EUCLID = "Euclid"
    DOT = "Dot"


class VectorRecord(BaseModel):
    """One vector and its payload, ready to write to a collection or index.

    The collection or index name is a call argument on the store, not a field
    here, so one record type can target any collection.

    Attributes:
        id: The record id. Callers set this to the id of the domain object the
            vector represents.
        vector: The dense embedding.
        payload: Fields stored alongside the vector, such as the source text or
            a chunk id. Read back unchanged by ``search``/``hybrid_search``.
    """

    id: UUID
    vector: list[float]
    payload: dict[str, Any]


class VectorHit(BaseModel):
    """One search result: a matched id, its score, and its stored payload.

    Returned by both ``VectorStore.search``/``hybrid_search`` and
    ``GraphStore.vector_search``, so a caller cannot tell which store produced
    a given hit.

    Attributes:
        id: The id of the matched record.
        score: The match score. Higher means a closer match, regardless of
            which distance metric the collection uses.
        payload: The payload stored with the matched record.
    """

    id: UUID
    score: float
    payload: dict[str, Any]
