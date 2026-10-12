"""Graph.reevaluate()'s result type."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from agrag.ingestion.resolved_entities import MatchDecision


class ReevaluationReport(BaseModel):
    """Report from Graph.reevaluate().

    Attributes:
        entities_reevaluated: Input entity ids reevaluated, deduped with
            input order preserved.
        matches_added: Confirmed matches with no active edge, now written.
        matches_removed: Ids of active match edges the resolver rejected, now
            deactivated. A rejection is an embedding score under the discard
            threshold or an explicit LLM "no match".
        matches_unverified: Ids of active match edges the resolver could not
            re-check, left active. The LLM request failed, the pair was over
            the per-label cap, no LLM settings were found, or the model
            answered uncertain.
        failed_llm_requests: LLM verification requests that raised.
        cap_truncated_pairs: Ambiguous pairs over the per-label cap.
        llm_unavailable_pairs: Ambiguous pairs that never reached the LLM
            because no LLM settings were found.
        unchanged_count: Input entities with no incident added or removed
            edge.
    """

    entities_reevaluated: list[UUID] = Field(default_factory=list)
    matches_added: list[MatchDecision] = Field(default_factory=list)
    matches_removed: list[UUID] = Field(default_factory=list)
    matches_unverified: list[UUID] = Field(default_factory=list)
    failed_llm_requests: int = 0
    cap_truncated_pairs: int = 0
    llm_unavailable_pairs: int = 0
    unchanged_count: int = 0
