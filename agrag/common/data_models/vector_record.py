"""Vector index types shared by the graph store and retrieval."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


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


class VectorHit(BaseModel):
    """One search result: a matched id, its score, and its stored payload.

    Returned by ``GraphStore.vector_search``.

    Attributes:
        id: The id of the matched record.
        score: The match score. Higher means a closer match, regardless of
            which distance metric the collection uses.
        payload: The payload stored with the matched record.
    """

    id: UUID
    score: float
    payload: dict[str, Any]
