"""Models for candidate review and schema patches."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from agrag.common.data_models.candidate import (
    CandidateKind,
    CandidateRecord,
    CandidateState,
)


ALLOWED_TRANSITIONS: dict[CandidateState, frozenset[CandidateState]] = {
    "pending": frozenset({"approved", "rejected"}),
    "approved": frozenset({"rejected"}),
    "rejected": frozenset(),
}
PATCH_FORMAT = 1
PATCH_README = (
    "Review this file. Merge additions and add_properties into your schema "
    "file, raise the schema version, then run conversion with this file."
)


def states_that_reach(target: CandidateState) -> list[CandidateState]:
    """List source states from which a candidate can enter ``target``.

    Args:
        target: State to enter.

    Returns:
        Allowed source states in alphabetical order.
    """
    return sorted(
        state for state, targets in ALLOWED_TRANSITIONS.items() if target in targets
    )


class CandidateQuery(BaseModel):
    """Filter candidate groups by kind, label, state, and total sightings.

    Attributes:
        kind: Candidate kind to include, or all kinds when unset.
        label: Exact candidate label to include, or all labels when unset.
        state: Review state to include. Defaults to pending candidates.
        min_count: Minimum aggregate sighting count, at least one.
    """

    model_config = ConfigDict(frozen=True)
    kind: CandidateKind | None = None
    label: str | None = None
    state: CandidateState | None = "pending"
    min_count: int = Field(default=1, ge=1)


class PatchBase(BaseModel):
    """Identify the schema used to plan the patch.

    Attributes:
        name: Schema name.
        version: Schema version.
        fingerprint: Fingerprint of the schema contents.
    """

    name: str
    version: str
    fingerprint: str


class PatchProperty(BaseModel):
    """Describe a property to add to an entity type.

    Attributes:
        entity: Entity label that will own the property.
        name: Property name.
        spec: Property definition, defaulting to an optional string.
    """

    entity: str
    name: str
    spec: dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "string",
            "required": False,
            "enum": None,
            "description": "",
        }
    )


class SchemaPatch(BaseModel):
    """A deterministic schema change set and its approved candidate ids.

    Attributes:
        readme: Instructions for applying the patch.
        patch_format: Patch format version.
        patch_id: Stable identifier derived from the base schema and candidates.
        created_at: Time the patch was planned.
        base_schema: Schema identity and fingerprint used for planning.
        additions: Entity and relation additions or relation pattern expansions.
        add_properties: Property definitions to add.
        evidence: Aggregate sightings keyed by planned schema change.
        candidate_ids: Approved candidate ids represented in the patch.
    """

    readme: str = PATCH_README
    patch_format: Literal[1] = PATCH_FORMAT
    patch_id: str
    created_at: datetime
    base_schema: PatchBase
    additions: dict[str, list[dict[str, Any]]] = Field(
        default_factory=lambda: {"entities": [], "relations": []}
    )
    add_properties: list[PatchProperty] = Field(default_factory=list)
    evidence: dict[str, int] = Field(default_factory=dict)
    candidate_ids: list[UUID] = Field(default_factory=list)


class CandidateGroup(BaseModel):
    """A deduplicated group of candidate nodes in one review state.

    Attributes:
        key: Stable key shared by the grouped candidate nodes.
        state: Current review state.
        count: Total sightings represented by the group.
        ids: Candidate node identifiers in the group.
        candidate: Representative candidate record.
        chunk_ids: Source chunk identifiers, when available.
        document_count: Number of documents represented by the group.
    """

    key: str
    state: CandidateState
    count: int
    ids: list[UUID]
    candidate: CandidateRecord
    chunk_ids: list[UUID] = Field(default_factory=list)
    document_count: int = 0

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "CandidateGroup":
        """Build a group from a candidate-listing result row.

        The row may contain a nested candidate record or candidate fields at
        the top level. Aggregate count and confidence values are applied to
        the representative record.

        Args:
            row: Flat graph result row with a key, state, count, and ids.

        Returns:
            Validated group with UUID identifiers.

        Raises:
            KeyError: If a required result field is missing.
            ValueError: If an identifier or candidate field is invalid.
        """
        record_data = dict(row.get("candidate", row))
        record_data.update(
            count=int(row["count"]), confidence=row.get("confidence", 0.0)
        )
        return cls(
            key=str(row["key"]),
            state=row["state"],
            count=int(row["count"]),
            ids=[UUID(str(value)) for value in row["ids"]],
            candidate=CandidateRecord.model_validate(record_data),
            chunk_ids=[UUID(str(value)) for value in row.get("chunk_ids", [])],
            document_count=int(row.get("document_count", 0)),
        )


class ReviewOutcome(BaseModel):
    """Report candidate groups moved and groups that could not be moved.

    Attributes:
        changed: Keys whose groups changed state.
        skipped: Keys not changed, mapped to the reason they were skipped.
    """

    changed: list[str] = Field(default_factory=list)
    skipped: dict[str, str] = Field(default_factory=dict)


class ApprovalResult(BaseModel):
    """Report approvals and the patch built from them.

    Attributes:
        outcome: Groups approved or skipped during the operation.
        patch: Schema patch for successful approvals, if any.
        path: Path of the written patch file, if requested and created.
    """

    outcome: ReviewOutcome
    patch: SchemaPatch | None = None
    path: str | None = None


class PruneReport(BaseModel):
    """Report groups matched and deleted by a prune operation.

    Attributes:
        matched: Number of groups matching the prune criteria.
        deleted: Number of groups deleted.
        applied: Whether a deletion was performed.
    """

    matched: int
    deleted: int
    applied: bool
