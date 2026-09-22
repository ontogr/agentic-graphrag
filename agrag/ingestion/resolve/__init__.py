"""Entity resolution public API."""

from agrag.ingestion.resolve.candidate_source import (
    GraphCandidateSource,
    PersistedCandidateSource,
    exact_match_lookup,
    persisted_candidate_indices,
)
from agrag.ingestion.resolve.exact_groups import exact_resolution_groups
from agrag.ingestion.resolve.resolver import (
    CandidateSource,
    Comparator,
    ComparisonResult,
    ComparisonVerdict,
    ExactMatch,
    FuzzyMatch,
    LLMVerify,
    ResolutionGroup,
    ResolutionResult,
    ResolvedMatch,
    Resolver,
    _group_matches,
)


__all__ = [
    "CandidateSource",
    "Comparator",
    "ComparisonResult",
    "ComparisonVerdict",
    "ExactMatch",
    "FuzzyMatch",
    "GraphCandidateSource",
    "PersistedCandidateSource",
    "persisted_candidate_indices",
    "LLMVerify",
    "ResolvedMatch",
    "ResolutionGroup",
    "ResolutionResult",
    "Resolver",
    "exact_match_lookup",
    "exact_resolution_groups",
    "_group_matches",
]
