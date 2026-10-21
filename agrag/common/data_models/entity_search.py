"""Models for entity search and bounded entity exploration.

An entity hit carries the passages that mention the entity, as evidence ids. An
exploration edge is either an assertion, with supporting passages, or a path,
which is a connection that no passage states. The models here are the values
that these calls exchange with callers.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from agrag.common.data_models.evidence import (
    EvidenceLocation,
    EvidenceSearchLeg,
    EvidenceSearchStatus,
    IndexState,
    LegFailure,
)


class EntityKind(StrEnum):
    """Whether an entity hit has a visible passage that mentions it.

    Attributes:
        SUPPORTED: At least one visible passage in scope mentions the entity.
        UNSUPPORTED: Passages in scope mention the entity, but none of them is
            current. The entity is not a verified fact in the current text.
    """

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"


class SupportingPassage(BaseModel):
    """A visible passage that supports an entity or a relation.

    Attributes:
        evidence_id: The evidence id of the passage. Fetch it to read the text.
        document_key: The key of the document the passage belongs to.
        location: The offsets or pages of the passage.
    """

    evidence_id: str
    document_key: str
    location: EvidenceLocation


class EntityHit(BaseModel):
    """One entity found by entity search.

    Attributes:
        entity_id: The id of the entity node.
        label: The entity label the node was found under.
        name: The entity name.
        properties: The schema properties of the entity. Internal fields, the
            embedding and the source chunk list are left out.
        kind: Whether the entity has a visible supporting passage.
        score: An ordering value. Higher scores rank first. It is not a
            confidence, and it is not a probability that the entity is correct.
        legs: The search legs that found the entity.
        support: Visible passages that mention the entity, up to the support
            limit of the call. Empty for an unsupported entity.
    """

    entity_id: str
    label: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    kind: EntityKind
    score: float
    legs: list[EvidenceSearchLeg]
    support: list[SupportingPassage] = Field(default_factory=list)


class EntityResult(BaseModel):
    """The result of one entity search call.

    Attributes:
        status: The overall outcome. A failed leg never shows as NO_MATCH.
        hits: The entities, best first.
        truncated: True when a search leg reached its candidate ceiling and
            fewer than ``limit`` entities were returned.
        index_state: Whether the needed indexes were ready. None when no index
            was checked.
        failures: The legs that failed. Empty when every leg ran.
    """

    status: EvidenceSearchStatus
    hits: list[EntityHit] = Field(default_factory=list)
    truncated: bool = False
    index_state: IndexState | None = None
    failures: list[LegFailure] = Field(default_factory=list)


class ExplorationStatus(StrEnum):
    """The outcome of an exploration call.

    Attributes:
        OK: The exploration ran. It may hold no edges.
        UNAVAILABLE: The start entity is missing, or no passage of it is in
            scope. Both cases give this same outcome.
        MALFORMED: The entity id is not a canonical UUID string.
        FAILED: The store failed while exploring.
    """

    OK = "ok"
    UNAVAILABLE = "unavailable"
    MALFORMED = "malformed"
    FAILED = "failed"


class ExplorationBound(StrEnum):
    """A bound that cut an exploration.

    Attributes:
        NODES: More entities were reached than ``max_nodes`` allows.
        EDGES: More edges existed than ``max_edges`` allows.
        DEPTH: Entities at the last allowed depth have further connections that
            were not followed.
        CANDIDATES: More relations existed than the per-frontier read limit.
    """

    NODES = "nodes"
    EDGES = "edges"
    DEPTH = "depth"
    CANDIDATES = "candidates"


class EdgeKind(StrEnum):
    """Whether an exploration edge is supported by a passage.

    Attributes:
        ASSERTION: The relation has visible supporting passages, which are listed
            in the edge.
        PATH: The entities are connected in the graph, and no passage in scope
            states the relation. A path is not a fact, and a conclusion drawn
            from it needs its own support.
    """

    ASSERTION = "assertion"
    PATH = "path"


class ExplorationNode(BaseModel):
    """An entity reached by exploration.

    Attributes:
        entity_id: The id of the entity node.
        label: The entity label.
        name: The entity name.
        depth: The number of relations from the start entity, at least one.
    """

    entity_id: str
    label: str
    name: str
    depth: int


class ExplorationEdge(BaseModel):
    """One relation between two entities found by exploration.

    Attributes:
        source_id: The id of the entity at the start of the stored relation.
        target_id: The id of the entity at the end of the stored relation.
        relation_type: The relation type.
        kind: Whether the edge is an assertion or a path.
        evidence: The visible supporting passages. Empty for a path.
    """

    source_id: str
    target_id: str
    relation_type: str
    kind: EdgeKind
    evidence: list[SupportingPassage] = Field(default_factory=list)


class ExplorationResult(BaseModel):
    """The result of one exploration call.

    Attributes:
        status: The overall outcome.
        nodes: The entities reached, in the order they were found.
        edges: The edges followed, in the order they were found.
        truncated: True when a bound cut the exploration.
        truncated_by: The bounds that cut the exploration.
        detail: A short message for a malformed or failed id. None otherwise.
    """

    status: ExplorationStatus
    nodes: list[ExplorationNode] = Field(default_factory=list)
    edges: list[ExplorationEdge] = Field(default_factory=list)
    truncated: bool = False
    truncated_by: list[ExplorationBound] = Field(default_factory=list)
    detail: str | None = None
