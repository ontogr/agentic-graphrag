"""Resolution-stage stats."""

from __future__ import annotations

from pydantic import BaseModel


class ResolutionStats(BaseModel):
    """Resolution-stage results.

    Attributes:
        exact_match_hits: Mentions that matched an already-persisted
            entity via the global exact-match tier.
        in_batch_groups: Groups of two or more mentions from this batch that
            the fuzzy, embedding, or LLM tier formed. Unmatched mentions are
            not groups.
        ambiguous_count: LLM answers that were uncertain, missing, or
            malformed. These pairs are never merged.
        failed_llm_requests: LLM verification requests that raised. Their
            pairs stay undecided and are not merged.
        cap_truncated_pairs: Ambiguous pairs over the per-label
            ``max_llm_pairs`` cap. They never reached the LLM.
        llm_unavailable_pairs: Ambiguous pairs skipped because no LLM
            settings were found.
    """

    exact_match_hits: int = 0
    in_batch_groups: int = 0
    ambiguous_count: int = 0
    failed_llm_requests: int = 0
    cap_truncated_pairs: int = 0
    llm_unavailable_pairs: int = 0
