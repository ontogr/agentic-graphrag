"""Vector index types shared by the graph store and retrieval."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from agrag.common.data_models.stage_failure import StageFailure


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


class VectorKind(StrEnum):
    """Collections for chunks, raw entities, resolved entities and communities."""

    CHUNK = "chunks"
    ENTITY = "entities"
    RESOLVED_ENTITY = "resolved_entities"
    COMMUNITY = "communities"


class VectorRecord(BaseModel):
    """An embedding with searchable labels and its exact embedding input.

    Attributes:
        id: The graph node id.
        vector: Dense embedding values.
        labels: Schema label and ancestors, or one system kind label.
        text: The exact embedding input, also used for lexical search.
    """

    id: UUID
    vector: list[float]
    labels: list[str]
    text: str


class VectorTarget(BaseModel):
    """A graph node whose external vector needs synchronization.

    Attributes:
        kind: The collection that indexes this node.
        id: The graph node id.
    """

    kind: VectorKind
    id: UUID


class CollectionInfo(BaseModel):
    """The dimensions, distance metric and record count of a collection.

    Attributes:
        dimensions: Number of dense values in each vector.
        distance: Metric used for dense search.
        count: Number of records stored in the collection. A store may report an
            estimate when the caller declines an exact count.
    """

    dimensions: int
    distance: Distance
    count: int


class VectorWork(BaseModel):
    """Durable vector synchronization and deletion work after a graph commit.

    Attributes:
        targets: Committed nodes to re-embed from current graph text.
        deletes: Candidates to remove only if their graph nodes are absent.
    """

    targets: list[VectorTarget] = Field(default_factory=list)
    deletes: list[VectorTarget] = Field(default_factory=list)


class VectorRepairCounts(BaseModel):
    """Repair counts and failures for one collection.

    Attributes:
        checked: Committed graph nodes considered.
        missing: Graph nodes without a stored vector.
        upserted: Missing vectors successfully written.
        pruned: Orphan vectors removed when pruning was requested.
        failures: Embedding or storage failures that require another repair.
    """

    checked: int = 0
    missing: int = 0
    upserted: int = 0
    pruned: int = 0
    failures: list[StageFailure] = Field(default_factory=list)


class VectorRepairResult(BaseModel):
    """Repair outcomes keyed by collection kind.

    Attributes:
        kinds: Counts and failures for each requested collection.
    """

    kinds: dict[VectorKind, VectorRepairCounts] = Field(default_factory=dict)
