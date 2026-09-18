"""Entity resolution public API."""

from agrag.ingestion.resolve.candidate_source import (
    GraphCandidateSource,
    InBatchCandidateSource,
    exact_match_lookup,
)
from agrag.ingestion.resolve.resolver import (
    CandidateSource,
    Comparator,
    ComparisonVerdict,
    ExactMatch,
    FuzzyMatch,
    LLMVerify,
    ResolutionGroup,
    Resolver,
    _group_matches,
)


__all__ = [
    "CandidateSource",
    "Comparator",
    "ComparisonVerdict",
    "ExactMatch",
    "FuzzyMatch",
    "GraphCandidateSource",
    "InBatchCandidateSource",
    "LLMVerify",
    "ResolutionGroup",
    "Resolver",
    "exact_match_lookup",
    "_group_matches",
]
