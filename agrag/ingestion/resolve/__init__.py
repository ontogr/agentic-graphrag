"""Entity resolution public API."""

from agrag.ingestion.resolve.candidate_source import (
    GraphCandidateSource,
    PersistedCandidateSource,
    build_relation_neighbors,
    fetch_persisted_neighbors,
    persisted_candidate_indices,
)
from agrag.ingestion.resolve.exact_groups import exact_resolution_groups
from agrag.ingestion.resolve.resolution import (
    SYSTEM_RELATION_TYPES,
    BatchResolution,
    find_exact_matches,
    resolve_among,
    resolve_batch,
    resolve_persisted,
)
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
    "SYSTEM_RELATION_TYPES",
    "BatchResolution",
    "find_exact_matches",
    "resolve_among",
    "resolve_batch",
    "resolve_persisted",
    "CandidateSource",
    "Comparator",
    "ComparisonResult",
    "ComparisonVerdict",
    "ExactMatch",
    "FuzzyMatch",
    "GraphCandidateSource",
    "PersistedCandidateSource",
    "build_relation_neighbors",
    "fetch_persisted_neighbors",
    "persisted_candidate_indices",
    "LLMVerify",
    "ResolvedMatch",
    "ResolutionGroup",
    "ResolutionResult",
    "Resolver",
    "exact_resolution_groups",
    "_group_matches",
]
