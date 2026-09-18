"""Validation for LLM batch entity-match verdicts."""

from collections.abc import Iterable

from pydantic import BaseModel, ValidationError

from agrag.ingestion.resolve.resolver import ComparisonResult, ComparisonVerdict


class BatchMatchVerdict(BaseModel):
    """One LLM result bound to the candidate pair it judged."""

    pair_id: str
    verdict: ComparisonVerdict
    reasoning: str | None = None


def validate_batch_verdicts(
    pair_ids: Iterable[str], results: Iterable[object]
) -> dict[str, ComparisonResult]:
    """Return fail-safe verdicts keyed by requested candidate pair identifiers.

    Unknown, duplicate, missing, and malformed results resolve to ``NO_MATCH``.
    This avoids assigning a valid LLM response to a different candidate pair.
    """
    requested = set(pair_ids)
    verdicts = {
        pair_id: ComparisonResult(verdict=ComparisonVerdict.NO_MATCH)
        for pair_id in requested
    }
    seen: set[str] = set()
    for result in results:
        try:
            verdict = BatchMatchVerdict.model_validate(result)
        except ValidationError:
            continue
        if verdict.pair_id not in requested:
            continue
        if verdict.pair_id in seen:
            verdicts[verdict.pair_id] = ComparisonResult(
                verdict=ComparisonVerdict.NO_MATCH
            )
            continue
        seen.add(verdict.pair_id)
        verdicts[verdict.pair_id] = ComparisonResult(
            verdict=verdict.verdict,
            reasoning=verdict.reasoning,
        )
    return verdicts
