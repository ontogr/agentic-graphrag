"""Graph.consolidate()'s result type."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agrag.common.data_models.stage_failure import StageFailure
from agrag.ingestion.resolved_entities import MatchDecision


class ConsolidationReport(BaseModel):
    """Report from Graph.consolidate().

    Attributes:
        would_match: Confirmed non-exact matches found, whether applied or not.
        applied: Whether the matches were applied.
        failures: Failures reading the candidates of an entity, which that
            entity then skips, and failures writing a match graph or
            rebuilding resolved entities. Only the candidate read failures
            appear when apply is False.
        ambiguous_count: LLM answers that were uncertain, missing, or
            malformed. These pairs never merge.
        failed_llm_requests: LLM verification requests that raised, summed
            over all labels. Their pairs are undecided and not merged.
        cap_truncated_pairs: Ambiguous pairs over the per-label cap
            (``max_llm_pairs``), summed over all labels. They never reached
            the LLM.
        llm_unavailable_pairs: Ambiguous pairs that never reached the LLM
            because no LLM settings were found, summed over all labels.
    """

    would_match: list[MatchDecision] = Field(default_factory=list)
    applied: bool = False
    failures: list[StageFailure] = Field(default_factory=list)
    ambiguous_count: int = 0
    failed_llm_requests: int = 0
    cap_truncated_pairs: int = 0
    llm_unavailable_pairs: int = 0
