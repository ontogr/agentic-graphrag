"""Comparison strategies used by entity resolution."""

# The implementations remain in ``resolver`` during the package conversion.
# Re-exporting them here keeps the move source-compatible while the resolver
# orchestration is split out in a later phase.
from agrag.ingestion.resolve.resolver import (
    Comparator,
    ComparisonResult,
    ComparisonVerdict,
    ExactMatch,
    FuzzyMatch,
    LLMVerify,
)


__all__ = [
    "Comparator",
    "ComparisonResult",
    "ComparisonVerdict",
    "ExactMatch",
    "FuzzyMatch",
    "LLMVerify",
]
