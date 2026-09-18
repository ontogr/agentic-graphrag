"""Resolution-stage stats."""

from __future__ import annotations

from pydantic import BaseModel


class ResolutionStats(BaseModel):
    """Resolution-stage results.

    Attributes:
        exact_match_hits: Mentions that matched an already-persisted
            entity via the global exact-match tier.
        in_batch_groups: Resolution groups the in-batch fuzzy/LLM tier
            found.
        ambiguous_count: Comparisons no comparator could confidently
            decide. These pairs are never merged.
    """

    exact_match_hits: int = 0
    in_batch_groups: int = 0
    ambiguous_count: int = 0
