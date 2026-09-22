"""Graph.reevaluate()'s result type."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from agrag.ingestion.materialize import MatchDecision


class ReevaluationReport(BaseModel):
    """Report from Graph.reevaluate().

    Attributes:
        entities_reevaluated: Input entity ids reevaluated, deduped with
            input order preserved.
        matches_added: Confirmed matches with no active edge, now written.
        matches_removed: Ids of active match edges the resolver did not
            confirm, now deactivated.
        unchanged_count: Input entities with no incident added or removed
            edge.
    """

    entities_reevaluated: list[UUID] = Field(default_factory=list)
    matches_added: list[MatchDecision] = Field(default_factory=list)
    matches_removed: list[UUID] = Field(default_factory=list)
    unchanged_count: int = 0
